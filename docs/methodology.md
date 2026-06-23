# Phương pháp và cơ sở lý thuyết

## 1. Không gian màu HSV và phân ngưỡng 3D

Hệ thống tách thông tin màu sắc (H) khỏi độ sáng (V) bằng cách chuyển sang không gian HSV,
giúp ngưỡng màu ổn định dưới nhiều mức chiếu sáng khác nhau.

### Chuyển đổi BGR → HSV

Sau khi chuẩn hóa r, g, b ∈ [0, 1]:

```
V = max(r, g, b)
S = (V − min(r,g,b)) / V      (S = 0 nếu V = 0)
H = 60° × (g−b)/(V−min)       nếu V = r
    60° × (2 + (b−r)/(V−min)) nếu V = g
    60° × (4 + (r−g)/(V−min)) nếu V = b
```

OpenCV nén H về `[0, 179]` (chia đôi từ 360°).

### Ngưỡng phân đoạn (source code thực tế)

| Đối tượng | H | S | V | Hàm gọi |
|---|---|---|---|---|
| Đường tham chiếu xanh | [110, 180] | [61, 255] | [0, 255] | `build_mask_color` trong `main()` |
| `build_mask_blue` (alias) | [90, 130] | [100, 255] | [0, 255] | Phiên bản đơn giản hơn |
| Vùng tối vi điện cực | [0, 179] | [70, 255] | [0, 70] | `build_mask_color` trong `main()` |

**Lý do dùng S_min=70 cho vùng tối**: chỉ giữ vùng tối CÓ màu (chromatic dark),
tránh nhầm với bóng xám achromatic (S≈0) ở nền.

---

## 2. Xử lý hình thái học — `repair_mask`

### Giãn nở (Dilation) — kernel ellipse

```
A ⊕ B = { z | (B̂)z ∩ A ≠ ∅ }
```

- Kernel **ellipse 5×5** cho đường xanh: mô phỏng nhiễu quang học đẳng hướng, nối đoạn đứt.
- Kernel **ellipse 3×3** cho vùng tối: nhỏ hơn để tránh làm mờ biên chip.

### Đóng (Closing) — kernel rectangle

```
A • B = (A ⊕ B) ⊖ B
```

- Kernel **rect 5×5** cho đường xanh: lấp lỗ nhỏ trong contour dài.
- Kernel **rect 17×17** cho vùng tối chip: lấp lỗ hổng lớn hơn do mặt chip không đồng đều.

**Thứ tự dilate → close** là có chủ ý: vùng liên thông lớn hơn sau dilate giúp
MORPH_CLOSE hoạt động hiệu quả hơn (ít iteration hơn, không bỏ sót lỗ ở biên).

---

## 3. Phát hiện đường tham chiếu — `cluster_and_fit`

### Tại sao không dùng KMeans / DBSCAN

| Phương pháp | Vấn đề |
|---|---|
| KMeans | Giả sử cluster hình cầu. Với hai đường dài song song, centroids hội tụ ở giữa ảnh → gán nhầm |
| DBSCAN | O(n log n) Python-level loop → 80–150 ms/frame trên Pi 4B |
| **cv2.findContours** | O(W·H) C++ thuần, topo-correct, **~40–80× nhanh hơn DBSCAN** |

### Thuật toán `cluster_and_fit`

```
1. cv2.findContours(CHAIN_APPROX_NONE)  → tất cả connected components
2. Sort by contourArea desc; lấy top-2 vượt min_contour_area
3. Mỗi contour: reshape (N,1,2) → (N,2) → fit_line_from_points
```

### `fit_line_from_points` — nội suy OLS

```python
cv2.fitLine(pts, cv2.DIST_L2, 0, 0.001, 0.001)
# → (vx, vy, x0, y0) tham số đường thẳng P(t) = P0 + t·d
```

Sau đó gọi `_canonicalize(vx, vy)` để chuẩn hóa chiều vectơ (xem mục 5).

