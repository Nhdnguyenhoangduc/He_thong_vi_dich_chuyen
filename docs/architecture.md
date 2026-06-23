# Kiến trúc hệ thống

## Tổng quan phân lớp

```
┌──────────────────────────────────────────────────────────────────┐
│  LỚP 3 — Phần mềm máy tính  (src/vision_pipeline.py)            │
│                                                                  │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ Vision Pipeline│→ │PIDController │→ │   SerialSender       │ │
│  │ 10 blocks      │  │ wall-clock dt│  │ ACK worker thread    │ │
│  └────────────────┘  └──────────────┘  └──────────────────────┘ │
└────────────────────────────────┬─────────────────────────────────┘
                                 │ UART 115 200 baud  "<N>b\n" / "OK\n"
┌────────────────────────────────▼─────────────────────────────────┐
│  LỚP 2 — Vi điều khiển  (arduino/stepper_controller.ino)         │
│  ISR Timer1 CTC → STEP pulse @ f_step Hz                         │
│  process_command() : parser lệnh ASCII + enable/disable driver   │
└────────────────────────────────┬─────────────────────────────────┘
                                 │ STEP / DIR
┌────────────────────────────────▼─────────────────────────────────┐
│  LỚP 1 — Cơ cấu chấp hành                                       │
│  SR3 Mini Driver → Stepper 2-phase → Ball screw p=2mm → Table    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Luồng dữ liệu chi tiết

```
Dino-Lite AM2111
  │ BGR 640×480 @ 30 fps
  ▼
build_mask_color()              build_mask_color()
  Blue  H:110-180 S:61-255       Dark  H:0-179 S:70-255 V:0-70
  ↓                               ↓
repair_mask()                  repair_mask()
  dilate ellipse 5×5             dilate ellipse 3×3
  close  rect    5×5             close  rect   17×17
  ↓                               ↓
filter_contours(min=3 000px²)  filter_contours(min=15 000px²)
  ↓                               ↓
detect_color_2lines()          find_rectangle_sides()
  top-2 contours by area          RANSAC N=150 ε=2px
  cv2.fitLine(DIST_L2)            extent_range 200–250px
  → LineInfo × 2                  parallel_tol 15°
                                  _sort_pair_by_x()
                                  → list[dict] × 2
                                        ↓
                               build_midline_from_pair()
                                  _canonicalize(d1) [v4 fix]
                                  align d2 → d1
                                  _canonicalize(avg)
                                  → LineInfo (VCL)
                ↓                       ↓
              compute_metrics(VCL, blue_lines)
                avg_angle_deg,  avg_dist_px
                        ↓
              PIDController.update(avg_dist_px)
                control = −pid_output
                        ↓
              SerialSender.update(control)
                → ACK worker thread
                → "<N>b\n"  (N = round(control_um / 1µm))
                        ↓
              Arduino: ISR Timer1 → N xung STEP
                        ↓
              "OK\n"  → tiếp tục frame kế
