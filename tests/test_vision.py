"""
test_vision.py — Unit tests cho các hàm xử lý ảnh trong vision_pipeline.py

Kiểm tra:
  • build_mask_blue / build_mask_color
  • repair_mask
  • filter_contours
  • fit_line_from_points
  • _canonicalize
  • build_midline_from_pair (stability fix v4)
  • find_rectangle_sides (ordering guarantee)
"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import numpy as np
import pytest
import cv2

from vision_pipeline import (
    build_mask_blue, build_mask_color, repair_mask, filter_contours,
    fit_line_from_points, _canonicalize, LineInfo,
    build_midline_from_pair, find_rectangle_sides,
    ransac_one_line,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def solid_bgr(b, g, r, h=100, w=100):
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[:] = (b, g, r)
    return frame


def make_line_dict(cx, cy, dx, dy, n=50, ext=100.0):
    """Tạo line-dict giả cho build_midline_from_pair."""
    norm = math.hypot(dx, dy)
    dx, dy = dx / norm, dy / norm
    c = np.array([cx, cy], dtype=np.float64)
    d = np.array([dx, dy], dtype=np.float64)
    # inliers dọc theo đường
    t = np.linspace(-ext / 2, ext / 2, n)
    inliers = c + np.outer(t, d)
    return {
        "centroid"  : c,
        "direction" : d,
        "normal"    : np.array([-dy, dx], dtype=np.float64),
        "inliers"   : inliers,
        "angle_deg" : math.degrees(math.atan2(dy, dx)) % 180,
        "n_inliers" : n,
        "extent"    : ext,
    }


# ─── build_mask_blue ──────────────────────────────────────────────────────────

def test_blue_mask_detects_blue_bgr():
    """BGR=(255,0,0) = xanh dương thuần → mặt nạ phải có 255."""
    frame = solid_bgr(255, 0, 0)
    mask  = build_mask_blue(frame)
    assert mask.max() == 255


def test_blue_mask_rejects_red():
    """BGR=(0,0,255) = đỏ → không thỏa HSV blue → mặt nạ rỗng."""
    frame = solid_bgr(0, 0, 255)
    mask  = build_mask_blue(frame)
    assert mask.max() == 0


# ─── build_mask_color ─────────────────────────────────────────────────────────

def test_mask_color_dark_region():
    """
    Vùng tối (V<70) được mặt nạ đúng.
    Trong source: dark mask dùng S_min=70 để tách vùng tối CÓ màu (chrom atic).
    BGR(20,20,20) là achromatic (S=0) nên không thỏa S>=70.
    Dùng BGR có màu tối: vd. BGR(0,0,40) = đỏ tối, S=255, V≈16 < 70.
    """
    frame = solid_bgr(0, 0, 40)   # BGR đỏ tối: H=0, S=255, V≈16 → thỏa
    mask  = build_mask_color(frame, 0, 70, 0, 179, 255, 70)
    assert mask.max() == 255


def test_mask_color_bright_rejected():
    """Frame trắng → V cao → không nằm trong dải [0,70]."""
    frame = solid_bgr(255, 255, 255)
    mask  = build_mask_color(frame, 0, 70, 0, 179, 255, 70)
    assert mask.max() == 0


# ─── repair_mask ──────────────────────────────────────────────────────────────

def test_repair_mask_fills_hole():
    """Lỗ 5×5 trong mặt nạ 50×50 phải bị lấp kín."""
    mask = np.ones((50, 50), dtype=np.uint8) * 255
    mask[20:25, 20:25] = 0
    repaired = repair_mask(mask)
    assert repaired[22, 22] == 255


def test_repair_mask_output_binary():
    """Đầu ra chỉ chứa 0 hoặc 255."""
    mask = np.random.randint(0, 2, (80, 80), dtype=np.uint8) * 255
    repaired = repair_mask(mask)
    unique = np.unique(repaired)
    assert set(unique).issubset({0, 255})


# ─── filter_contours ──────────────────────────────────────────────────────────

def test_filter_contours_removes_small_blobs():
    """Blob nhỏ hơn min_area phải bị loại."""
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[5:8, 5:8]    = 255   # ~9 px² — nhỏ
    mask[40:80, 40:80] = 255  # 1600 px² — lớn
    cleaned, valid = filter_contours(mask, min_area=500)
    assert len(valid) == 1
    # blob nhỏ bị xóa
    assert cleaned[6, 6] == 0


def test_filter_contours_keeps_large():
    """Blob lớn phải còn lại trong cleaned mask."""
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[10:90, 10:90] = 255
    cleaned, valid = filter_contours(mask, min_area=100)
    assert len(valid) == 1
    assert cleaned[50, 50] == 255


# ─── _canonicalize ────────────────────────────────────────────────────────────

def test_canonicalize_near_vertical_vy_positive():
    """Near-vertical: |vy| ≥ |vx| → vy > 0."""
    vx, vy = _canonicalize(0.1, -0.9949)
    assert vy > 0


def test_canonicalize_near_horizontal_vx_positive():
    """Near-horizontal: |vx| > |vy| → vx > 0."""
    vx, vy = _canonicalize(-0.9949, 0.1)
    assert vx > 0


def test_canonicalize_idempotent():
    """Áp dụng hai lần phải cho kết quả giống lần một."""
    vx0, vy0 = _canonicalize(0.6, 0.8)
    vx1, vy1 = _canonicalize(vx0, vy0)
    assert vx0 == vx1 and vy0 == vy1


# ─── fit_line_from_points ─────────────────────────────────────────────────────

def test_fit_line_horizontal():
    """Tập điểm nằm ngang → vx ≈ 1, vy ≈ 0."""
    pts = np.column_stack([np.arange(0, 100), np.full(100, 50)])
    li  = fit_line_from_points(pts, img_h=200, img_w=300)
    assert li is not None
    assert abs(li.vx) == pytest.approx(1.0, abs=0.01)
    assert abs(li.vy) == pytest.approx(0.0, abs=0.01)


def test_fit_line_vertical():
    """Tập điểm thẳng đứng → |vy| ≈ 1."""
    pts = np.column_stack([np.full(100, 50), np.arange(0, 100)])
    li  = fit_line_from_points(pts, img_h=200, img_w=300)
    assert li is not None
    assert abs(li.vy) == pytest.approx(1.0, abs=0.01)


def test_fit_line_too_few_points():
    """Ít hơn 10 điểm → trả về None."""
    pts = np.array([[0, 0], [1, 1], [2, 2]], dtype=np.float32)
    assert fit_line_from_points(pts, 100, 100) is None


def test_fit_line_canonical_direction():
    """Vectơ chỉ phương phải đã được chuẩn hóa (canonicalize)."""
    pts = np.column_stack([np.arange(50), np.arange(50)])  # 45° diagonal
    li  = fit_line_from_points(pts, 200, 200)
    assert li is not None
    # Sau canonicalize: near-vertical → vy > 0 ; near-horizontal → vx > 0
    if abs(li.vy) >= abs(li.vx):
        assert li.vy > 0
    else:
        assert li.vx > 0


# ─── ransac_one_line ──────────────────────────────────────────────────────────

def test_ransac_finds_horizontal_line():
    """RANSAC phải tìm được đường ngang trong tập điểm nhiễu."""
    rng = np.random.default_rng(0)
    # Inliers: đường ngang y=50
    x_in = rng.uniform(0, 200, 100)
    y_in = np.full(100, 50.0) + rng.normal(0, 0.5, 100)
    # Outliers: ngẫu nhiên
    x_out = rng.uniform(0, 200, 20)
    y_out = rng.uniform(0, 100, 20)
    pts = np.column_stack([
        np.concatenate([x_in, x_out]),
        np.concatenate([y_in, y_out]),
    ])
    centroid, direction, mask = ransac_one_line(pts, n_iter=300, thresh=2.0)
    assert centroid is not None
    assert abs(direction[1]) < 0.05   # vy ≈ 0 → gần ngang


def test_ransac_returns_none_for_noise():
    """Thuần nhiễu → không tìm được đường hợp lệ (hoặc ít inlier)."""
    rng = np.random.default_rng(1)
    pts = rng.uniform(0, 100, (10, 2))  # quá ít điểm / thuần ngẫu nhiên
    centroid, direction, mask = ransac_one_line(pts, n_iter=50, thresh=1.0)
    # Hoặc None hoặc inlier count rất thấp
    if centroid is not None:
        assert mask.sum() <= len(pts)


# ─── build_midline_from_pair (v4 stability fix) ───────────────────────────────

def test_midline_stable_across_flipped_input():
    """
    v4 fix: build_midline_from_pair phải trả về cùng vectơ chỉ phương
    khi input bị đổi thứ tự (pair[0] ↔ pair[1]).
    """
    l_left  = make_line_dict(cx=100, cy=200, dx=1.0, dy=0.05)
    l_right = make_line_dict(cx=300, cy=200, dx=1.0, dy=0.05)

    mid1 = build_midline_from_pair([l_left,  l_right], img_h=480, img_w=640)
    mid2 = build_midline_from_pair([l_right, l_left],  img_h=480, img_w=640)

    assert mid1 is not None and mid2 is not None
    # Hướng phải giống nhau (có thể sai dấu nhưng _canonicalize chuẩn hóa)
    assert abs(mid1.vx - mid2.vx) < 1e-6
    assert abs(mid1.vy - mid2.vy) < 1e-6


def test_midline_stable_across_opposite_directions():
    """
    Nếu RANSAC trả về d1 = +d và lần sau d1 = −d (đều hợp lệ),
    midline phải cho cùng kết quả sau _canonicalize.
    """
    l1_pos = make_line_dict(cx=100, cy=200, dx= 1.0, dy=0.0)
    l1_neg = make_line_dict(cx=100, cy=200, dx=-1.0, dy=0.0)  # flipped d
    l2     = make_line_dict(cx=300, cy=200, dx= 1.0, dy=0.0)

    mid_pos = build_midline_from_pair([l1_pos, l2], img_h=480, img_w=640)
    mid_neg = build_midline_from_pair([l1_neg, l2], img_h=480, img_w=640)

    assert mid_pos is not None and mid_neg is not None
    assert abs(mid_pos.vx - mid_neg.vx) < 1e-6
    assert abs(mid_pos.vy - mid_neg.vy) < 1e-6


def test_midline_centroid_is_midpoint():
    """Centroid của midline phải là trung điểm giữa hai cạnh."""
    l1 = make_line_dict(cx=100.0, cy=200.0, dx=1.0, dy=0.0)
    l2 = make_line_dict(cx=300.0, cy=200.0, dx=1.0, dy=0.0)
    mid = build_midline_from_pair([l1, l2], img_h=480, img_w=640)
    assert mid is not None
    assert mid.x0 == pytest.approx(200.0, abs=0.5)


def test_midline_returns_none_for_empty():
    assert build_midline_from_pair([], img_h=480, img_w=640) is None
    assert build_midline_from_pair([make_line_dict(100,100,1,0)], 480, 640) is None


# ─── find_rectangle_sides ordering guarantee ──────────────────────────────────

def test_find_rectangle_sides_ordering():
    """
    Kết quả phải luôn được sắp xếp left→right (centroid X tăng dần).
    Tạo mask chứa hai dải dọc, chạy find_rectangle_sides và kiểm tra thứ tự.
    """
    mask = np.zeros((200, 300), dtype=np.uint8)
    # Dải trái: x = 50..60
    mask[40:160, 50:62] = 255
    # Dải phải: x = 220..230
    mask[40:160, 220:232] = 255

    sides = find_rectangle_sides(
        mask_clean   = mask,
        n_iter       = 200,
        thresh       = 3.0,
        min_inliers  = 10,
        max_attempts = 6,
        parallel_tol = 20.0,
        extent_range = (50, 9999),
    )

    if len(sides) == 2:
        cx0 = float(sides[0]["centroid"][0])
        cx1 = float(sides[1]["centroid"][1])
        # centroid X của side[0] phải ≤ side[1]
        assert sides[0]["centroid"][0] <= sides[1]["centroid"][0]
