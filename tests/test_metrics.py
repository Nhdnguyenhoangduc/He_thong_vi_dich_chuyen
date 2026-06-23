"""
test_metrics.py — Unit tests cho signed_angle_deg, signed_distance_px, compute_metrics
Dựa trên logic thực tế trong vision_pipeline.py
"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from vision_pipeline import (
    LineInfo, signed_angle_deg, signed_distance_px,
    px_to_um, compute_metrics, SCALE_UM_PER_PX,
)


def make_line(vx, vy, x0=0.0, y0=0.0):
    """Helper: tạo LineInfo với pt1/pt2 giả."""
    norm = math.hypot(vx, vy)
    vx, vy = vx / norm, vy / norm
    return LineInfo(pt1=(0, 0), pt2=(100, 100), vx=vx, vy=vy, x0=x0, y0=y0)


# ─── signed_angle_deg ─────────────────────────────────────────────────────────

def test_zero_angle_parallel_lines():
    """Hai đường song song → góc = 0."""
    l1 = make_line(1.0, 0.0, 0.0, 100.0)
    l2 = make_line(1.0, 0.0, 0.0, 200.0)
    assert signed_angle_deg(l1, l2) == pytest.approx(0.0, abs=1e-9)


def test_angle_45():
    """Chip nghiêng 45° so với tham chiếu."""
    ref  = make_line(1.0, 0.0)
    chip = make_line(1.0, 1.0)  # 45°
    angle = signed_angle_deg(chip, ref)
    assert abs(angle) == pytest.approx(45.0, abs=0.01)


def test_angle_normalized_in_range():
    """Góc chuẩn hóa phải nằm trong (−90°, +90°]."""
    for deg in [-89, -45, 0, 45, 89]:
        r = math.radians(deg)
        l1 = make_line(math.cos(r), math.sin(r))
        l2 = make_line(1.0, 0.0)
        a = signed_angle_deg(l1, l2)
        assert -90.0 <= a <= 90.0


def test_angle_sign_nonzero():
    """Line1 nghiêng so với line2 → góc ≠ 0."""
    l1 = make_line(1.0, 0.2)   # hơi nghiêng lên
    l2 = make_line(1.0, 0.0)   # ngang
    # signed_angle_deg(l1, l2): cross = vx1*vy2 - vy1*vx2 = 1*0 - 0.196*1 < 0
    # → góc âm (l1 nghiêng ngược chiều clock so với l2)
    assert signed_angle_deg(l1, l2) != pytest.approx(0.0, abs=0.5)
    # Đảo chiều: signed_angle_deg(l2, l1) phải ngược dấu
    assert signed_angle_deg(l1, l2) * signed_angle_deg(l2, l1) < 0


# ─── signed_distance_px ───────────────────────────────────────────────────────

def test_zero_distance_same_centroid():
    """Hai đường cùng centroid → khoảng cách = 0."""
    l1 = make_line(1.0, 0.0, 100.0, 100.0)
    l2 = make_line(1.0, 0.0, 100.0, 100.0)
    assert signed_distance_px(l1, l2) == pytest.approx(0.0, abs=1e-9)


def test_distance_magnitude_horizontal():
    """
    line2 nằm ngang tại y=100, line1 centroid tại y=50.
    Khoảng cách theo phương thẳng đứng = 50 px.
    """
    l1 = make_line(1.0, 0.0, 0.0,  50.0)   # chip centroid y=50
    l2 = make_line(1.0, 0.0, 0.0, 100.0)   # ref  centroid y=100
    # vy2=0, vx2=1 → dist = vy2*(x0_1-x0_2) - vx2*(y0_1-y0_2)
    #              = 0 - 1*(50-100) = 50
    d = signed_distance_px(l1, l2)
    assert abs(d) == pytest.approx(50.0, abs=0.1)


def test_distance_sign_flip():
    """Đổi vị trí hai đường → dấu khoảng cách đổi."""
    l1 = make_line(1.0, 0.0, 0.0, 150.0)
    l2 = make_line(1.0, 0.0, 0.0, 100.0)
    d_forward = signed_distance_px(l1, l2)
    d_reverse = signed_distance_px(l2, l1)
    assert d_forward * d_reverse < 0   # khác dấu


# ─── px_to_um ─────────────────────────────────────────────────────────────────

def test_scale_factor():
    """300 px × SCALE_UM_PER_PX ≈ 10 000 µm."""
    assert px_to_um(300.0) == pytest.approx(10_000.0, rel=1e-6)


def test_px_to_um_zero():
    assert px_to_um(0.0) == 0.0


# ─── compute_metrics ──────────────────────────────────────────────────────────

def test_compute_metrics_empty_list():
    """Không có blue line → trả về (None, None)."""
    vcl = make_line(1.0, 0.0)
    a, d = compute_metrics(vcl, [])
    assert a is None and d is None


def test_compute_metrics_parallel_zero_angle():
    """VCL song song với blue lines → avg_angle ≈ 0."""
    vcl   = make_line(1.0, 0.0, 0.0, 200.0)
    blue1 = make_line(1.0, 0.0, 0.0, 100.0)
    blue2 = make_line(1.0, 0.0, 0.0, 300.0)
    avg_angle, avg_dist = compute_metrics(vcl, [blue1, blue2])
    assert avg_angle == pytest.approx(0.0, abs=1e-6)


def test_compute_metrics_avg_dist():
    """avg_dist phải bằng trung bình của hai khoảng cách riêng lẻ."""
    vcl   = make_line(1.0, 0.0, 0.0, 200.0)
    blue1 = make_line(1.0, 0.0, 0.0, 100.0)
    blue2 = make_line(1.0, 0.0, 0.0, 300.0)
    avg_angle, avg_dist = compute_metrics(vcl, [blue1, blue2])
    d1 = signed_distance_px(vcl, blue1)
    d2 = signed_distance_px(vcl, blue2)
    assert avg_dist == pytest.approx((d1 + d2) / 2.0, abs=1e-9)