```

---

## Mô tả từng module / block

### Block 1 — `build_mask_color` / `build_mask_blue`
- BGR → HSV (`cv2.cvtColor`)
- `cv2.inRange` 3D: lower/upper bound arrays
- Output: binary mask uint8

### Block 2 — `repair_mask`
- `cv2.dilate` kernel ellipse (5×5 hoặc 3×3) — nối đoạn đứt
- `cv2.morphologyEx(MORPH_CLOSE)` kernel rect — lấp lỗ hổng
- Thứ tự dilate→close là có chủ ý: vùng liên thông lớn hơn giúp close hiệu quả hơn

### Block 3 — `filter_contours`
- `cv2.findContours(RETR_EXTERNAL, CHAIN_APPROX_SIMPLE)`
- Giữ contour có area ≥ min_area, vẽ lại lên mask sạch
- Output: (mask_clean, valid_contours)

### Block 4 — `cluster_and_fit` (contour-based, thay DBSCAN)
- `cv2.findContours(CHAIN_APPROX_NONE)` — cần toàn bộ pixel
- Sort by area desc, lấy top-2
- Mỗi contour → `fit_line_from_points`
- **Tốc độ**: C++ O(W·H) so với DBSCAN O(n log n) Python → **~40–80×**

### Block 5 — `detect_color_2lines`
- Kết hợp repair→filter→cluster_and_fit
- Vẽ 2 đường màu cyan/cam lên frame

### Block 6 — `ransac_one_line`
- Sample 2 điểm → direction vector đơn vị
- **Tối ưu**: `_orthogonal_distances_vec` dùng cross-product 2D thay SVD per-iter → **~10–15×**
- SVD chỉ gọi 1 lần trên winning inlier set

### Block 7 — `find_rectangle_sides`
- Tìm tuần tự nhiều cạnh, loại bỏ inliers đã dùng
- `_best_parallel_pair`: score = separation / mean_extent
- **v4**: `_sort_pair_by_x` — sắp xếp theo centroid X để gán left/right nhất quán

### Block 8 — `draw_rectangle_sides`
- Vẽ đoạn thẳng theo projected extent (không kéo dài đến biên)
- Annotate angle, extent, n_inliers

### Block 9 (không đánh số) — `build_midline_from_pair`
- **v4 fix**: `_canonicalize(d1)` trước → align d2 → `_canonicalize(avg)`
- `_extend_to_frame`: kéo đến biên theo Case A/B

### Block 10 — `compute_metrics` (vectorised)
- Stack vx2/vy2/x2/y2 thành NumPy arrays
- `np.arctan2` vectorised → avg_angle
- cross-product vectorised → avg_dist
- **Tốc độ**: ~3–5× so với list comprehension

### Block 11 — `SerialSender`
- Daemon thread riêng (`_ack_worker`)
- `update(val)`: ghi pending, set event
- Worker: gửi `<N>b\n`, chờ `OK\n` trong 10 s
- Nếu chưa nhận OK → không gửi lệnh mới (stop-and-wait)
- `SERIAL_ENABLE = False` → dry-run, không cần phần cứng

### Block 12 — `PIDController`
- `update(error)`: đo `dt` bằng `time.time()`
- Integral clamp: `np.clip(integral, -limit, +limit)`
- Output clamp: `np.clip(raw, -output_limit, +output_limit)`
- `reset()`: gọi khi mất nhận diện (tránh integrator wind-up)

---

## Firmware Arduino — `stepper_controller.ino`

### ISR Timer1 CTC
```
TIMER1_COMPA_vect:
  if remaining == 0 → stop timer, clear isr_moving
  PORTD |= (1<<2)   # STEP HIGH
  _delay_us(10)
  PORTD &= ~(1<<2)  # STEP LOW
  remaining--
```

### Hàm `move_steps(steps, send_ack)`
1. Chờ `isr_moving == false`
2. Đặt DIR_PIN theo dấu của steps
3. `cli()` → set `isr_steps_remaining`, `isr_moving=true` → `sei()`
4. `start_timer1(speed_steps_sec)` — prescaler /8, CTC mode
5. Busy-wait `while(isr_moving){}`
6. In `"Moved: Nb"`, nếu `send_ack=true` in `"OK"`

### Bộ parser lệnh (`process_command`)
| Lệnh | Hành động |
|---|---|
| `e` / `E` | Enable driver (HIGH) |
| `d` / `D` | Disable driver (LOW) |
| `x` / `X` | Dừng khẩn cấp (stop_timer1) |
| `s<N>` | Set tốc độ N bước/s |
| `<N>b` | Di chuyển N bước, gửi OK |
| `<F>` | Di chuyển F mm (dùng terminal thủ công) |

### Thông số cơ học
```
STEPS_PER_REV_DRIVER = 2000  vi-bước/vòng
LEAD_MM              = 2.0   mm/vòng
STEPS_PER_MM         = 1000  vi-bước/mm
d_step               = 1 µm/vi-bước
```
