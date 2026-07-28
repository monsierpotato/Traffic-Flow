# Inference model bundle

Put model weights used by the worker and serving process in this directory.
This directory is the canonical deploy location so `inference/serving/` and
the model assets can be shipped together:

```text
inference/
├── models/
│   └── yolov8n.pt
└── serving/
    └── app.py
```

Weights are ignored by git. Configure a different location with
`AI_MODEL_DIR` and optionally select a file with `AI_MODEL_PATH`.
