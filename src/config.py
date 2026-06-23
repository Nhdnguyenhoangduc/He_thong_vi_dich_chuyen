"""
config.py — Tham số hệ thống vi dịch chuyển

Chỉnh sửa file này để hiệu chuẩn lại hệ thống hoặc thay đổi cổng kết nối.
"""

# ─── Camera ────────────────────────────────────────────────────────────────────
CAMERA_INDEX    = 0          # Index thiết bị USB (Dino-Lite AM2111)
FRAME_WIDTH     = 640
FRAME_HEIGHT    = 480
TARGET_FPS      = 30

# ─── Hiệu chuẩn không gian ─────────────────────────────────────────────────────
# Đo: thước 10 mm xuất hiện 300 px trên ảnh → S = 10000/300 ≈ 33.33 µm/px
SCALE_UM_PER_PX: float = 10_000 / 300   # µm/pixel

# ─── Ngưỡng HSV — đường tham chiếu xanh dương ─────────────────────────────────
# OpenCV nén H về [0,179]  →  H=110 tương đương blue thuần
BLUE_H_MIN, BLUE_H_MAX = 110, 180
BLUE_S_MIN, BLUE_S_MAX = 61,  255
BLUE_V_MIN, BLUE_V_MAX = 0,   255

# ─── Ngưỡng HSV — vùng tối vi điện cực ────────────────────────────────────────
DARK_H_MIN, DARK_H_MAX = 0,  179
DARK_S_MIN, DARK_S_MAX = 70, 255
DARK_V_MIN, DARK_V_MAX = 0,  70

# ─── Hình thái học ─────────────────────────────────────────────────────────────
MORPH_DILATE_KSIZE = (5, 5)   # phần tử cấu trúc hình elip
MORPH_CLOSE_KSIZE  = (5, 5)   # phần tử cấu trúc hình chữ nhật

# ─── Lọc contour ───────────────────────────────────────────────────────────────
MIN_CONTOUR_AREA = 500         # px²  — loại bỏ nhiễu còn sót

# ─── RANSAC tìm cạnh chip ──────────────────────────────────────────────────────
RANSAC_ITERATIONS      = 150
RANSAC_INLIER_THRESH   = 2.0   # px
RANSAC_MAX_SIDES       = 6     # số lần tìm cạnh tối đa
RANSAC_PARALLEL_DEG    = 15.0  # ngưỡng kiểm tra song song (độ)

# ─── Bộ điều khiển PID ─────────────────────────────────────────────────────────
KP: float = 0.2
KI: float = 0.01
KD: float = 0.0
I_MAX: float   = 5_000.0       # µm  — kẹp tích phân anti-windup
U_MAX: float   = 150_000.0     # µm  — bão hòa đầu ra

TOLERANCE_UM: float = 15.0     # µm  — ngưỡng hội tụ

# ─── Serial / Arduino ──────────────────────────────────────────────────────────
SERIAL_PORT   = "COM3"         # Linux: "/dev/ttyACM0"
SERIAL_BAUD   = 115_200
ACK_TIMEOUT_S = 10.0           # giây

# ─── Cơ học ────────────────────────────────────────────────────────────────────
D_STEP_UM: float = 1.0         # µm/vi-bước  (p=2mm, 2000 vi-bước/vòng)
MOTOR_MAX_SPEED  = 35_000      # bước/giây
MOTOR_DEF_SPEED  = 8_000       # bước/giây
