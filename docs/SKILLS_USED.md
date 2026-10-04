# Skills Used — Paste-to-Product

## Skill → Task Mapping (initial)

| Skill | Task Part | When |
|-------|-----------|------|
| **using-superpowers** | Session boot — ensure all skills are discovered and invoked before work begins | Start |
| **brainstorming** | Requirements already provided in the build brief; brief treated as the approved spec | Start (brief IS the spec) |
| **writing-plans** | Architecture, stack, data model, agent design, SerpApi engine selection, phased build order → `docs/PLAN.md` | Before any code |
| **executing-plans** | Implement the plan task-by-task with checkpoints | Build phase |
| **subagent-driven-development** | Dispatch fresh implementer subagents per task if parallelism helps | Build phase |
| **test-driven-development** | Parser contract tests, verifier tests, cache tests, compare-flow tests | Every feature |
| **systematic-debugging** | Any bug, test failure, or unexpected SerpApi response during build | As needed |
| **verification-before-completion** | Confirm each phase works before moving on; evidence before claims | Every milestone |
| **requesting-code-review** | Final code review before submission | End |
| **receiving-code-review** | Handle review feedback with technical rigor | End |
| **finishing-a-development-branch** | Merge, tag, deploy | End |
| **dispatching-parallel-agents** | Independent tasks within the build (e.g., eval harness + UI work) | Build phase |
| **using-git-worktrees** | Isolated workspace for feature work | Build phase |
| **ponytail** | Keep solutions minimal — YAGNI, stdlib first, no over-engineering | Always |
| **ponytail-review** | Post-build review for over-engineering | End |

## Skill → Task Mapping (Parser & SSE Fix)

| Skill | Task Part |
|-------|-----------|
| **writing-plans** | Analyze root causes, define test cases, and create an execution plan for both fixes. |
| **test-driven-development** | Write regression tests for parser prompt (section 1) and stream robustness (section 2) before fixing. |
| **ui-ux-pro-max** | Design unobtrusive UI for `origin` field and handle error/retry states for SSE drops. |
| **systematic-debugging** | Used during any unexpected test failures while resolving stream boundary issues. |

## Missing Skills

| Need | Gap |
|------|-----|
| UI/UX design skill | No dedicated UI/UX skill exists; will use brainstorming + web design best practices from system prompt |
| Evaluation/benchmarking skill | No eval-specific skill; will build bespoke eval harness |

## Actual Usage (Parser & SSE Fix — 2026-10-03)

| Skill | Used For | Notes |
|-------|----------|-------|
| **using-superpowers** | Session boot | Read skill, confirmed all relevant skills |
| **systematic-debugging** | Root cause analysis | Confirmed both bugs from code reading; documented real causes vs. reported causes |
| **writing-plans** | Created detailed implementation plan | Saved to brain artifacts; 7 tasks with bite-sized steps |
| **executing-plans** | Implemented plan in-session | All 7 tasks completed without blockers |
| **test-driven-development** | Parser regression suite + SSE reliability suite | Tests written before/alongside implementation; all watched to fail first via mocked responses |
| **ui-ux-pro-max** | Origin badge design + warning banner | Chose subtle amber palette; "suggested" micro-badge on parsed tags; full-width warning banner |

## Missing Skills (still missing)

| Need | Gap |
|------|-----|
| End-to-end browser test | No Playwright/Cypress skill; e2e test for the interview chat paste is manual-only |

---

## Skill → Task Mapping (Audience Selector + Offline Brand Logic + 50 km Radius)

| Skill | Task Part | When |
|-------|-----------|------|
| **writing-plans** | Architecture for gender flow, brand-selection logic, radius enforcement → `docs/PLAN_AUDIENCE_AND_RADIUS.md` | Before any code |
| **brainstorming** | Brief treated as approved spec (same as D11); skip interactive Q&A | Start (brief IS the spec) |
| **subagent-driven-development** | Dispatch fresh subagent per task from the implementation plan | Build phase |
| **test-driven-development** | Selector tests, audience propagation tests, brand-logic tests, radius tests, regression suite | Every feature |
| **ui-ux-pro-max** | Selector component, disabled-search state, no-store empty map state, brand-source note | UI tasks |
| **systematic-debugging** | Any unexpected SerpApi field shapes, coordinate absence patterns, brand extraction failures | As needed |
| **verification-before-completion** | Confirm each change works before claiming done | Every milestone |
| **requesting-code-review** | Final code review after all three changes | End |
| **ponytail** | Keep brand-logic, radius filter, and audience threading minimal | Always |

## Actual Usage (Audience + Brand Logic + Radius — 2026-10-03)

*(To be filled in as work completes)*

| Skill | Used For | Notes |
|-------|----------|-------|
