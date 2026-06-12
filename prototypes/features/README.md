# features

## Purpose

`prototypes/features/` holds one directory per feature slug. Each feature directory should bundle the pages needed for a single spec/plan pairing tied to a feature slug.

## Contract

- `prototypes/features/` is organized by feature slug.
- Each feature slug maps to one spec and one plan.
- Put delivery pages, feature notes, and change logs here.
- Do not put long-lived masters or shared shells here.
- `feature.meta.json` is the homepage showcase contract for each feature slug.
- `README.md` remains the narrative documentation for the feature directory.
- When creating a new feature, keep `README.md`, `index.html`, and `feature.meta.json` in sync.
- Keep `feature.meta.json` up to date so the showcase homepage can auto-discover the feature card, representative pages, and ordering without extra wiring.

## `feature.meta.json` Schema

```json
{
  "title": "feature 标题",
  "summary": "一句话说明这个 feature",
  "status": "可评审",
  "tags": ["标签1", "标签2"],
  "coverTheme": "mixed-admin",
  "order": 10,
  "featuredPages": [
    {
      "path": "pages/space/flow-edit.html",
      "title": "流程编辑页",
      "summary": "展示该页的核心能力",
      "pageType": "流程编辑"
    }
  ]
}
```

`featuredPages[*].path` 必须指向当前 feature 目录下真实存在的 HTML 文件，首页会拿它作为代表页入口。

## What goes here

- Feature-specific prototype pages.
- Lightweight feature notes and change logs.
- Pages that are meant to answer one concrete requirement.

## What should not go here

- Long-lived master patterns.
- Shared shell fragments.
- Miscellaneous examples that are not tied to a feature slug.

## Relationship to `docs/specs` and `docs/plans`

Each feature directory should be traceable back to one `docs/specs/` document and one `docs/plans/` document. That relationship should stay explicit so the prototype work can be reviewed against the requested scope.
