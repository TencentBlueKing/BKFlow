# _shared

## Purpose

`prototypes/masters/_shared/` stores shared shells and navigation scaffolding that multiple masters can reuse. It is not a page-type master and does not preview independently.

## Contract

- `prototypes/masters/_shared/` is shared scaffolding only and is not a page-type master.
- It does not preview independently.
- Keep navigation shells, structural fragments, and other reuse-only pieces here.
- Do not put delivery pages or feature-specific masters here.

## What goes here

- Shared layout shells.
- Cross-master navigation structure.
- Common structural fragments that are not business-specific.

## What should not go here

- Feature-specific pages.
- Archived examples.
- Anything that only makes sense for a single spec or plan.

## Relationship to `docs/specs` and `docs/plans`

`docs/specs/` and `docs/plans/` define the work that consumes these shared shells. The shared directory should stay generic so it can support many specs and plans without being rewritten each time.
