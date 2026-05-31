# Decision Log

## Accepted Decisions

- Use `trafficflow.runtime.engine` as the reusable AI workflow entrypoint.
- Keep `trafficflow.cli.run_counting` as a thin wrapper.
- Add production boundaries for API, worker, queue, storage, and observability before implementing each layer.
- Use rectangular ROI for lane drawing support.
- Use `annotation crop: yes; processing crop: no` for the MVP.
- Store lane geometry in source-frame coordinates.
- Support rectangular annotation ROI in the OpenCV config generator before building the web canvas flow.

## Deferred Decisions

- Whether to crop frames during AI processing.
- Whether to add ONNX/OpenVINO optimization before or after local end-to-end MVP.
- Whether MVP database starts with SQLite or PostgreSQL.
- Whether the OpenCV config generator needs ROI editing after lanes have already been added.

## Links

- [[Production Architecture]]
- [[ROI Annotation]]
- [[Project Backlog]]
