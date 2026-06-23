"""
visualization.py — Vẽ overlay lên frame camera

Hiển thị:
  - Hai đường tham chiếu xanh dương (màu cyan)
  - Hai cạnh chip (màu vàng) và đường trung tâm ảo (màu đỏ)
  - Giá trị Δd, Δθ và tín hiệu PID lên góc trái trên
"""

import cv2
import numpy as np
from typing import Optional, Tuple

LineParams = Tuple[float, float, float, float]


def draw_line(
    frame: np.ndarray,
    line: LineParams,
    color: Tuple[int, int, int],
    thickness: int = 2,
    label: str = "",
) -> None:
    """Vẽ đường thẳng kéo dài đến biên ảnh."""
    from .visualization import _extend
    h, w = frame.shape[:2]
    pt1, pt2 = _extend(*line, w, h)
    cv2.line(frame, pt1, pt2, color, thickness)
    if label:
        mid = ((pt1[0] + pt2[0]) // 2, (pt1[1] + pt2[1]) // 2)
        cv2.putText(frame, label, mid, cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, color, 1, cv2.LINE_AA)


def _extend(vx, vy, x0, y0, w, h):
    """Kéo đường tham số đến biên ảnh (tái sử dụng logic từ line_fitting)."""
    pts = []
    for t in [(-x0 / vx) if abs(vx) > 1e-9 else None,
              ((w - x0) / vx) if abs(vx) > 1e-9 else None,
              (-y0 / vy) if abs(vy) > 1e-9 else None,
              ((h - y0) / vy) if abs(vy) > 1e-9 else None]:
        if t is None:
            continue
        px, py = int(x0 + t * vx), int(y0 + t * vy)
        if 0 <= px <= w and 0 <= py <= h:
            pts.append((px, py))
    if len(pts) < 2:
        return (int(x0) - 200, int(y0)), (int(x0) + 200, int(y0))
    return pts[0], pts[-1]


def draw_overlay(
    frame: np.ndarray,
    ref1:         Optional[LineParams],
    ref2:         Optional[LineParams],
    left_side:    Optional[LineParams],
    right_side:   Optional[LineParams],
    center_line:  Optional[LineParams],
    delta_d_um:   Optional[float] = None,
    delta_theta:  Optional[float] = None,
    u_um:         Optional[float] = None,
    n_step:       Optional[int]   = None,
) -> np.ndarray:
    """
    Vẽ toàn bộ overlay lên một bản sao của frame.

    Returns:
        Frame đã vẽ overlay (không chỉnh sửa in-place).
    """
    out = frame.copy()
    h, w = out.shape[:2]

    # Đường tham chiếu — cyan
    for ref in [ref1, ref2]:
        if ref is not None:
            pt1, pt2 = _extend(*ref, w, h)
            cv2.line(out, pt1, pt2, (255, 255, 0), 2)

    # Cạnh chip — vàng
    for side in [left_side, right_side]:
        if side is not None:
            pt1, pt2 = _extend(*side, w, h)
            cv2.line(out, pt1, pt2, (0, 200, 255), 1)

    # Đường trung tâm ảo — đỏ đậm
    if center_line is not None:
        pt1, pt2 = _extend(*center_line, w, h)
        cv2.line(out, pt1, pt2, (0, 0, 255), 2)
        # Vẽ centroid
        cx, cy = int(center_line[2]), int(center_line[3])
        cv2.circle(out, (cx, cy), 5, (0, 0, 255), -1)

    # HUD — góc trái trên
    lines_text = []
    if delta_d_um  is not None: lines_text.append(f"dd={delta_d_um:+.1f} um")
    if delta_theta is not None: lines_text.append(f"dth={delta_theta:+.3f} deg")
    if u_um        is not None: lines_text.append(f"u={u_um:+.1f} um")
    if n_step      is not None: lines_text.append(f"step={n_step:+d}")

    for i, txt in enumerate(lines_text):
        cv2.putText(out, txt, (10, 22 + i * 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 255, 200), 1, cv2.LINE_AA)

    return out
