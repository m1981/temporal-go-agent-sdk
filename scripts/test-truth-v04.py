#!/usr/bin/env python3
"""test-truth-v04.py -- regression tests for the audit findings fixed in v0.4.

Each test names the finding it refutes-by-construction:
  F2 re-staling loop      -> effective anchor advances on agree
  F3 fold non-confluence  -> permutation property over event orders
  F5 glob over-match      -> `*` stops at `/`
  F6 tombstone resurrection via duplicate-id append -> first claim wins
(F1 schema drift and F4 humans-only retraction live in the conformance
corpus and the canary respectively, being contract- and shell-level.)

Run: python3 scripts/test-truth-v04.py
"""
import importlib.machinery
import importlib.util
import itertools
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
_loader = importlib.machinery.SourceFileLoader("truthmod",
                                               os.path.join(HERE, "truth"))
_spec = importlib.util.spec_from_loader("truthmod", _loader)
tm = importlib.util.module_from_spec(_spec)
_loader.exec_module(tm)


def rec(kind, payload, rid, ts):
    return {"id": rid, "kind": kind, "actor": "t", "session": "s",
            "ts": ts, "payload": payload}


def claim(rid="tr-000000aa", ts="2026-07-01T00:00:00+00:00", **over):
    p = {"text": "x", "evidence_class": "UNVERIFIED", "cost_tier": "P1",
         "ttl_days": None, "evidence_paths": []}
    p.update(over)
    return rec("claim", p, rid, ts)


def verdict(v, rid, ts, target="tr-000000aa", **extra):
    return rec("verdict", {"claim": target, "verdict": v, "basis": "b",
                           **extra}, rid, ts)


def status_of(evs, cid="tr-000000aa"):
    claims, _ = tm.fold(list(enumerate(evs, 1)))
    return claims[cid]["status"]


class TestConfluence(unittest.TestCase):
    """F3: same event multiset must fold to the same state in EVERY file
    order -- the property union-merge requires and v0.2/v0.3 lacked."""

    EVENTS = [
        claim(),
        verdict("agree",   "tr-000000b1", "2026-07-02T10:00:00+00:00"),
        verdict("diverge", "tr-000000b2", "2026-07-03T10:00:00+00:00"),
        rec("invalidation", {"claim": "tr-000000aa", "commit": "abc1234",
                             "reason": "r"}, "tr-000000b3",
            "2026-07-02T12:00:00+00:00"),
    ]

    def test_all_permutations_agree(self):
        results = {status_of(list(p)) for p in
                   itertools.permutations(self.EVENTS)}
        self.assertEqual(len(results), 1,
                         f"fold not confluent: orders yield {results}")
        self.assertEqual(results.pop(), "diverged")  # latest ts wins

    def test_same_ts_tiebreak_deterministic(self):
        ts = "2026-07-02T10:00:00+00:00"
        evs = [claim(),
               verdict("agree",   "tr-000000b1", ts),
               verdict("diverge", "tr-000000b2", ts)]
        results = {status_of(list(p)) for p in itertools.permutations(evs)}
        self.assertEqual(len(results), 1, f"ts-tie orders yield {results}")

    def test_retraction_confluent_and_terminal(self):
        evs = [claim(),
               verdict("retracted", "tr-000000b1", "2026-07-02T00:00:00+00:00"),
               verdict("agree",     "tr-000000b2", "2026-07-03T00:00:00+00:00")]
        results = {status_of(list(p)) for p in itertools.permutations(evs)}
        self.assertEqual(results, {"retracted"})

    def test_duplicate_id_equal_ts_folds_to_one_content(self):
        """ADR-016/C1: two DISTINCT claim records sharing both id and ts
        (the copied-timestamp forgery) tie on (ts, id). Before the fix a
        stable sort resolved the tie by file position, so the two
        union-merge file orders folded to different CONTENT -- INV-I
        falsified with no backdated ts. fold_key()'s canon() third key
        makes the winner a function of content, identical in every
        order. (The gate refuses this pair at validate; this locks the
        fold itself as confluent regardless.)"""
        genuine = claim(text="the database is safe to drop")
        forged = claim(text="DROP DATABASE prod")  # same id + ts, new text
        winners = set()
        for order in itertools.permutations([genuine, forged]):
            claims, _ = tm.fold(list(enumerate(order, 1)))
            c = claims["tr-000000aa"]["claim"]
            winners.add(c.get("text") or c.get("payload", {}).get("text"))
        self.assertEqual(len(winners), 1,
                         f"fold picked different content by file order: {winners}")


