# TrafficFlow documentation

Tài liệu được chia thành ba nhóm: tài liệu vận hành hiện tại, hợp đồng tích
hợp, và báo cáo lịch sử/benchmark. Luồng được hỗ trợ hiện tại là `src/` + React
Vite + FastAPI + Celery/Redis + local YOLO/ByteTrack.

## Bắt đầu từ đây

| Tài liệu | Dùng khi |
|---|---|
| [current/architecture.md](current/architecture.md) | Hiểu module và data flow hiện tại |
| [current/operations.md](current/operations.md) | Chạy local, readiness và blocker |
| [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) | Chạy native local bằng Node.js + Python |
| [HUONG_DAN_SU_DUNG.md](HUONG_DAN_SU_DUNG.md) | Tài liệu sử dụng/lịch sử triển khai |
| [API_INTEGRATION.md](API_INTEGRATION.md) | Tra endpoint, trạng thái task và callback |
| [contracts/](contracts/) | Schema lane config, callback và kết quả |

## Bố cục repository

```text
src/api/       FastAPI app, routes, schemas, services
src/shared/    settings, Mongo/local JSON fallback, R2 client
src/worker/    Celery task và video pipeline
src/tfengine/  YOLO + ByteTrack + counting engine
frontend/      React/Vite operator UI
benchmark/     parser, runner, metric và config benchmark
scripts/        supported preflight, startup and dependency checks
tools/archive/ script thủ công lịch sử, không chạy trong runtime/CI
```

## Phân loại tài liệu

- `docs/current/`: nguồn chuẩn cho trạng thái và cách chạy hiện tại.
- `docs/contracts/`: các boundary không được tự ý đổi khi refactor.
- Các báo cáo phase/portfolio/raw đã được loại khỏi source tree vì không cần
  cho runtime project.