---

## 4. RANSAC nội suy cạnh chip — `ransac_one_line`

### So sánh với phiên bản gốc

| | Phiên bản gốc | v4 (hiện tại) |
|---|---|---|
| Tính khoảng cách | `np.linalg.svd` per iteration | Cross-product 2D vectorised |
| Độ phức tạp | O(n²) per iter | O(n) per iter |
| SVD | Mỗi vòng lặp | Chỉ 1 lần trên winning set |
| Tốc độ | baseline | **~10–15×** nhanh hơn |

### Công thức khoảng cách vuông góc vectorised

```python
# _orthogonal_distances_vec(points, anchor, direction):
diff = points - anchor            # (N, 2)
dist = |diff[:,0]*dy - diff[:,1]*dx|    # 2D cross product
```

Tương đương toán học với khoảng cách từ điểm đến đường thẳng:

```
d(P, L) = |(P − A) × d̂|  (scalar cross product trong 2D)
```

### Thuật toán tổng thể

```
for i in range(N=150):
    Chọn ngẫu nhiên 2 điểm (seed=0, reproducible)
    direction = normalize(p2 − p1)
    dists = _orthogonal_distances_vec(points, p1, direction)
    inliers = dists < ε=2px
    Lưu mask nếu count(inliers) > best

Tái nội suy SVD trên winning inlier set (1 lần duy nhất)
```

### Chọn cặp cạnh song song — `_best_parallel_pair`

```
score = separation / mean_extent
```

Chọn cặp có score cao nhất trong số các cặp có `|angle_diff| < 15°`.
Score ưu tiên hai cạnh có khoảng cách rộng và chiều dài dài → đúng là hai cạnh dài đối diện.

---

## 5. Chuẩn hóa vectơ — `_canonicalize`

RANSAC và SVD trả về vectơ đơn vị **vô hướng**: cả `+d` và `−d` đều hợp lệ.
Nếu không chuẩn hóa, đường trung tâm ảo sẽ "lật" ngẫu nhiên giữa các frame.

### Quy tắc

```python
def _canonicalize(vx, vy):
    if |vy| >= |vx|:          # near-vertical
        if vy < 0: flip
    else:                      # near-horizontal
        if vx < 0: flip
```

Kết quả: `vy > 0` (near-vertical) hoặc `vx > 0` (near-horizontal) — **bất biến frame-to-frame**.

---

## 6. Đường trung tâm ảo ổn định — `build_midline_from_pair` (v4)

### Vấn đề cũ (trước v4)

Chỉ dùng `if dot(d1, d2) < 0: d2 = −d2` để align d2 theo d1.
Nếu **d1 tự lật** (RANSAC trả về `−d1` thay `+d1`), d2 cũng bị kéo theo → cả avg bị lật.

### Giải pháp v4 (3 bước)

```python
# Bước 1: Canonical hóa d1 về hemisphere tuyệt đối
d1x, d1y = _canonicalize(d1[0], d1[1])
d1 = np.array([d1x, d1y])

# Bước 2: Align d2 theo d1 đã ổn định
if np.dot(d1, d2) < 0:
    d2 = -d2

# Bước 3: Trung bình + canonical hóa kết quả
dir_avg = normalize(d1 + d2)
vx, vy  = _canonicalize(dir_avg[0], dir_avg[1])
```

### `_sort_pair_by_x`

```python
sorted(pair, key=lambda ln: (ln["centroid"][0], ln["centroid"][1]))
```

Đảm bảo `pair[0]` luôn là cạnh **trái** và `pair[1]` luôn là cạnh **phải** mỗi frame,
bất kể RANSAC phát hiện chúng theo thứ tự nào.

---

## 7. Sai lệch hình học — `compute_metrics`

### Sai lệch góc Δθ (vectorised)

