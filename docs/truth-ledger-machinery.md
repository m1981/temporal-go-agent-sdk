# The Truth Ledger, Illustrated

> Reader: anyone being introduced to the truth ledger (presentation audience, new collaborator) | Enables: understanding the machinery well enough to trust its gates and file claims/issues correctly | Update-trigger: a consumed template version changes fold semantics, gates, or verbs

Presentation-friendly diagrams of how the truth ledger works. Source of
truth for semantics: `.truth/README.md` and the ADRs in `docs/adr/truth/`.
GitHub renders these natively; for slides, paste each block into any
mermaid renderer (e.g. mermaid.live).

---

## 1. The big picture — one file, derived truth

Everything — verified facts *and* work items — is an append-only line in
`.truth/claims.jsonl`. Nothing stores a status; status is **recomputed**
every time by replaying all events in order (the "fold"). You can never
edit history, only append to it.

```mermaid
flowchart TB
    subgraph inputs ["You append events"]
        C["claim<br/><i>'a verified fact'</i>"]
        V["verdict<br/><i>'a second opinion'</i>"]
        I["issue / issue_event<br/><i>'work to do'</i>"]
    end

    L[("claims.jsonl<br/>append-only log")]
    F["fold<br/><i>replay everything,<br/>derive status</i>"]

    C --> L
    V --> L
    I --> L
    L --> F

    subgraph outputs ["Derived views (never stored)"]
        S1["truth list --live<br/><i>facts you may rely on</i>"]
        S2["truth ready<br/><i>work you may start</i>"]
        S3["truth queue / doctor<br/><i>what needs attention</i>"]
    end

    F --> S1
    F --> S2
    F --> S3
```

**Why it matters:** there is no field an agent (or human) can quietly
flip to "done" or "true". The only way to change a status is to append a
new, attributable, gate-checked event.

---

## 2. Life of a fact — how a claim stays honest

A claim is born with an **evidence command** (how to re-check it) and
either **paths** (repo facts) or a **TTL** (world facts). It is born
**unverified**: filing runs and hashes the evidence twice, but that
double-run is a gate, not a verdict — only an independent session's
`agree` makes it *live*. Evidence attached and evidence confirmed are
two distinct events, never conflated. The repo itself stales it: any
commit touching its paths knocks it back to *stale* until someone
re-verifies.

```mermaid
stateDiagram-v2
    [*] --> Unverified : truth claim (intake gates pass)

    Unverified --> Live : verdict agree (independent session)
    Unverified --> Stale : commit touches paths, or TTL expires
    Unverified --> CannotVerify : verdict cannot_verify

    Live --> Stale : commit touches paths, or TTL expires
    Live --> Diverged : verdict diverge (re-run said otherwise)
    Live --> CannotVerify : verdict cannot_verify (queued if P0)
    Live --> Live : verdict agree (anchor advances)

    Stale --> Live : re-verified (agree)
    Diverged --> Live : verdict agree (dispute resolved)
    CannotVerify --> Live : evidence fixed, then agree

    Live --> Retracted : human-gated tombstone (typed id)
    Stale --> Retracted : human-gated tombstone
    Retracted --> [*]

    note right of Live
        Intake gates (refusal, not warning):
        empty text, near-duplicate,
        quantifier/scope mismatch (ADR-007),
        unsafe evidence command (ADR-009)
    end note

    note right of Diverged
        diverge --mechanical (ADR-012):
        the measuring recipe changed,
        not necessarily the fact
    end note
```

**Why it matters:** facts decay automatically. Nobody has to remember
to distrust old knowledge — the ledger forgets *for* you, loudly.

### Filing hygiene & aftermath — rules earned in consumer production

**The tail-variation rule (2026-07-27):** claim
families filed as a batch (symbol pins, sentinel pairs) must vary their
texts beyond the distinguishing token — a shared boilerplate tail can
push two sibling claims over the ADR-018 near-duplicate threshold and
the gate refuses the batch midway (observed at jaccard 0.617 on the
door_width × drawer_front_width pin pair before their tails were
diversified).

**Pre-scan batch texts mechanically:** before filing a claim family,
run the CLI's own quantifier and jaccard functions over every text —
don't eyeball it. ADR-007 matches PHRASES as well as tokens ("the
project" fires even through an apostrophe), and the ADR-018 threshold
is measured against the *active* claim set, not guessed against the
sibling you happen to be looking at.

**Retraction citation sweep:** before recommending or executing a
retraction, grep the whole corpus — specs, docs, use-cases — for the
id. A retracted id cited by any spec blocks every spec commit via the
health gate; swap the citations to the successor claim FIRST, then
retract.

**The doc↔claim two-commit dance:** when a doc must cite a claim that
in turn watches that doc, commit the doc citing the claim by TITLE
first, file the claim (its paths are now tracked), then a second
commit swaps the title for the id. Filing before the content commit is
either refused (INV-M) or restales at birth.

