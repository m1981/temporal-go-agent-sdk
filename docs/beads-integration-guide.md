# Beads + Truth Ledger — Agent Operating Guide

> **Reader:** an AI coding agent (or the human wiring one up) working in a repo that has the truth ledger and wants to use **Beads** as the work tracker behind `truth ready`.
> **Enables:** installing Beads, connecting it to the ledger through the adapter seam, and running the correct claim→verify→work loop.
> **Update-trigger:** the Beads CLI surface changes, or `scripts/truth`'s `ready` contract changes.

---

## 0. Sourcing note (read once)

The Beads facts below are taken from the official repository **`github.com/gastownhall/beads`** (npm package `@beads/bd`, binary `bd`), verified at authoring time. Beads is young and moves fast, and this guide was written against knowledge current to early 2026 — **before running any `bd` command whose flags you are unsure of, run `bd --help` or `bd <cmd> --help` and trust that over this document.** The integration is deliberately built so that the *exact* JSON field names Beads emits do not matter (see §3), precisely because they may change.

The two tools are complementary and must not be confused:

| | **Beads (`bd`)** | **Truth ledger (`scripts/truth`)** |
|---|---|---|
| Answers | *What should I work on?* | *What do we know, and does it still hold?* |
| Stores | Issues, dependencies, status | Claims, evidence, verdicts |
| Backed by | Dolt (versioned SQL) | Append-only JSONL |
| Relationship | **read-only** from the ledger (contract E1) | consumes `bd ready` as input to `truth ready` |

The ledger never writes to Beads. The only bridge is one-directional: `truth ready` *reads* Beads' ready-issue list and filters it by premise validity.

---

## 1. Install and initialize Beads

Beads ships as a single CLI. Install it **system-wide — do not clone the Beads repo into your project.**

```bash
npm install -g @beads/bd        # Node.js; see the repo's INSTALLING.md for other methods
```

Then initialize it inside your project (the repo that already has the truth ledger):

```bash
cd your-project
bd init                         # creates .beads/, sets up storage, writes/updates AGENTS.md
```

Notes verified from the official docs:
- `bd init` **creates or updates `AGENTS.md`** with Beads' own agent instructions, and installs IDE/agent integrations unless you pass `--skip-agents` or `--stealth`. Your repo already has a truth-ledger snippet in `AGENTS.md`; Beads appends rather than clobbers, but **read the file afterward and confirm both snippets are present.**
- `bd init --stealth` uses Beads locally without committing its files — useful on shared repos where you don't want to add Beads to everyone's history.
- Storage is Dolt-backed. `.beads/issues.jsonl` is an **export** of the issue table, not the source of truth — don't hand-edit it.

Confirm it works:

```bash
bd ready --json                 # should print a JSON array (possibly empty) and exit 0
```

If that command errors, fix Beads before wiring the ledger — the ledger will degrade gracefully but you won't get the `ready` gate.

---

## 2. Wire Beads to the truth ledger

`truth ready` resolves its work list from, in precedence order: `--stdin`, then the `TRUTH_TRACKER_CMD` environment variable, then the default `bd ready --json`. You have two good options.

### Option A — direct (simplest; use if `bd ready --json` already emits `{id, title}` objects)

Nothing to configure. The default path calls `bd ready --json` for you:

```bash
scripts/truth ready
```

### Option B — through the bundled adapter (recommended; robust to Beads' JSON shape)

The repo ships `scripts/truth-bd-adapter.sh`, which normalizes whatever Beads emits down to the exact `[{"id","title"}]` array the join needs, and **fails loudly** if it can't find an id (rather than silently joining against nothing — which would let work proceed on unchecked premises). Wire it once:

```bash
export TRUTH_TRACKER_CMD="bash scripts/truth-bd-adapter.sh"
scripts/truth ready
```

Make it durable by adding that `export` to your shell profile or your agent runtime's environment. Or pipe explicitly:

```bash
bash scripts/truth-bd-adapter.sh | scripts/truth ready --stdin
```

**Which to choose:** start with A; if `truth ready` shows no issues when `bd ready` clearly returns some, Beads is using field names the direct path doesn't expect — switch to B, which recognizes `id`/`issue_id`/`key`/… and `title`/`summary`/`name`/….

---

## 3. What the join actually requires (the contract)

`truth ready` keys on exactly two fields per issue and ignores everything else:

- **`id`** — must match the id you used in `truth premise <id> <claim>`. For Beads this is the hash-based id like `bd-a1b2` (or hierarchical `bd-a3f8.1`).
- **`title`** — display only; falls back to the id if absent.

