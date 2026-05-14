---
description: Write a story-driven direct-response video ad script using the Coursiv microdrama architecture (HOOK → JOLT → MENTOR-CONFESSION → CTA). Runs a 24-question intake Q&A before generating the script. Different from /microdramaideas (registry) and /microdrama-scriptwriter (serialized IP).
argument-hint: [brand name or short brief] (optional — kicks off the Q&A pre-filled with that context)
---

User invoked /brandedmicrodramascript. Args: `$ARGUMENTS`

## Action

Load the `brandedmicrodramascript` skill from `~/.claude/skills/brandedmicrodramascript/SKILL.md` and follow its workflow.

If `$ARGUMENTS` is non-empty, treat it as a kickoff seed — name the brand, draft any answers you can infer, then run the rest of the Q&A on the gaps.

If `$ARGUMENTS` is empty, run the full intake from Q1.

## Quick reference

The skill produces ONE 60s–3:30 vertical or landscape ad script per invocation. Architecture:

```
9 beats × time %    Characters     Intake Q&A
─────────────────   ───────────    ──────────
HOOK (0-7%)         Protagonist    A. Product (Q1-3)
CONTEXT (7-15%)     Threat         B. Buyer (Q4-11)
JOLT 1 (15-30%)     Witness        C. Mentor (Q12-16)
RECKONING (30-45%)  Mentor         D. CTA (Q17-19)
MENTOR (45-55%)     Gatekeeper     E. Style (Q20-24)
CONFESSION (55-65%) (Viewer)
TRANSFORM (65-75%)
PAYOFF (75-90%)
CTA (90-100%)
```

## Trigger discipline

- Branded DR ad / VSL / Coursiv-style → THIS skill
- Original-IP serialized microdrama → `/microdrama-scriptwriter`
- Per-shot production docs → `/microdrama-shotlist`
- Static carousel posts → `/post-shotlist`
- Concept idea registry pull → `/microdramaideas`

## Output

Vertical-ready screenplay with all 9 beats, character notes, and product-integration callouts. Ready to hand to a production team or atomize via `/microdrama-shotlist`.