**Version-pin divergences are genuine:** when a pinned version string
is superseded by a release, the FACT changed, not the measuring recipe
— diverge without `--mechanical`, and file a successor claim pinned to
the new version.

**Copier-managed files:** a consumer-local edit to a template-managed
file must be upstreamed into the template at the next release, or the
next `copier update` conflicts on it. The tail-variation rule above
took exactly that path — earned in a consumer, promoted here.

**Batch execution hygiene:** file claim batches through argv-array
drivers, never shell-interpolated loops — shell echo can rewrite
backslash escapes inside evidence commands. And after a union-merge
pull, commit the reaffirm agrees before pushing.

### The authoring loop — who does what, in which order

The ledger's refusals assume a division of labor. The shape that has
held up in consumer production (dozens of feature and release cycles)
uses four roles — human, agent, or a mix; the roles matter, not the
runner:

1. **An implementing worker**, fresh context, writes the code, tests,
   and docs. It never commits and never writes the ledger — its output
   is a working tree and a report.
2. **An adversarial reviewer**, fresh context, attacks the change
   BEFORE anything is committed — the ledger and every append-only
   record forgive nothing after. Arm it with the CLI's own gate
   functions (quantifier, jaccard, screen) and let it run two-state
   tests on scratch copies, never on the tree.
3. **An orchestrator** alone re-runs the suites, commits the CONTENT
   first (INV-M refuses untracked watch paths, and a claim filed
   before its watched content lands restales at birth), then files
   the claims, then runs scan and reaffirm in a fresh session.
4. **Verifiers**, one per dispatch, never the author (the ADR-010
   refusal is structural, but the habit matters more than the gate).
   They parallelize safely — ledger appends are single-write.

Close with a separate `ledger:` commit, pull before push. Two triggers
are not optional: an adversarial review for every feature or release
(each one in production has caught something the suites did not), and
a verifier dispatch IMMEDIATELY for freshly filed claims — reaffirm
skips the never-agreed, so an unverified claim's first restale bricks
it. Mismatches always go to a dispatch judgment, never batch-agreed.

---

## 3. Life of a work item — planning that stands on facts

Work items live in the same ledger. Each one can declare the facts it
**stands on** (`--premise`). If a premise dies, the work is HELD — the
plan invalidates itself the moment its factual basis does.

```mermaid
flowchart LR
    A["truth issue 'title'<br/>--deps wk-a,wk-b<br/>--premise tr-x"]
    B{"truth ready"}
    C["truth start wk-…<br/><i>claim it</i>"]
    D["do the work"]
    E["truth done wk-…<br/>--claim '&lt;new fact&gt;'"]
    F["closed <b>and</b> the resulting<br/>fact is filed — atomic,<br/>both-or-neither"]
    H["HELD<br/><i>premise stale/diverged —<br/>re-verify the fact, or redirect<br/>the premise (ADR-013)</i>"]

    A --> B
    B -->|"deps done + premises live"| C
    B -->|"a premise died"| H
    H -.->|"fact re-verified, or truth premise<br/>--supersedes to its corrected claim"| B
    C --> D
    D --> E
    E --> F
```

**Why it matters:** an agent will happily execute a plan whose factual
basis died three sessions ago. Humans notice; models don't. The premise
gate makes that impossible by construction.

---

## 4. The ready gate — what "you may start this" actually checks

```mermaid
flowchart TB
    Q["work item wk-…"] --> O{"open?<br/>(not closed/cancelled)"}
    O -->|no| X1["not shown"]
    O -->|yes| D{"all --deps<br/>closed?"}
    D -->|no| X2["blocked<br/><i>waits for dependency</i>"]
    D -->|yes| P{"premises pass the<br/>ADR-001 matrix?"}
    P -->|"stale / diverged /<br/>retracted / missing"| X3["HELD<br/><i>shown with the dead fact named</i>"]
    P -->|"cannot_verify on a<br/>P0 premise"| X3
    P -->|"live — or unverified /<br/>non-P0 cannot_verify<br/>(pass WITH a warning)"| R["READY ✅"]

    style R stroke-width:3px
    style X3 stroke-dasharray: 5 5
```

The premise check is a tier-sensitive **matrix** (ADR-001), not a
binary: `live` passes clean; `unverified` passes with a warning (low
filing friction is a stated trade); `cannot_verify` blocks only P0
premises and warns otherwise; `stale`, `diverged`, `retracted`, and
missing claims always block.

The same gate works with an external tracker (Beads via adapter, or any
command printing `[{id,title}]` JSON) — the ledger contributes the
premise filter either way (ADR-004 seam; the source precedence is the
next diagram).

---

## 5. Where the work comes from — one join, four sources

`truth ready` doesn't care who the tracker is. Sources resolve in a
fixed precedence order (ADR-002), and the **premise join is applied
identically to whichever source won** — which is what makes the seam
and the kernel incapable of disagreeing.

