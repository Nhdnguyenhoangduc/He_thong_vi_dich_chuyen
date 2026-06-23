# API Reference — `src/vision_pipeline.py`

## Constants

```python
SCALE_UM_PER_PX: float = 10_000 / 300   # ≈ 33.33 µm/px

SERIAL_PORT     = "COM5"
SERIAL_BAUDRATE = 115_200
SERIAL_ENABLE   = True
ACK_TIMEOUT_S   = 10.0
```

---

## Data Classes

### `LineInfo`

```python
@dataclass(slots=True)
class LineInfo:
    pt1: tuple[int, int]    # điểm đầu (clipped đến biên ảnh)
    pt2: tuple[int, int]    # điểm cuối (clipped đến biên ảnh)
    vx:  float              # vectơ chỉ phương (đã canonicalize)
    vy:  float
    x0:  float              # centroid / anchor point
    y0:  float
```

---

## Block 1 — Colour Masking

```python
build_mask_color(frame, h_low, s_low, v_low, h_up, s_up, v_up) -> np.ndarray
```
BGR → HSV → `cv2.inRange`. Trả về binary mask uint8.

```python
build_mask_blue(frame) -> np.ndarray
```
Shortcut: H=[90,130], S=[100,255], V=[0,255].

---

## Block 2 — Morphology

```python
repair_mask(mask, dilate_ksize=5, close_ksize=5) -> np.ndarray
```
Dilate ellipse → Close rect. Trả về binary mask đã làm sạch.

---

## Block 3 — Contour Filtering

```python
filter_contours(mask, min_area=300) -> tuple[np.ndarray, list]
```
Loại bỏ blob nhỏ. Trả về `(mask_clean, valid_contours)`.

---

## Block 4 — Line Fitting

```python
_canonicalize(vx, vy) -> tuple[float, float]
```
Chuẩn hóa chiều vectơ: `vy > 0` (near-vertical) hoặc `vx > 0` (near-horizontal).

```python
_extend_to_frame(x0, y0, vx, vy, img_h, img_w) -> tuple[pt1, pt2]
```
Kéo dài đường tham số đến biên ảnh.

```python
fit_line_from_points(points, img_h, img_w) -> LineInfo | None
```
`cv2.fitLine(DIST_L2)` → `_canonicalize` → `_extend_to_frame`.
Trả về `None` nếu len(points) < 10.

---

## Block 5 — Blue Line Detection

```python
cluster_and_fit(mask, img_h, img_w,
                min_contour_area=300,
                min_pts_per_line=10) -> list[LineInfo]
```
Top-2 contours by area → fit_line_from_points. Trả về 0–2 `LineInfo`.

```python
detect_color_2lines(frame, mask,
                    colors=((0,255,0),(0,128,255)),
                    thickness=2) -> tuple[frame_drawn, list[LineInfo], mask_cleaned]
```
Pipeline đầy đủ: repair → filter → cluster_and_fit → vẽ lên frame.

---

## Block 6 — RANSAC

```python
_orthogonal_distances_vec(points, anchor, direction) -> np.ndarray
```
Khoảng cách vuông góc vectorised: `|diff[:,0]*dy - diff[:,1]*dx|`.

```python
_fit_line_svd(points) -> tuple[centroid, direction]
```
SVD refinement. Chỉ gọi 1 lần trên winning inlier set.

```python
ransac_one_line(points, n_iter=300, thresh=2.0) -> tuple[centroid, direction, mask]
```
RANSAC core. Trả về `(None, None, None)` nếu thất bại.

---

## Block 7 — Rectangle Sides

```python
_angle_diff(a1, a2) -> float
```
Góc không dấu giữa 2 đường, kết quả ∈ [0°, 90°].

```python
_line_separation(l1, l2) -> float
```
Khoảng cách vuông góc giữa hai đường song song.

```python
_sort_pair_by_x(pair) -> list[dict]
```
Sắp xếp theo centroid X tăng dần (left → right). **v4 fix**.

