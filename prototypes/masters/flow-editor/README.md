# flow-editor

## Purpose

`prototypes/masters/flow-editor/` is the reusable master for graph-style flow editing pages. It mirrors the audited BKFlow interaction split between the canvas, a double-click node configuration drawer, floating overlays, and the save / publish / debug header actions.

## What it covers

- A header with back entry, flow title, and version context.
- Canvas-first editing with single-click selection and a nearby floating toolbar.
- A double-click node configuration drawer grouped into `基础信息 / 输入参数 / 输出参数`.
- A global variables floating layer opened from the drawer instead of a full-page switch.
- Separate local drawer confirm and global save / publish / debug header actions.