```python
cross = vx_vcl * vy_blue - vy_vcl * vx_blue   # array
dot   = vx_vcl * vx_blue + vy_vcl * vy_blue
delta = np.degrees(np.arctan2(cross, dot))
# chuẩn hóa: >90° → -180°, <-90° → +180°
avg_angle = delta.mean()
```

Dùng `atan2` thay `arccos` để tránh singularity khi `vx ≈ 0` hoặc `vy ≈ 0`.

### Sai lệch khoảng cách Δd (vectorised)

```python
# signed_distance_px(VCL, blue):
dist = vy_blue*(x_vcl - x_blue) - vx_blue*(y_vcl - y_blue)
avg_dist = dists.mean()
```

Giá trị dương: VCL lệch theo một chiều; âm: chiều ngược lại.

### Quy đổi px → µm

```python
SCALE_UM_PER_PX = 10_000 / 300  # ≈ 33.33 µm/px
um = px * SCALE_UM_PER_PX
```

---

## 8. Bộ điều khiển PID rời rạc

### Phương trình

```
P(k) = Kp × e(k)
I(k) = Ki × Σ e(j)·Δt_j     (clamp ∈ [−5000, +5000])
D(k) = Kd × (e(k) − e(k−1)) / Δt_k    (Kd=0 → tắt)
u(k) = clip(P+I+D, −150000, +150000)
```

Trong `main()`: **`control = −pid.update(avg_dist)`** — dấu âm để đổi chiều tín hiệu điều khiển
(lệch dương → cần dịch chuyển ngược chiều dương).

### Tham số

| Tham số | Giá trị | Lý do |
|---|---|---|
| Kp = 0.2 | Đáp ứng nhanh mà không vọt lố |
| Ki = 0.01 | Triệt sai lệch tĩnh |
| Kd = 0.0 | Tắt — khuếch đại nhiễu camera nhiều hơn lợi ích |
| integral_limit = 5 000 | Giới hạn tích lũy khi mất tín hiệu |
| output_limit = 150 000 | Bảo vệ hành trình cơ học |

### Anti-windup

Khi không nhận diện được đối tượng: `pid.reset()` xóa toàn bộ trạng thái.
Khi nhận diện lại: PID bắt đầu từ trạng thái sạch, tránh "giật" đột ngột.

---

## 9. Giao thức Serial ACK — `SerialSender`

### Stop-and-wait

```
PC ─── "<N>b\n" ──────────────────────► Arduino
                                         (ISR Timer1: N xung STEP)
PC ◄── "Moved: Nb\n" ─────────────────── Arduino
PC ◄── "OK\n" ────────────────────────── Arduino
PC gửi lệnh tiếp theo (hoặc timeout 10s)
```

### Thread model

```
Main thread          │  ACK worker thread (_ack_worker)
─────────────────────┼──────────────────────────────────────
compute_metrics      │  wait(event, timeout=0.5s)
pid.update           │  read pending_um
sender.update(val) ──┼──set event
                     │  ser.write("<N>b\n")
                     │  loop readline until "OK" or timeout
main loop continue   │  clear pending, ready for next
```

Worker thread chạy daemon → tự kết thúc khi process thoát.

### Quy đổi µm → bước

```python
N = round(px_to_um(avg_dist) / 1.0)   # d_step = 1 µm/vi-bước
msg = f"{N}b"
```

Firmware nhận `<N>b\n`, kiểm tra ký tự cuối là `'b'`, tách số N, gọi `move_steps(N, send_ack=true)`.

---

## 10. Vẽ đồ thị PID response

Sau khi thoát vòng lặp chính (nhấn `q`), nếu `time_log` không rỗng:

```python
ax.plot(time_log, error_log, color="steelblue", label="Sai lệch thực tế")
ax.axhline(y=0.0, color="red", linestyle="--", label="Setpoint = 0")
# Box PID params (Kp/Ki/Kd) ở góc 0.98, 0.97 axes
fig.savefig("pid_response.png", dpi=150)
```

Có thể tái tạo đồ thị từ CSV bằng `scripts/plot_results.py`.
