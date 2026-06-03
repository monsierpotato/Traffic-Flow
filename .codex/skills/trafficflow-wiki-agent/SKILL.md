---
name: trafficflow-wiki-agent
description: Maintain a persistent markdown wiki for the TrafficFlow project. Use when Codex is asked to ingest project notes, architecture decisions, code findings, sprint plans, contracts, meeting notes, or research into `docs/wiki`; answer questions from the project wiki with citations; update cross-references; create new wiki pages; or lint the TrafficFlow knowledge base for stale claims, contradictions, missing pages, and orphaned topics.
---

# TrafficFlow Wiki Agent

Use this skill to keep a compounding project wiki for TrafficFlow. The wiki is the durable knowledge layer between raw project sources and chat answers.

## Wiki Location

Use these paths by default:

```text
docs/raw/
  notes/
  meetings/
  diagrams/
  research/
  attachments/
docs/wiki/
  index.md
  log.md
  architecture/
  ai-workflow/
  contracts/
  sprints/
  decisions/
  sources/
```

Read `references/trafficflow-wiki-schema.md` before creating or reorganizing wiki pages.

## Core Rules

- Treat raw sources, repo files, attached notes, and command output as evidence.
- Store durable user-provided source material under `docs/raw` before ingesting it when the source should be reused later.
- Treat `docs/wiki` as LLM-maintained synthesis, not source of truth.
- For TrafficFlow project questions, search `docs/wiki/index.md` and `docs/wiki/log.md` first to recover prior conversation context, completed work, decisions, architecture, progress, and related pages before giving a broad answer.
- Keep claims traceable with links to repo files, contract files, source notes, or log entries.
- Update `docs/wiki/index.md` after creating, renaming, or materially changing pages.
- Append one entry to `docs/wiki/log.md` for each ingest, query filed back to the wiki, or lint pass.
- Prefer small, focused pages over one large document.
- Use Obsidian-style links when linking wiki pages, for example `[[AI Runtime Engine]]`.
- Do not rewrite unrelated wiki pages just for style.

## Workflows

### Ingest

When the user gives a new source or asks to add knowledge to the wiki:

1. Read the source and identify durable facts, decisions, open questions, and contradictions.
2. Create or update the relevant wiki pages.
3. Add cross-links between pages.
4. Update `index.md`.
5. Append a dated `ingest` entry to `log.md`.
6. Summarize changed pages and unresolved questions.

### Query

When the user asks a project question:

1. Read `docs/wiki/index.md` first if it exists.
2. Read recent entries in `docs/wiki/log.md` to recover what changed recently.
3. Read the most relevant wiki pages and inspect repo files when current code state matters.
4. Prefer concise answers backed by wiki citations instead of re-explaining all prior context.
5. If the answer creates durable synthesis, ask or infer whether to file it back; when filing, create/update a wiki page and log the query.

### Lint

When asked to health-check the wiki:

1. Find orphan pages, duplicate topics, stale claims, missing cross-links, and contradictions.
2. Compare important claims against current repo files when possible.
3. Fix low-risk index/link issues directly.
4. Report higher-risk contradictions as findings before changing substantive claims.
5. Append a `lint` entry to `log.md`.

## TrafficFlow Focus Areas

Prioritize pages for:

- AI pipeline: YOLO/ByteTrack, counting, geometry, runtime engine, ROI annotation.
- Contracts: lane config, result JSON, API task/status/result shapes.
- Architecture: CLI, runtime, future FastAPI, worker, queue, storage, observability.
- Sprints: current progress, backlog, task ownership for a 5-person team.
- Decisions: accepted tradeoffs such as rectangular annotation ROI and `annotation crop: yes; processing crop: no`.

## Page Style

Use this page skeleton unless a page needs a different shape:

```markdown
# Page Title

## Summary
One short paragraph.

## Current State
- Evidence-backed facts.

## Decisions
- Accepted decisions and rationale.

## Open Questions
- Unresolved items.

## Links
- [[Related Page]]
```
