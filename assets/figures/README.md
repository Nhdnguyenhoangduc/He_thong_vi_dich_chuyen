# Figures

Thư mục này chứa các hình ảnh minh họa cho tài liệu:

| File | Mô tả |
|---|---|
| `system_overview.png` | Sơ đồ tổng thể hệ thống phần cứng |
| `vision_pipeline.png` | Kết quả từng bước của pipeline thị giác |
| `pid_response.png` | Đồ thị đáp ứng PID (tạo bằng `scripts/plot_results.py`) |
| `hardware_setup.jpg` | Ảnh thực tế bàn thực nghiệm |

Để tạo `pid_response.png`:
```bash
python scripts/plot_results.py --csv results/pid_response_sample.csv --save
```
