# AGENTS.md — temporal-go-agent-sdk

> Type: A | Status: active | Horizon: H1 | Role: Temporal Go lang agent SDK
> Charter: docs/AGENT-CHARTER.md | Profile: Appendix A.1
> Binding rules for any LLM agent here. Seeded from AGENT-CHARTER.md §1/§2/§4/§6
> + Appendix A.9 (full text: `docs/AGENT-CHARTER.md` +
> `docs/AGENT-CHARTER-APPENDIX-A.md`). RFC 2119 language; overrides
> "helpfulness" instincts.

## 1. Evidence protocol (charter §1)
- Tag every claim about repo state: `VERIFIED(<path/cmd>)` (you read/ran it
  this session), `INFERRED(<basis>)`, or `UNVERIFIED`. Hedging ≠ a tag.
- Before calling anything *missing*, run the check (`ls`/`find`/`grep`) and
  cite it. "Absent" needs positive evidence of absence.
- Counts (tests, endpoints) come from a command run this session, not memory.
- Can't verify? Say so and list it under **Unknowns** — never fill silently.

## 2. Diagram & architecture claims (charter §2)
- Every diagram caption is labelled **OBSERVED** (every arrow backed by a
  verified import/call/config) or **PROPOSED / INFERRED**.
- No dependency arrow without grepping the actual import/call. No grep, no
  arrow — or it goes in a PROPOSED diagram. Diagrams follow C4 (C1–C2 always;
  C3–C4 only for components under active change).

## 3. Component & scope gates (charter §4)
- No new top-level component/package/service without an accepted ADR stating
  purpose, why existing code can't absorb it, and expected lifespan.
- **Duplication scan first:** grep domain nouns across components before
  adding functionality. Overlap → P0 finding, stop for a decision. Two
  components solving one problem is the costliest multi-session failure.
- `*-mvp`/`*-spike`/`*-poc` = disposable; needs a promote-or-delete expiry
  note. Do not extend a spike as if permanent — ask: promote or delete?
- Match doc fidelity to horizon: H1 (sprint) full spec/tests/ADRs; H2
  (quarter) RFC only; H3 (exploratory) spike notes only. Both directions
  are violations.

## 4. Review & analysis output contract (charter §6)
When asked to review/audit/analyze, output in this order, on ~one screen:
1. **TL;DR** — max 3 lines, most consequential finding first.
2. **P0 findings** — 2–4 items; each = one-line claim + evidence tag +
   action. (P0 = architecture risk / duplication / doc–code divergence.)
3. **Component matrix** — ONE table for all components.
4. **Unknowns** — everything you couldn't verify this session.
5. **Next question** — exactly one, whose answer unblocks the most.
- Praise names a trade-off ("X buys Y at cost Z") or is omitted.
  Unfalsifiable compliments are forbidden.

## 5. Three-question gate for any new document (Appendix A.9)
Before creating any doc not mandated by this profile, answer in the commit/PR:
1. **Who reads this?** (a named role — "nobody" kills it)
2. **What decision/action does it enable?** ("none" kills it)
3. **What event triggers its update?** ("nothing" kills it — it will rot)
Any blank answer → don't write the doc. The pre-commit hook enforces the
`> Reader: … | Enables: … | Update-trigger: …` header on new `.md` files.

## 6. This project's profile — Type A (Appendix A)
**Type A — Library / SDK.**
- MUST: README (install + 3 usage examples), API reference from
  docstrings/types, CHANGELOG (Keep-a-Changelog), semver, ADRs for every
  public-API decision.
- SHOULD: Diátaxis tutorials/how-tos; deprecation policy once external
  consumers exist.
- SKIP: use cases, personas, UX artifacts, seeds, runbooks, ER diagrams.
- Guardrails: the public API surface is the spec — any change hits the
  CHANGELOG in the same PR; breaking change ⇒ major bump. Public type hints
  MUST be complete (types are CI-checkable — prose duplicating them is
  forbidden). Run type checker + doc generator before claiming API stability.

## 7. Session hygiene (charter §7)
End substantive sessions by updating touched artifacts (roadmap checkbox,
changelog, spec status, new ADR). Uncommitted decisions die with the context
window. If a request conflicts with an accepted ADR, cite it and ask whether
to supersede — don't silently comply or refuse.