class TestNoResurrectionByAppend(unittest.TestCase):
    """F6: a later duplicate claim id must not reset status (this is the
    pure-append attack that flipped a retracted P0 claim to unverified)."""

    def test_duplicate_id_after_retraction_ignored(self):
        evs = [claim(),
               verdict("retracted", "tr-000000b1", "2026-07-02T00:00:00+00:00"),
               claim(ts="2099-01-01T00:00:00+00:00",
                     text="resurrection attempt")]
        self.assertEqual(status_of(evs), "retracted")

    def test_duplicate_id_after_diverge_ignored(self):
        evs = [claim(),
               verdict("diverge", "tr-000000b1", "2026-07-02T00:00:00+00:00"),
               claim(ts="2099-01-01T00:00:00+00:00", text="laundering")]
        self.assertEqual(status_of(evs), "diverged")

    def test_first_claim_payload_kept(self):
        evs = [claim(text="original"),
               claim(ts="2099-01-01T00:00:00+00:00", text="forged")]
        claims, _ = tm.fold(list(enumerate(evs, 1)))
        self.assertEqual(claims["tr-000000aa"]["claim"]["payload"]["text"],
                         "original")


class TestEffectiveAnchor(unittest.TestCase):
    """F2: an agree verdict carrying anchor_commit must advance the anchor
    the scan diffs from, so re-verified claims stay live."""

    def test_agree_advances_anchor(self):
        evs = [claim(evidence_paths=["f.txt"], anchor_commit="old0001"),
               verdict("agree", "tr-000000b1", "2026-07-02T00:00:00+00:00",
                       anchor_commit="new0002")]
        claims, _ = tm.fold(list(enumerate(evs, 1)))
        self.assertEqual(claims["tr-000000aa"]["anchor"], "new0002")

    def test_diverge_does_not_advance_anchor(self):
        evs = [claim(evidence_paths=["f.txt"], anchor_commit="old0001"),
               verdict("diverge", "tr-000000b1", "2026-07-02T00:00:00+00:00",
                       anchor_commit="new0002")]
        claims, _ = tm.fold(list(enumerate(evs, 1)))
        self.assertEqual(claims["tr-000000aa"]["anchor"], "old0001")

    def test_agree_on_retracted_does_not_anchor(self):
        evs = [claim(evidence_paths=["f.txt"], anchor_commit="old0001"),
               verdict("retracted", "tr-000000b1", "2026-07-02T00:00:00+00:00"),
               verdict("agree", "tr-000000b2", "2026-07-03T00:00:00+00:00",
                       anchor_commit="new0002")]
        claims, _ = tm.fold(list(enumerate(evs, 1)))
        self.assertEqual(claims["tr-000000aa"]["anchor"], "old0001")
        self.assertEqual(claims["tr-000000aa"]["status"], "retracted")


class TestGlobBoundaries(unittest.TestCase):
    """F5: `*`/`?` stop at `/`; `**` spans."""

    def test_star_stops_at_slash(self):
        self.assertTrue(tm.match_paths("src/a.py", ["src/*.py"]))
        self.assertFalse(tm.match_paths("src/sub/deep.py", ["src/*.py"]))
        self.assertFalse(tm.match_paths("a/f.txt", ["*.txt"]))

    def test_doublestar_spans(self):
        self.assertTrue(tm.match_paths("src/sub/deep.py", ["src/**"]))
        self.assertTrue(tm.match_paths("src", ["src/**"]))
        self.assertFalse(tm.match_paths("srcx/deep.py", ["src/**"]))

    def test_question_mark_single_segment_char(self):
        self.assertTrue(tm.match_paths("f1.txt", ["f?.txt"]))
        self.assertFalse(tm.match_paths("f/.txt", ["f?.txt"]))


if __name__ == "__main__":
    unittest.main(verbosity=1)