This is why the integration survives Beads changing its schema: the ledger never depended on Beads' full issue shape, only on an id it can match against premise links. **Do not "enrich" the adapter to pass more fields through — the join uses none of them, and a wider contract is a wider thing to break.**

---

## 4. The agent loop: claim → verify → work → close

This is the combined workflow. Beads verbs are from its official essential-commands table; ledger verbs are from `scripts/truth`.

**Step 1 — Find safe work.** Never start from `bd ready` alone; start from `truth ready`, which is `bd ready` minus anything standing on a broken premise:

```bash
scripts/truth ready
# lists ready issues; prints "HELD <id> broken premises: …" for issues you must NOT start
```

If an issue you need is HELD, its premise is `stale`/`diverged`/`retracted`/missing. Resolve the premise first (re-verify it, §Step 3) — do not work around the hold.

**Step 2 — Claim the Beads issue** (Beads-side bookkeeping: assign + mark in-progress):

```bash
bd update bd-a1b2 --claim
```

**Step 3 — Do the work. Whenever you establish a repository fact, file it in the ledger** — this is the whole point of the pairing:

```bash
# before relying on an existing fact:
scripts/truth list --live

# when YOU verify something with a command:
scripts/truth claim "auth middleware rejects expired tokens" \
  --class VERIFIED --evidence-cmd "pytest tests/auth -k expired -q" \
  --paths "src/auth/**" --tier P1

# reasoned, not directly run:  --class INFERRED --basis "…"
# just flagging for later:      --class UNVERIFIED
```

**Step 4 — Link facts your work depends on** so future work is protected:

```bash
scripts/truth premise bd-a1b2 tr-1234abcd
```

Now if a later commit touches `src/auth/**`, the ledger marks that claim `stale`, and `truth ready` will HOLD any issue premised on it until someone re-verifies.

**Step 5 — Close the Beads issue** when done:

```bash
bd close bd-a1b2 "expired-token rejection verified and covered by tests"
```

**Step 6 — Keep the ledger honest.** Before trusting a stale claim again, re-verify it. Run the mechanical recheck first:

```bash
scripts/truth verdict tr-1234abcd --recheck
```

Recheck semantics (TL-4): the **negative** outcomes are filed automatically because they are mechanical facts (hash mismatch → `diverge`; command not found → `cannot_verify`) — do not file a duplicate. A **matching** hash is only *reported*, never filed: it proves the command still produces that output, not that the claim's text is a sound interpretation of it. After you have independently confirmed the text, file your judgment once (this also advances the claim's anchor so it stays live):

```bash
scripts/truth verdict tr-1234abcd agree --basis "re-ran the auth suite at HEAD, still passing"
```

Retraction (killing a claim permanently) is a **human** action and requires `TRUTH_HUMAN=1`; as an agent, if you believe a claim should die, file `diverge` with your reasoning and let the human queue decide.

---

## 5. Daily / hygiene commands

| When | Command | Why |
|---|---|---|
| Before starting any work | `scripts/truth ready` | Beads' ready list, minus broken-premise work |
| Before trusting any repo fact | `scripts/truth list --live` | is it still believed? |
| Daily (~2 min) | `scripts/truth queue` | diverged / stale-P0P1 / unverifiable-P0 needing a human |
| After a merge | (post-merge hook runs `invalidate-scan`) | facts whose evidence changed go stale automatically |
| Sync Beads across machines | `bd dolt push` / `bd dolt pull` | Beads' own sync; unrelated to the ledger |

---

## 6. Failure modes and what they mean

- **`truth ready` says "tracker command failed … exit 127"** → `bd` isn't installed or isn't on PATH. Install it (§1), or run the ledger standalone (`truth queue`, `truth list --live`) until you do.
- **`truth ready` returns nothing but `bd ready` returns issues** → JSON-shape mismatch on the direct path; switch to the adapter (§2 Option B).
- **`truth-bd-adapter.sh` exits with "none had an id field this adapter recognizes"** → Beads changed its id field name; add the new key to `ID_KEYS` at the top of the adapter and report it. **Do not** patch the ledger itself.
- **An issue is HELD and you think it shouldn't be** → check the named broken premise with `scripts/truth list` and re-verify it on the record; the hold is the system refusing to let work proceed on a fact nobody re-checked since the ground moved. That is working as designed.

---

## 7. The one rule that matters most

Beads tells you what is *ready*. The ledger tells you what is *still true*. **Work only where both agree** — that intersection is `truth ready`, and it is the entire reason to run the two together. If you find yourself reaching past a HOLD to start held work, stop: you are about to do exactly the thing this pairing exists to prevent.
