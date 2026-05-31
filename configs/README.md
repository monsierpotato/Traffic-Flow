# Configs

Manual geometry JSON files live here.

```text
configs/
  examples/    Small/reference configs
  danang/      Danang camera configs
```

Generate a Danang config:

```powershell
.\.venv-gpu\Scripts\python.exe -m trafficflow.cli.config_generator --video "data\raw\danang\Cầu Rồng.mp4" --output configs\danang\cau_rong_manual.json --camera-id danang_cau_rong --frame-index 150 --display-max-size 1280
```

Run counting with it:

```powershell
.\.venv-gpu\Scripts\python.exe -m trafficflow.cli.run_counting --video "data\raw\danang\Cầu Rồng.mp4" --config configs\danang\cau_rong_manual.json --model models\yolov8n.pt --device 0 --output-video outputs\danang\cau_rong\counted.mp4 --output-jsonl outputs\danang\cau_rong\events.jsonl
```
