# masters

## Purpose

`prototypes/masters/` is the long-lived source of truth for page-type masters and state templates. Put full page-type masters, reusable interaction shells, and stable state templates here.

## Contract

- `prototypes/masters/` is the source of truth for complete page-type masters and state templates.
- Use this directory for reusable full pages, interaction shells, and stable states.
- Do not put `_shared/` pages here.
- See `docs/specs/` and `docs/plans/` for feature scope; this tree stays reusable.

## What goes here

- Page-type masters that can be reused by multiple features.
- Shared shell fragments that are stable enough to become defaults.
- Reference states that help future feature pages stay consistent.

## What should not go here

- One-off feature pages tied to a single spec or plan.
- Historical snapshots that only exist for archive purposes.
- Temporary experiments that are not ready to be treated as a master.

## Relationship to `docs/specs` and `docs/plans`

`docs/specs/` defines the target behavior and `docs/plans/` tracks implementation steps for a single change. This directory holds the reusable master material that those documents can point to, but it should remain independent from any one spec or plan slug.