```python
find_rectangle_sides(mask_clean,
                     n_iter=300, thresh=2.0,
                     min_inliers=20, max_attempts=6,
                     parallel_tol=15.0,
                     extent_range=(0, inf)) -> list[dict]
```
Tìm hai cạnh dài song song. Mỗi dict có keys:
```
centroid, direction, normal, inliers, angle_deg, n_inliers, extent
```

---

## Block 8 — Debug Draw

```python
draw_rectangle_sides(frame, lines) -> np.ndarray
```
Vẽ đoạn thẳng (không kéo đến biên) + annotate angle/extent/n lên bản sao frame.

---

## Block 9 — Virtual Centre Line

```python
build_midline_from_pair(pair, img_h, img_w) -> LineInfo | None
```
**v4 fix**: `_canonicalize(d1)` → align d2 → `_canonicalize(avg)` → extend.
Trả về `None` nếu pair rỗng hoặc < 2 phần tử.

---

## Block 10 — Metrics

```python
signed_angle_deg(line1, line2) -> float
```
Góc có dấu từ line2 → line1, chuẩn hóa về (−90°, +90°].
```
cross = vx1*vy2 − vy1*vx2
dot   = vx1*vx2 + vy1*vy2
Δθ = atan2(cross, dot)
```

```python
signed_distance_px(line1, line2) -> float
```
Khoảng cách có dấu từ centroid line1 đến line2:
```
d = vy2*(x1−x2) − vx2*(y1−y2)
```

```python
px_to_um(distance_px, scale=SCALE_UM_PER_PX) -> float
```

```python
compute_metrics(line1, lines2) -> tuple[float, float] | tuple[None, None]
```
Vectorised: avg_angle_deg, avg_dist_px. Trả về `(None, None)` nếu `lines2` rỗng.

---

## Block 11 — SerialSender

```python
class SerialSender:
    def __init__(self, port, baudrate, enable=True): ...
    def update(self, avg_dist_px: float) -> None: ...
    def close(self) -> None: ...
    status_text: str   # hiển thị trên frame
```

**`update(val)`**: convert → pending_um, set event.  
**ACK worker**: gửi `"<N>b\n"`, loop readline cho đến `"OK"` hoặc timeout 10 s.  
**`SERIAL_ENABLE=False`**: dry-run, in log nhưng không cần phần cứng.

---

## Block 12 — PIDController

```python
class PIDController:
    def __init__(self, kp, ki, kd,
                 integral_limit=5000.0,
                 output_limit=10000.0): ...

    def update(self, error: float) -> float: ...
    def reset(self) -> None: ...

    # Read-only state (sau mỗi update)
    last_p:   float
    last_i:   float
    last_d:   float
    last_out: float
    _integral: float
```

**Lưu ý quan trọng**: Trong `main()`, tín hiệu điều khiển được đảo dấu:
```python
control = -pid.update(avg_dist)   # đổi chiều: lệch dương → di chuyển âm
sender.update(control)
```

---

## Firmware Arduino — Protocol

### Giao tiếp
- Baudrate: 115 200, 8N1
- Lệnh kết thúc bằng `\n`; `\r` bị bỏ qua

### Bảng lệnh

| Lệnh | Hành động | Phản hồi |
|---|---|---|
| `e` | Enable driver (HIGH) | `Driver: ON` |
| `d` | Disable driver (LOW) | `Driver: OFF` |
| `x` | Dừng khẩn cấp | `DUNG KHAN CAP` |
| `s<N>` | Set speed (bước/s) | `Toc do: N` |
| `<N>b` | Di chuyển N vi-bước | `Moved: Nb` + `OK` |
| `<F>` | Di chuyển F mm | `Moved: Nb` (không gửi OK) |

### Thông số Timer1

```
prescaler = /8  →  f_tick = 16MHz/8 = 2MHz
OCR1A = (2_000_000 / speed_steps_sec) − 1
Mode: CTC (WGM12)
```

Với tốc độ mặc định 8 000 bước/s:
```
OCR1A = 2_000_000/8_000 − 1 = 249
f_ISR = 2MHz / 250 = 8 000 Hz  ✓
```
