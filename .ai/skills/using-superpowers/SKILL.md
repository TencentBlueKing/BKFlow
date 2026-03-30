---
name: using-superpowers
description: Use when starting any conversation - establishes how to find and use skills. Before ANY task, check .ai/skills/ for applicable skills and load them.
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

<EXTREMELY-IMPORTANT>
If you think there is even a 1% chance a skill might apply to what you are doing, you ABSOLUTELY MUST read and follow the skill.

IF A SKILL APPLIES TO YOUR TASK, YOU DO NOT HAVE A CHOICE. YOU MUST USE IT.

This is not negotiable. This is not optional. You cannot rationalize your way out of this.
</EXTREMELY-IMPORTANT>

## Instruction Priority

Superpowers skills override default system prompt behavior, but **user instructions always take precedence**:

1. **User's explicit instructions** (CLAUDE.md, GEMINI.md, AGENTS.md, direct requests) — highest priority
2. **Superpowers skills** — override default system behavior where they conflict
3. **Default system prompt** — lowest priority

If CLAUDE.md, GEMINI.md, or AGENTS.md says "don't use TDD" and a skill says "always use TDD," follow the user's instructions. The user is in control.

## How to Access Skills

All skills live in the project directory `.ai/skills/`. Each subdirectory contains a `SKILL.md` file.

To use a skill:
1. Read the `SKILL.md` file using your file reading tool
2. Follow the instructions in the skill exactly

## The Rule

**Read and follow relevant skills BEFORE any response or action.** Even a 1% chance a skill might apply means you should check it. If a loaded skill turns out to be wrong for the situation, you don't need to use it.

### Workflow

```
User message received
  → Might any skill apply? (check .ai/skills/ list below)
    → YES (even 1% chance) → Read the SKILL.md → Follow it exactly
    → Definitely not → Respond normally
```

## Available Skills

| Skill | When to use |
|-------|-------------|
| brainstorming | Before any creative work - creating features, building components, adding functionality, or modifying behavior |
| writing-plans | When you have a spec or requirements for a multi-step task, before touching code |
| executing-plans | When you have a written implementation plan to execute with review checkpoints |
| subagent-driven-development | When executing implementation plans with independent tasks in the current session |
| test-driven-development | When implementing any feature or bugfix, before writing implementation code |
| systematic-debugging | When encountering any bug, test failure, or unexpected behavior, before proposing fixes |
| requesting-code-review | When completing tasks, implementing major features, or before merging |
| receiving-code-review | When receiving code review feedback, before implementing suggestions |
| verification-before-completion | When about to claim work is complete or fixed, before committing or creating PRs |
| dispatching-parallel-agents | When facing 2+ independent tasks that can be worked on without shared state |
| using-git-worktrees | When starting feature work that needs isolation from current workspace |
| finishing-a-development-branch | When implementation is complete and you need to decide how to integrate the work |
| writing-skills | When creating or editing skills |
| ui-prototype | When designing new pages, modifying page layouts, or prototyping UI changes |
| api-doc-sync | When API views, serializers, or routes in bkflow/apigw are changed |
| tapd-workitem-sync | When development requirements are confirmed, before implementation - ensure TAPD work item exists |

## Red Flags

These thoughts mean STOP—you're rationalizing:

| Thought | Reality |
|---------|---------|
| "This is just a simple question" | Questions are tasks. Check for skills. |
| "I need more context first" | Skill check comes BEFORE clarifying questions. |
| "Let me explore the codebase first" | Skills tell you HOW to explore. Check first. |
| "This doesn't need a formal skill" | If a skill exists, use it. |
| "I remember this skill" | Skills evolve. Read current version. |
| "The skill is overkill" | Simple things become complex. Use it. |
| "I'll just do this one thing first" | Check BEFORE doing anything. |

## Skill Priority

When multiple skills could apply, use this order:

1. **Process skills first** (brainstorming, debugging) - these determine HOW to approach the task
2. **Implementation skills second** - these guide execution

"Let's build X" → brainstorming first, then implementation skills.
"Fix this bug" → systematic-debugging first, then domain-specific skills.

## Skill Types

**Rigid** (TDD, debugging): Follow exactly. Don't adapt away discipline.

**Flexible** (patterns): Adapt principles to context.

The skill itself tells you which.

## User Instructions

Instructions say WHAT, not HOW. "Add X" or "Fix Y" doesn't mean skip workflows.
