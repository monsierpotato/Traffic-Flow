# Raw Sources

This directory stores immutable source material for the TrafficFlow wiki.

Use this layer for:

- pasted planning notes
- meeting notes
- architecture sketches
- API contract drafts
- benchmark notes
- research links exported as markdown
- screenshots or diagrams referenced by notes

The wiki agent reads files from this directory and writes synthesized pages under `docs/wiki/`.
Do not edit raw files during ingest except to fix filename mistakes or add missing metadata requested by the user.

Suggested structure:

```text
docs/raw/
  notes/
  meetings/
  diagrams/
  research/
  attachments/
```
