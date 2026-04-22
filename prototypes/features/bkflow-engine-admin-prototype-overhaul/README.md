# BKFlow Engine Admin Prototype Overhaul

## Related Docs
- Spec: `docs/specs/2026-04-21-bkflow-engine-admin-prototype-overhaul-design.md`
- Plan: `docs/plans/2026-04-21-bkflow-engine-admin-prototype-overhaul.md`

## Purpose
This feature bundles the full BKFlow engine admin prototype overhaul into one traceable delivery set. The goal is to rebuild the admin experience as a complete `space / system / plugin` prototype family, with the real navigation, list, editor, detail, and debug states represented in one feature directory.

## Masters Used
- `prototypes/masters/_shared/space-shell.html`
- `prototypes/masters/_shared/system-shell.html`
- `prototypes/masters/_shared/plugin-shell.html`
- `prototypes/masters/list-page/template.html`
- `prototypes/masters/config-page/template.html`
- `prototypes/masters/flow-editor/template.html`
- `prototypes/masters/task-detail/template.html`
- `prototypes/masters/decision-editor/template.html`
- `prototypes/masters/engine-panel/template.html`
- `prototypes/masters/overlays/dialogs.html`
- `prototypes/masters/overlays/sidesliders.html`

## Page Entries

### Space
- `pages/space/template-list.html`
- `pages/space/flow-view.html`
- `pages/space/flow-edit.html`
- `pages/space/flow-debug.html`
- `pages/space/task-list.html`
- `pages/space/debug-task-list.html`
- `pages/space/task-detail-complete.html`
- `pages/space/task-detail-failed.html`
- `pages/space/decision-list.html`
- `pages/space/decision-editor.html`
- `pages/space/space-config.html`
- `pages/space/credential-list.html`
- `pages/space/label-list.html`
- `pages/space/statistics-exception.html`

### System
- `pages/system/space-config-list.html`
- `pages/system/module-config-list.html`

### Plugin
- `pages/plugin/plugin-list.html`

## Notes
- `index.html` is the feature entry point for previewing the page inventory.
- `CHANGELOG.md` keeps only lightweight initialization and follow-up notes.
