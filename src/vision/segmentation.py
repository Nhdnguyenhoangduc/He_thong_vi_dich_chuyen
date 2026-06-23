"""
segmentation.py — Phân đoạn màu HSV và làm sạch hình thái học

Pipeline:
    BGR frame → HSV → threshold (3D) → repair_mask (dilate + close) → binary mask
"""

import cv2
import numpy as np
from typing import Tuple

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import (
    BLUE_H_MIN, BLUE_H_MAX, BLUE_S_MIN, BLUE_S_MAX, BLUE_V_MIN, BLUE_V_MAX,
    DARK_H_MIN, DARK_H_MAX, DARK_S_MIN, DARK_S_MAX, DARK_V_MIN, DARK_V_MAX,
    MORPH_DILATE_KSIZE, MORPH_CLOSE_KSIZE,
)


def bgr_to_hsv(frame: np.ndarray) -> np.ndarray:
    """Chuyển đổi frame BGR sang không gian HSV."""
    return cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)


def threshold_color(
    hsv: np.ndarray,
    h_min: int, h_max: int,
    s_min: int, s_max: int,
    v_min: int, v_max: int,
) -> np.ndarray:
    """
    Phân ngưỡng 3 chiều trên không gian HSV.

    Returns:
        Mặt nạ nhị phân (uint8, 0 hoặc 255).
    """
    lower = np.array([h_min, s_min, v_min], dtype=np.uint8)
    upper = np.array([h_max, s_max, v_max], dtype=np.uint8)
    return cv2.inRange(hsv, lower, upper)


def repair_mask(mask: np.ndarray) -> np.ndarray:
    """
    Làm sạch mặt nạ nhị phân bằng hình thái học:
      1. Giãn nở (ellipse 5×5) — nối đoạn đứt và giảm nhiễu quang học đẳng hướng.
      2. Đóng  (rect   5×5) — lấp lỗ hổng bên trong biên chip hình chữ nhật.

    Thứ tự giãn nở trước rồi mới đóng là có chủ ý (xem Chapter 3 báo cáo).
    """
    k_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, MORPH_DILATE_KSIZE)
    k_close  = cv2.getStructuringElement(cv2.MORPH_RECT,    MORPH_CLOSE_KSIZE)

    mask = cv2.dilate(mask, k_dilate, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k_close)
    return mask


def get_blue_mask(frame: np.ndarray) -> np.ndarray:
    """Trả về mặt nạ đã làm sạch cho hai đường tham chiếu xanh dương."""
    hsv  = bgr_to_hsv(frame)
    raw  = threshold_color(hsv,
                           BLUE_H_MIN, BLUE_H_MAX,
                           BLUE_S_MIN, BLUE_S_MAX,
                           BLUE_V_MIN, BLUE_V_MAX)
    return repair_mask(raw)


def get_dark_mask(frame: np.ndarray) -> np.ndarray:
    """Trả về mặt nạ đã làm sạch cho vùng tối của tấm vi điện cực."""
    hsv  = bgr_to_hsv(frame)
    raw  = threshold_color(hsv,
                           DARK_H_MIN, DARK_H_MAX,
                           DARK_S_MIN, DARK_S_MAX,
                           DARK_V_MIN, DARK_V_MAX)
    return repair_mask(raw)
