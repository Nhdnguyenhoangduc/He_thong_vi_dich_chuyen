"""
metrics.py — Tính sai lệch hình học Δd và Δθ

Δd  : khoảng cách vuông góc có dấu từ đường trung tâm ảo đến đường tham chiếu (µm)
Δθ  : góc có dấu giữa trục chip và trục tham chiếu (độ), chuẩn hóa về (-90°,+90°]

Đơn vị chuyển đổi:  L_µm = L_px × SCALE_UM_PER_PX
"""

import math
from typing import Optional, Tuple

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import SCALE_UM_PER_PX

LineParams = Tuple[float, float, float, float]   # (vx, vy, x0, y0)


# ─── Sai lệch vị trí ──────────────────────────────────────────────────────────

def signed_distance_px(
    ref:    LineParams,
    center: Tuple[float, float],
) -> float:
    """
    Hình chiếu có dấu của vectơ (A→P) lên pháp tuyến đường tham chiếu.

        Δd = n̂_r · (P_c - A_r)
           = -vy_r*(x_c-x0_r) + vx_r*(y_c-y0_r)

    Dấu dương: P_c ở phía chiều dương của n̂_r.
    """
    vx_r, vy_r, x0_r, y0_r = ref
    xc, yc = center
    return -vy_r * (xc - x0_r) + vx_r * (yc - y0_r)


def mean_signed_distance_px(
    ref1:   LineParams,
    ref2:   LineParams,
    center: Tuple[float, float],
) -> float:
    """Trung bình Δd trên hai đường tham chiếu song song."""
    d1 = signed_distance_px(ref1, center)
    d2 = signed_distance_px(ref2, center)
    return (d1 + d2) / 2.0


# ─── Sai lệch góc ─────────────────────────────────────────────────────────────

def signed_angle_deg(
    chip_line: LineParams,
    ref_line:  LineParams,
) -> float:
    """
    Góc có dấu Δθ giữa đường trục chip và đường tham chiếu.

        sin(Δθ) = d1 × d2  (tích có hướng 2D)
        cos(Δθ) = d1 · d2

        Δθ = atan2(sin, cos), chuẩn hóa về (-90°, +90°]

    Sử dụng atan2 thay cho arctan để tránh nhập nhằng góc phần tư.
    """
    vx1, vy1 = chip_line[0], chip_line[1]
    vx2, vy2 = ref_line[0],  ref_line[1]

    cross = vx1 * vy2 - vy1 * vx2   # sin(Δθ)
    dot   = vx1 * vx2 + vy1 * vy2   # cos(Δθ)

    angle = math.degrees(math.atan2(cross, dot))

    # Chuẩn hóa: đường thẳng vô hướng nên ánh xạ về (-90°, +90°]
    if angle > 90.0:
        angle -= 180.0
    elif angle < -90.0:
        angle += 180.0

    return angle


# ─── Quy đổi đơn vị ───────────────────────────────────────────────────────────

def px_to_um(distance_px: float) -> float:
    """Chuyển đổi khoảng cách từ pixel sang micromet."""
    return distance_px * SCALE_UM_PER_PX


def um_to_px(distance_um: float) -> float:
    """Chuyển đổi khoảng cách từ micromet sang pixel."""
    return distance_um / SCALE_UM_PER_PX


# ─── API tổng hợp ─────────────────────────────────────────────────────────────

def compute_metrics(
    ref1:     LineParams,
    ref2:     LineParams,
    center_line: LineParams,
) -> Tuple[float, float]:
    """
    Tính toán đầy đủ sai lệch hình học.

    Args:
        ref1, ref2      : hai đường tham chiếu xanh dương
        center_line     : đường trung tâm ảo của tấm vi điện cực

    Returns:
        (delta_d_um, delta_theta_deg)
            delta_d_um       : sai lệch khoảng cách có dấu (µm)
            delta_theta_deg  : sai lệch góc có dấu (độ)
    """
    center_pt = (center_line[2], center_line[3])

    delta_d_px = mean_signed_distance_px(ref1, ref2, center_pt)
    delta_d_um = px_to_um(delta_d_px)

    # Sử dụng ref1 làm trục tham chiếu góc
    delta_theta = signed_angle_deg(center_line, ref1)

    return delta_d_um, delta_theta
