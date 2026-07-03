# AGENT CHARTER — Documentation, Specification & Scope Discipline

> **Audience:** Any LLM agent (Claude, GPT, Copilot, etc.) working in this repository.
> **Status:** Binding. These rules override stylistic preferences and "helpfulness" instincts.
> **Language:** The key words MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are to be
> interpreted as in RFC 2119.

---

## 0. Prime Directive

You are a contributor to a **commercial-grade** codebase maintained primarily by a solo
developer working with multiple LLM sessions. The greatest systemic risks in this setup are:

1. **Inference dressed as fact** — agents asserting repository state they never verified.
2. **Accidental duplication** — separate sessions creating overlapping components.
3. **Context decay** — taxonomies, decisions, and plans silently lost between sessions.
4. **Scope creep** — fidelity of work not matched to the certainty of the plan.

Every rule below exists to counter one of these four risks.

---

## 1. Evidence Protocol (MUST)

1.1. Every factual claim about repository state MUST be tagged with its evidence class:
  - `VERIFIED(<path or command>)` — you read the file or ran the command in this session.
  - `INFERRED(<basis>)` — a plausible conclusion from indirect evidence. State the basis.
  - `UNVERIFIED` — recalled from prior context, training, or assumption.

1.2. You MUST NOT present INFERRED or UNVERIFIED content in the same voice as VERIFIED
content. Hedged phrasing ("appears to", "likely") does NOT substitute for the tag.

1.3. Before claiming a file, test, dependency, or config is *missing*, you MUST run the
check (`ls`, `find`, `grep`) and cite it. "Absent" claims require positive evidence
of absence.

1.4. Counts (tests, endpoints, modules) MUST come from a command executed this session,
never from memory of an earlier session.

1.5. If verification is impossible (file too large, tool unavailable), say so explicitly
and list the claim under an **Unknowns** section. Never fill the gap silently.

---

## 2. Diagram & Architecture Claims (MUST)

2.1. Every architecture diagram MUST carry one of two labels in its caption:
  - **OBSERVED** — every arrow backed by a verified import, call, or config reference.
  - **PROPOSED / INFERRED** — a hypothesis or design intent, not current reality.

2.2. Before drawing a dependency arrow between components, you MUST grep for the actual
import or API call (e.g. `grep -r "import <pkg>" <component>/`). No grep, no arrow —
or the arrow goes in a PROPOSED diagram.

2.3. Diagrams follow the **C4 model**. Maintain C1–C2 for the whole system; C3–C4 only
for components under active change. Do not gold-plate diagrams for dormant code.

---

## 3. Context Re-Anchoring (MUST)

3.1. You MUST NOT reference labels, taxonomies, or shorthand from prior sessions or
compacted context ("Type A", "the plan we agreed") without restating their definition
inline or linking to the repo file that defines them.

3.2. If a definition exists nowhere in the repo, your first action is to write it down
(as an ADR, glossary entry, or spec section) — then use it.

3.3. At the start of any non-trivial task, read in this order before acting:
  1. `ROADMAP.md` (current intent)
  2. `ARCHITECTURE.md` and/or C1–C2 diagrams (current shape)
  3. `docs/decisions/` — ADR index (constraints already decided)
  4. The spec in `specs/` linked from the roadmap item you are working on

3.4. If any of those files is stale or contradicts the code, flag the divergence as a
finding BEFORE doing the requested work. Divergence between docs and code is itself
a P1 defect.

---

## 4. Component & Scope Gates (MUST)

4.1. You MUST NOT create a new top-level component, package, or service without an
accepted ADR that states: purpose, why existing components cannot absorb it, and its
expected lifespan.

4.2. Before adding functionality, run a **duplication scan**: search for existing code
that solves the same domain problem (`grep` for domain nouns across components).
If overlap exists, surface it as a P0 finding and stop for a decision. Two components
solving one problem is the single most expensive failure mode of multi-session
LLM development.

4.3. Naming encodes lifecycle:
  - `*-mvp`, `*-spike`, `*-poc` suffixes mean **disposable**. Such components MUST have
    an expiry note in their README ("promote or delete by <date/milestone>").
  - An agent MUST NOT extend a spike as if it were permanent. Ask: promote or delete?

4.4. Match documentation fidelity to planning horizon:

| Horizon | Certainty | Required artifacts |
|---------|-----------|--------------------|
| H1 — current sprint | High | Full spec, tests, ADRs, changelog entry |
| H2 — next quarter | Medium | RFC / lightweight spec only |
| H3 — exploratory | Low | Spike notes only |

  Writing full specs for H3 work, or skipping specs for H1 work, are both violations.

---

## 5. Artifact Contract (MUST)

5.1. Canonical layout — docs live next to code, reviewed in the same PR:

```
repo/
├── src/  tests/
├── docs/
│   ├── architecture/     # C4 diagrams (Structurizr DSL or Mermaid, in-repo)
│   ├── decisions/        # ADR-NNNN-*.md — numbered, immutable
│   └── glossary.md       # definitions of taxonomies and domain terms
├── specs/                # living specifications, one per feature
├── ROADMAP.md            # checkbox syntax; links to specs + ADRs
├── CHANGELOG.md          # Keep-a-Changelog format
└── ARCHITECTURE.md       # C1/C2 narrative
```

5.2. ADR rules:
  - Accepted ADRs are **immutable**. To change a decision, write a superseding ADR.
  - One page max. Sections: Status, Context, Decision, Consequences, Supersedes.
  - Code and specs reference decisions by number (`ADR-0017`).

5.3. Every behavior-changing code change MUST answer, in the PR/commit description:
"Which spec, ADR, or roadmap item does this trace to, and which doc did I update?"
"None needed" is an acceptable answer only when stated explicitly.

5.4. The **Spec–Code–Test triangle**: every H1 feature has all three legs, linked.
Prefer executable specs (contract tests, architecture tests, Gherkin) over prose —
a spec that cannot fail CI is decoration.

5.5. Documentation follows **Diátaxis**: classify every doc as tutorial, how-to,
reference, or explanation. Do not write hybrid documents.

---

## 6. Review & Analysis Output Contract (MUST)

When asked to review, audit, or analyze the repository, your output MUST follow this
shape — in this order, with these size limits:

1. **TL;DR** — max 3 lines. The most consequential finding first.
2. **P0 findings** — 2–4 items. Each: one-line claim + evidence tag + concrete action.
   (P0 = architectural risk / duplication / doc–code divergence. P1 = quality gap.
   P2 = polish.)
3. **Component matrix** — ONE table for all components, not one table per component.
4. **Unknowns** — explicit list of everything you could not verify this session.
5. **Next question** — exactly one focused question whose answer unblocks the most.

6.1. Total length SHOULD fit on one screen; details go to an appendix only on request.
6.2. Praise MUST name a trade-off ("X gives you Y at the cost of Z") or be omitted.
Unfalsifiable compliments ("brilliant", "rare for solo devs") are forbidden — they
consume trust and signal nothing.
6.3. Recommendations MUST be specific to this repo's observed pain points. If a
recommendation would apply to any repository, cut it or ground it in a finding.

---

## 7. Session Hygiene (SHOULD)

7.1. End every substantive session by updating the artifacts your work touched:
roadmap checkbox, changelog entry, spec status, new ADR if a decision was made.
Uncommitted decisions die with the context window.

7.2. When you make a non-trivial judgment call mid-task, record it — a one-line ADR
stub is better than a decision that exists only in chat history.

7.3. If the user's request conflicts with an accepted ADR, do not silently comply or
silently refuse: cite the ADR, state the conflict, and ask whether to supersede it.

---

## 8. Forbidden Behaviors (MUST NOT)

- MUST NOT state repository facts without an evidence tag (§1).
- MUST NOT draw dependency arrows without a verified import/call (§2.2).
- MUST NOT use prior-session taxonomies without restating them (§3.1).
- MUST NOT create components without an ADR (§4.1).
- MUST NOT extend `*-mvp`/`*-spike` code without a promote-or-delete decision (§4.3).
- MUST NOT edit an accepted ADR (§5.2).
- MUST NOT pad reviews with per-component boilerplate tables or unranked findings (§6).
- MUST NOT offer praise without a named trade-off (§6.2).
- MUST NOT leave a session's decisions unrecorded in the repo (§7).

---

## 9. Escape Hatch

If following this charter would block genuinely urgent work (production incident,
data loss), do the minimum safe action, then write a retroactive ADR titled
`ADR-NNNN: Emergency deviation — <what and why>` in the same session.

*This charter is itself governed by §5.2: change it via a superseding ADR, not by edit.*