```mermaid
flowchart TB
    R["truth ready"] --> S1{"--stdin piped?"}
    S1 -->|yes| J["ADR-001 premise join<br/><i>same join, every source</i>"]
    S1 -->|no| S2{"TRUTH_TRACKER_CMD<br/>set?"}
    S2 -->|yes| J
    S2 -->|no| S3{"ledger holds<br/>issue records?"}
    S3 -->|"yes — native<br/>work kernel"| J
    S3 -->|"no"| S4["bd ready --json<br/>(Beads default)"] --> J
    J --> OUT["READY / HELD"]

    K["truth issues --ready-json"] -.->|"emits the same adapter contract:<br/>the kernel is itself a tracker source,<br/>so seam and kernel cannot diverge"| S1

    style J stroke-width:3px
```

**Why it matters:** the ledger stands alone with no tracker, joins any
tracker that can print `[{id,title}]` JSON, and — because the native
kernel speaks the same contract through `issues --ready-json` — the
adapter seam can be tested against the kernel itself. A missing or
failing tracker degrades with guidance, never a traceback.

---

## 6. Two branches, one truth — union-merge confluence

Ledgers on diverged branches merge by **union** (`.gitattributes`:
`merge=union`), and the fold replays events in a canonical
`(timestamp, id)` total order — *not* file order. So both merge
directions derive identical status.

```mermaid
flowchart TB
    subgraph A["branch A appends"]
        A1["claim tr-x (ts=10:00)"]
    end
    subgraph B["branch B appends"]
        B1["verdict agree tr-x (ts=10:05)"]
    end

    A -->|"merge A←B"| M1[("file order 1:<br/>claim, verdict")]
    B -->|"merge B←A"| M2[("file order 2:<br/>verdict, claim")]

    M1 --> F["fold: sort by (ts, id),<br/>then replay"]
    M2 --> F
    F --> S["tr-x: live —<br/>identical either direction ✅"]
```

Three per-field merge disciplines make this safe (paper §6.3), each an
audit scar: claim **content** is first-writer-wins — a duplicate id
can never substitute text or evidence (F6); **status** is
last-writer-wins in `(ts, id)` order (F3); **retraction** is terminal
— a tombstone can never be resurrected by a later append (G12). A
backdated duplicate id that tries to game the sort is detected at
commit (ADR-008), because within one history, file order is append
order.

**Why it matters:** agents on parallel branches never coordinate, and
nobody resolves ledger merge conflicts — convergence is a property of
the fold, not a procedure for the humans.

---

## 7. The immune system — who guards the guards

The machinery distrusts itself. Every safety property is either
executed regularly or was converted from a norm ("please don't")
into syntax ("the CLI refuses").

```mermaid
flowchart TB
    subgraph continuous ["Every commit / merge"]
        H1["pre-commit: check-truth.sh<br/><i>schema + fold sanity</i>"]
        H2["post-merge: invalidate-scan<br/><i>stale claims whose paths changed</i>"]
    end

    subgraph battery ["On demand + weekly CI"]
        G1["canary: seeded faults<br/><i>each must be CAUGHT or the<br/>run fails — it prints its own count</i>"]
        G2["core + conformance suite<br/><i>drift detector ARMED</i>"]
        G3["truth doctor<br/><i>hooks wired? snippet present?<br/>queue aging?</i>"]
    end

    subgraph syntax ["Norms made refusals"]
        N1["filer ≠ verifier<br/>(session separation, ADR-010)"]
        N2["backdating detected<br/>(order coherence, ADR-008)"]
        N3["evidence commands screened<br/>read-only allowlist (ADR-009)"]
        N4["tombstones need a human<br/>+ typed id (ADR-011)"]
    end

    continuous --> LGR[("claims.jsonl")]
    battery -->|"attacks a scratch copy,<br/>never your data"| LGR
    syntax -->|"enforced at intake,<br/>not reviewed after"| LGR
```

**Why it matters:** a safety check whose failure mode is a print
statement is a norm, not a property. Here, failing checks *stop the
machine*.

---

## 8. Proposed next: `--accept-cmd` — "done" must be demonstrable

Filed upstream as
[truth-ledger#1](https://github.com/m1981/truth-ledger/issues/1):
today `done` takes the agent's word; with an acceptance command declared
at birth, `done` refuses until the finish line actually passes.

```mermaid
flowchart LR
    A["truth issue<br/>--premise tr-x<br/>--accept-cmd C"] --> B{"truth ready"}
    B -->|"deps done + premises live"| C["truth start"]
    C --> D["work happens"]
    D --> E{"truth done --claim"}
    E -->|"C exits 0"| F["closed + fact filed<br/>(atomic)"]
    E -->|"C fails"| D
```

Born on live facts (premise-at-birth), dies into a verifiable fact
(accept-cmd + claim-at-death). The loop closes.
