# Thực nghiệm và kết quả

## Điều kiện thực nghiệm

| Yếu tố | Giá trị |
|---|---|
| Camera | Dino-Lite AM2111, CMOS 640×480, 30 fps, 20–200× |
| Máy tính | Acer Swift 3, Python 3.10, OpenCV 4.x |
| Vi điều khiển | Arduino Uno (ATmega328P, 16 MHz, 32 KB Flash) |
| Driver | SR3 Mini |
| Động cơ | Stepper 2 pha, 2 000 vi-bước/vòng |
| Vít me | Ball screw p = 2 mm → δ = 1 µm/vi-bước |
| Cổng Serial | COM5, 115 200 baud, 8N1 |
| Môi trường | Bàn cố định, phòng thí nghiệm |

---

## Thông số hệ thống

| Thông số | Giá trị | Đơn vị |
|---|---|---|
| Hệ số tỷ lệ S | 33.33 | µm/px |
| Kp | 0.2 | — |
| Ki | 0.01 | — |
| Kd | 0.0 | — |
| integral_limit | 5 000 | µm |
| output_limit | 150 000 | µm |
| δ (độ phân giải) | 1 | µm/vi-bước |
| ε (ngưỡng hội tụ visual) | ~33 | µm (1 px) |
| RANSAC N | 150 | — |
| RANSAC ε_inlier | 2.0 | px |
| extent_range | [200, 250] | px |
| parallel_tol | 15.0 | ° |
| Timeout ACK | 10 | s |
| Tốc độ motor mặc định | 8 000 | vi-bước/s |
| Tốc độ motor tối đa | 35 000 | vi-bước/s |

---

## Thực nghiệm 1 — Hiệu suất pipeline thị giác

### Mục tiêu
Đánh giá tốc độ và độ ổn định nhận diện của từng block.

### Kết quả tốc độ (640×480, CPU Intel Core i5)

| Block | Phiên bản cũ | v4 (hiện tại) | Tăng tốc |
|---|---|---|---|
| Cluster blue lines (DBSCAN) | ~80–150 ms | — | — |
| Cluster blue lines (contour) | — | ~1–3 ms | **~40–80×** |
| RANSAC distance (SVD per iter) | ~15–30 ms | — | — |
| RANSAC distance (cross-product) | — | ~1–3 ms | **~10–15×** |
| compute_metrics (list comp.) | ~2–4 ms | — | — |
| compute_metrics (vectorised) | — | ~0.4–0.8 ms | **~3–5×** |
| Tổng pipeline / frame | ~100–180 ms | ~8–15 ms | **~10–20×** |

### Kết quả ổn định nhận diện

| Điều kiện | Blue lines | Rectangle sides | VCL stable |
|---|---|---|---|
| Góc lệch < 5° | ✅ | ✅ | ✅ (v4 fix) |
| Góc lệch 5°–15° | ✅ | ✅ | ✅ |
| Góc lệch 15°–30° | ✅ | ⚠️ extent filter | ✅ |
| Dịch chuyển ngang | ✅ | ✅ | ✅ |
| Ánh sáng đồng đều | ✅ | ✅ | ✅ |
| Ánh sáng không đồng đều | ⚠️ | ⚠️ | ⚠️ |
| Phản xạ bề mặt chip | ✅ | ⚠️ RANSAC outlier | ✅ |

---

## Thực nghiệm 2 — Hội tụ bộ điều khiển PID

### Điều kiện ban đầu
- Sai lệch vị trí: **+51.9 px ≈ +1 731.6 µm**
- Sai lệch góc: +0.095°

### Dữ liệu đáp ứng (trích từ `results/pid_response_sample.csv`)

| Frame | t (s) | Δd (µm) | u (µm) | N bước |
|---|---|---|---|---|
| 1 | 0.000 | +1 731.6 | +346.3 | 346 |
| 5 | 0.133 | +709.3 | +141.9 | 142 |
| 10 | 0.300 | +231.4 | +46.3 | 46 |
| 20 | 0.633 | −13.2 | −2.6 | −3 |
| 30 | 0.966 | −3.1 | −0.6 | −1 |
| 60 | 1.966 | +0.3 | +0.1 | 0 |
| 100 | 3.300 | 0.0 | 0.0 | 0 |
| 440 | 14.500 | 0.0 | 0.0 | 0 |

### Kết quả chỉ tiêu

| Chỉ tiêu | Giá trị đo | Nhận xét |
|---|---|---|
| Thời gian xác lập t_s | ≈ 2.5 s | Đáp ứng nhanh |
| Sai số hội tụ | < 33 µm (< 1 px) | Giới hạn bởi độ phân giải camera |
| Quá điều chỉnh | ≈ −8 px ≈ 15% | Do Kd=0, quán tính cơ học |
| Sai lệch tĩnh | 0 | Ki=0.01 triệt tiêu hoàn toàn |
| Thời gian quan sát | 14.5 s | Ổn định không dao động |

---

## Thực nghiệm 3 — Kiểm tra giao thức Serial ACK

### Kịch bản test

```
python scripts/test_serial.py --port COM5 --steps 500
```

| Test | Lệnh gửi | Phản hồi Arduino | Thời gian |
|---|---|---|---|
| Enable driver | `e\n` | `Driver: ON` | < 5 ms |
| Di chuyển +500 bước | `500b\n` | `Moved: 500b` + `OK` | ≈ 63 ms (500/8000 s) |
| Di chuyển −500 bước | `-500b\n` | `Moved: -500b` + `OK` | ≈ 63 ms |
| Disable driver | `d\n` | `Driver: OFF` | < 5 ms |

**Ghi chú**: 500 bước × 1 µm = 500 µm = 0.5 mm. Tốc độ 8 000 bước/s → t = 500/8000 ≈ 62.5 ms.

---

## Phân tích hạn chế và đề xuất cải thiện

### Hạn chế hiện tại

| Hạn chế | Nguyên nhân | Ảnh hưởng |
|---|---|---|
| Sai số ≥ 33 µm | S = 33.33 µm/px → 1 px = 33 µm (độ phân giải camera) | Chưa đạt mục tiêu < 2 µm |
| Quá điều chỉnh ~15% | Kd = 0, quán tính cơ học, delay Serial | Có thể cải thiện với Kd > 0 |
| Nhạy ánh sáng | HSV threshold cố định | Mất nhận diện khi sáng thay đổi |
| Chỉ 1 trục (X) | Thiết kế phần cứng hiện tại | Chưa bù được Δθ |
| extent_range [200,250] px | Phụ thuộc zoom Dino-Lite | Cần điều chỉnh khi thay đổi độ phóng đại |

### Đề xuất cải thiện

| Vấn đề | Giải pháp |
|---|---|
| S = 33 µm/px | Camera công nghiệp + vật kính cao hơn → S < 5 µm/px → đạt < 2 µm |
| Quá điều chỉnh | Kd > 0 + low-pass filter trên D term |
| Nhạy ánh sáng | CLAHE adaptive histogram eq. + vòng LED đồng trục |
| Điều khiển góc | Thêm trục quay θ, đưa avg_angle vào PID thứ 2 |
| extent_range cứng | Auto-calibrate từ frame đầu tiên khi nhận diện thành công |
| Kiểm tra chip | Mô hình CNN/YOLOv8 phát hiện bụi/xước/bọt khí trước khi căn chỉnh |
