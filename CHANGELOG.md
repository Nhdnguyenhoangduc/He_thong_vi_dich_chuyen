# Changelog

Format theo [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
phiên bản theo [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- Điều khiển trục Y + xoay θ (avg_angle đã tính sẵn)
- Auto-calibrate extent_range từ frame đầu tiên
- CLAHE adaptive histogram equalization giảm nhạy sáng
- Kd > 0 + low-pass filter trên D term
- Camera công nghiệp → S < 5 µm/px → đạt mục tiêu < 2 µm

---

## [4.0.0] — 2026-06-01  *(current)*

### Fixed — Virtual centre line "flipping" bug (critical)
- **`build_midline_from_pair`**: thêm bước `_canonicalize(d1)` TRƯỚC khi dùng d1
  làm tham chiếu cho d2 — loại bỏ hoàn toàn hiện tượng đường trung tâm nhảy
  frame-to-frame khi RANSAC trả về `−d1` thay `+d1`.
- **`_sort_pair_by_x`**: sắp xếp cặp cạnh theo centroid X → pair[0]/pair[1]
  luôn là left/right ổn định mỗi frame.

### Changed
- `_canonicalize`: tài liệu hoá rõ quy tắc near-vertical/near-horizontal
- Thêm `seed=0` vào `np.random.default_rng` trong `ransac_one_line` → kết quả reproducible

---

## [3.0.0] — 2026-05-15

### Changed — Thay thế KMeans bằng `cv2.findContours`
- **`cluster_and_fit`**: xoá bỏ sklearn KMeans, dùng contour topology C++
- Tốc độ: ~40–80× so với DBSCAN; ~8–12× so với KMeans
- Không còn dependency sklearn tại runtime

---

## [2.0.0] — 2026-04-20

### Changed — Vectorised RANSAC & metrics
- **`_orthogonal_distances_vec`**: thay `np.linalg.svd` per-iteration bằng
  cross-product 2D vectorised → ~10–15× nhanh hơn
- **`compute_metrics`**: thay list comprehension bằng NumPy stack → ~3–5× nhanh hơn
- SVD chỉ gọi 1 lần trên winning inlier set (`_fit_line_svd`)

---

## [1.0.0] — 2026-03-01  *(baseline)*

### Added
- Vision pipeline 10 blocks: HSV masking → morphology → contour → RANSAC → metrics
- `PIDController`: wall-clock dt, anti-windup, output clamp
- `SerialSender`: daemon ACK thread, stop-and-wait protocol
- Firmware Arduino: ISR Timer1 CTC + command parser ASCII
- `_canonicalize`, `_extend_to_frame`, `_sort_pair_by_x`
- Đồ thị PID response tích hợp trong `main()` (matplotlib)
