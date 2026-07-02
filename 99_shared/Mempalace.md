Mempalace.md --> setup and intention of project-memory in mempalace.

Overall --> Mempalace should document mechanically architectural decisions, learnings, incidents, and release notes across the two repos data-layer and product-layer. 

Folder taxonomy
Use one workspace with two root areas:

01_product-layer

02_data-layer

99_shared

Inside each root area, use the same page structure so the pattern stays consistent:

00_overview

01_decisions

02_design-notes

03_incidents

04_learnings

05_releases

06_quality-runs

07_open-items


folder-tree
----
mempalace/
├── product-layer/
│   ├── 00_overview/
│   ├── 01_decisions/
│   ├── 02_design-notes/
│   ├── 03_incidents/
│   ├── 04_learnings/
│   ├── 05_releases/
│   ├── 06_quality-runs/
│   └── 07_open-items/
├── data-layer/
│   ├── 00_overview/
│   ├── 01_decisions/
│   ├── 02_design-notes/
│   ├── 03_incidents/
│   ├── 04_learnings/
│   ├── 05_releases/
│   ├── 06_quality-runs/
│   └── 07_open-items/
├── 99_shared/
│   ├── 00_index/
│   ├── 01_standards/
│   ├── 02_access-control/
│   ├── 03_metadata/
│   ├── 04_test-strategy/
│   └── 05_llm-ops/
├── decision.md
├── incident.md
├── design-note.md
├── release.md
├── quality-run.md
├── learnings.md
├── open-items.md
└── 00_index.md