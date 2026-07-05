Tôi đang có một project về traffic flow với việc detect, tracking và counting vehicle , inference trên một video từ input người dùng. Tôi đã hoàn thành phần detect với việc sử dụng yolov11 và tracking với lại counting, hiện tại tới bước inference sẽ bao gồm frontend để tạo một website, backend, worker engineer. Tôi thì đảm nhận phần backend. Backend sẽ có các task gợi ý như sau :





3.1 FastAPI app structure: Dựng cấu trúc ứng dụng FastAPI (trafficflow/api/app.py) và định nghĩa các routes: upload, tasks, results, lanes.

3.2 Database schema: Tạo các bảng: Task (id, status, progress...), TrafficStatistic (task\_id, lane\_id, count...), và LaneConfig.

3.3 Upload + preview frame API: Route POST /api/v1/upload/video để lưu video, trích xuất frame đầu tiên và trả về video\_id + URL ảnh preview.

3.4 Task API: Các routes POST /api/v1/tasks/process, GET /api/v1/tasks/status/{task\_id}, và GET /api/v1/tasks/result/{task\_id}.

3.5 Tự động Dọn dẹp Ổ cứng (Data Retention): Viết Cron Job hoặc Background Task (cũng có thể giao cho Member 4) để tự động quét DB và xóa các file video cũ hơn 3 ngày khỏi ổ cứng, chỉ giữ lại số liệu thống kê.

3.6 Giới hạn Kích thước \& Định dạng File: Viết Middleware/Validator để chỉ chấp nhận các định dạng video phổ biến và từ chối file quá lớn (ví dụ: >50MB) hoặc video quá dài, trả về lỗi 413.



Sau cùng để kiểm tra backend oke chưa thì bạn có thể tạo cho tôi frontend để kiểm thử luôn web chạy trên local luôn.

