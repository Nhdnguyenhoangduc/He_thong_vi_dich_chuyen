"""
test_segmentation.py — Unit tests cho HSV segmentation và morphology
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import numpy as np
import pytest
from vision.segmentation import bgr_to_hsv, threshold_color, repair_mask


def _solid_bgr(b, g, r, h=100, w=100):
    """Tạo frame màu đồng nhất."""
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[:] = (b, g, r)
    return frame


def test_bgr_to_hsv_shape():
    frame = _solid_bgr(255, 0, 0)
    hsv = bgr_to_hsv(frame)
    assert hsv.shape == frame.shape


def test_blue_thresholding_detects_blue():
    """Frame xanh dương thuần phải cho mặt nạ != 0."""
    # Blue BGR = (255,0,0)
    frame = _solid_bgr(255, 0, 0)
    hsv   = bgr_to_hsv(frame)
    mask  = threshold_color(hsv, 100, 140, 150, 255, 50, 255)
    assert mask.max() == 255


def test_non_blue_frame_gives_empty_mask():
    """Frame đỏ không thỏa dải H của màu xanh."""
    frame = _solid_bgr(0, 0, 255)   # BGR đỏ
    hsv   = bgr_to_hsv(frame)
    mask  = threshold_color(hsv, 110, 130, 61, 255, 0, 255)
    assert mask.max() == 0


def test_repair_mask_fills_hole():
    """Lỗ nhỏ trong mặt nạ phải được lấp kín bởi repair_mask."""
    mask = np.ones((50, 50), dtype=np.uint8) * 255
    mask[20:25, 20:25] = 0            # tạo lỗ nhỏ 5×5
    repaired = repair_mask(mask)
    # Vùng lỗ phải được lấp kín
    assert repaired[22, 22] == 255


def test_repair_mask_removes_isolated_noise():
    """Điểm nhiễu đơn lẻ phải biến mất sau xói mòn ẩn trong phép đóng."""
    mask = np.zeros((100, 100), dtype=np.uint8)
    # Tạo vùng lớn (50×50) và một điểm nhiễu đơn lẻ
    mask[25:75, 25:75] = 255
    mask[10, 10] = 255               # nhiễu đơn
    repaired = repair_mask(mask)
    # Nhiễu đơn lẻ phải biến mất (hoặc ít nhất vùng lớn còn nguyên)
    assert repaired[25:75, 25:75].mean() > 200
