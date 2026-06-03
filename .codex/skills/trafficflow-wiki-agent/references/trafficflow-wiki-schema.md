# TrafficFlow Wiki Schema

## Directory Layout

```text
docs/raw/
  README.md                Raw source policy.
  notes/                   Pasted planning notes and ad-hoc source text.
  meetings/                Meeting transcripts and summaries.
  diagrams/                Architecture diagrams and image references.
  research/                Papers, articles, benchmark notes.
  attachments/             Supporting assets referenced by raw notes.
docs/wiki/
  index.md                 Content-oriented catalog.
  log.md                   Append-only chronological activity log.
  architecture/            System boundaries and deployment shape.
  ai-workflow/             Detection, tracking, counting, ROI, geometry.
  contracts/               JSON/API contracts shared by frontend/backend/AI.
  sprints/                 Sprint plans, backlog, ownership.
  decisions/               Architecture decision records.
  sources/                 Summaries of raw notes, pasted files, meetings.
```

Create directories as needed. Do not create empty pages unless they help navigation.

`docs/raw` is source material. The wiki agent may add new raw files when asked to preserve a source, but should not rewrite raw source content during normal ingest.

## Required Files

### `docs/wiki/index.md`

Keep this content-oriented. Organize by category and list each wiki page with a one-line summary.

Example:

```markdown
# TrafficFlow Wiki Index

## Architecture
- [[Production Architecture]] - Backend, worker, queue, storage, and AI runtime boundaries.

## AI Workflow
- [[ROI Annotation]] - Rectangular crop workflow for accurate lane drawing.
```

### `docs/wiki/log.md`

Keep this append-only. Each entry starts with:

```markdown
## [YYYY-MM-DD] ingest | Title
## [YYYY-MM-DD] query | Title
## [YYYY-MM-DD] lint | Title
```

Include short bullets for pages changed and source evidence.

## Naming

- Use Title Case page titles.
- Use descriptive filenames in kebab-case.
- Keep wiki links human-readable with Obsidian-style labels.

Example:

```text
docs/wiki/ai-workflow/roi-annotation.md
Title: ROI Annotation
Wiki link: [[ROI Annotation]]
```

## Evidence Rules

- For repo evidence, link to files such as `trafficflow/runtime/engine.py`.
- For contract evidence, link to files such as `docs/contracts/annotation_roi.md`.
- For user-provided source notes, create a summary page under `docs/wiki/sources/`.
- If a claim is inferred, label it as an inference.
- For ordinary TrafficFlow project questions, start with `docs/wiki/index.md` and recent `docs/wiki/log.md` entries to avoid rediscovering context from scratch.
- If a wiki page is stale or contradicted by current repo files, trust the current repo file, update the wiki page if appropriate, and append a log entry.

## TrafficFlow Canonical Decisions

Record these unless contradicted by newer project decisions:

- `trafficflow.cli.run_counting` should remain a thin CLI wrapper.
- Reusable AI orchestration belongs in `trafficflow.runtime.engine`.
- Production-facing boundaries include `api`, `worker`, `queue`, `storage`, and `observability`.
- Rectangular ROI for lane drawing is an annotation feature first.
- MVP ROI policy: `annotation crop: yes; processing crop: no`.
- Lane geometry sent to backend/AI should remain in full-frame source coordinates.
