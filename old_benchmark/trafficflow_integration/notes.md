# TrafficFlow Integration Notes

## Lane Assignment

Input cần có:

- Lane polyline theo schema chung.
- Vehicle bounding box từ YOLOv8 + track id từ ByteTrack.
- Vùng ROI hoặc homography nếu muốn mapping sang mặt phẳng đường.

Baseline đơn giản:

1. Lấy bottom-center point của vehicle bbox.
2. Tạo polygon lane từ cặp lane boundary hoặc từ centerline đã mở rộng.
3. Kiểm tra point-in-polygon để gán `lane_id`.
4. Nếu point không nằm trong polygon nào, chọn lane gần nhất theo khoảng cách tới polyline.

## Rủi ro

- CCTV cố định khác domain dashcam, lane detector có thể lệch nhiều.
- Xe che vạch làn làm lane nhảy giữa các frame.
- Lane nhìn đẹp chưa chắc counting đúng, cần đo downstream metric theo lane.
