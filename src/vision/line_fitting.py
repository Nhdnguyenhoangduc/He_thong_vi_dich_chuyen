"""
line_fitting.py — Nội suy đường thẳng OLS cho hai đường tham chiếu màu xanh

Sử dụng cv2.fitLine (Orthogonal Least Squares) — phù hợp với đường liên tục,
ít outlier.  Kết quả: điểm neo (x0,y0) + vectơ chỉ phương (vx,vy).
"""

import cv2
import numpy as np
from typing import Optional, List, Tuple

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import MIN_CONTOUR_AREA

# Kiểu dữ liệu: (vx, vy, x0, y0)
LineParams = Tuple[float, float, float, float]


def _normalize_direction(vx: float, vy: float) -> Tuple[float, float]:
    """
    Chuẩn hóa chiều vectơ chỉ phương sao cho vx ≥ 0
    (nếu vx == 0 thì vy > 0).
    Đảm bảo tính nhất quán giữa các khung hình liên tiếp.
    """
    if vx < 0 or (vx == 0 and vy < 0):
        vx, vy = -vx, -vy
    return vx, vy


def fit_line_from_contour(contour: np.ndarray) -> Optional[LineParams]:
    """
    Nội suy đường thẳng OLS từ một contour.

    Args:
        contour: mảng điểm (N,1,2) từ cv2.findContours.

    Returns:
        (vx, vy, x0, y0) hoặc None nếu contour không đủ điểm.
    """
    pts = contour.reshape(-1, 2).astype(np.float32)
    if len(pts) < 2:
        return None

    result = cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01)
    vx, vy, x0, y0 = float(result[0]), float(result[1]), float(result[2]), float(result[3])
    vx, vy = _normalize_direction(vx, vy)
    return vx, vy, x0, y0


def extend_line_to_frame(
    vx: float, vy: float, x0: float, y0: float,
    width: int, height: int
) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """
    Kéo dài đường thẳng tham số P(t)=P0+t*d đến biên ảnh.

    Returns:
        (pt1, pt2) — hai điểm cuối trên biên ảnh (pixel).
    """
    pts = []
    # Biên trái x=0
    if abs(vx) > 1e-9:
        t = (0 - x0) / vx
        y = y0 + t * vy
        if 0 <= y <= height:
            pts.append((0, int(y)))
    # Biên phải x=width
    if abs(vx) > 1e-9:
        t = (width - x0) / vx
        y = y0 + t * vy
        if 0 <= y <= height:
            pts.append((width, int(y)))
    # Biên trên y=0
    if abs(vy) > 1e-9:
        t = (0 - y0) / vy
        x = x0 + t * vx
        if 0 <= x <= width:
            pts.append((int(x), 0))
    # Biên dưới y=height
    if abs(vy) > 1e-9:
        t = (height - y0) / vy
        x = x0 + t * vx
        if 0 <= x <= width:
            pts.append((int(x), height))

    # Lấy hai điểm xa nhau nhất
    if len(pts) < 2:
        return (int(x0) - 200, int(y0)), (int(x0) + 200, int(y0))
    pt1, pt2 = pts[0], pts[-1]
    return pt1, pt2


def fit_reference_lines(
    mask: np.ndarray,
) -> Optional[Tuple[LineParams, LineParams]]:
    """
    Tìm hai đường tham chiếu xanh dương từ mặt nạ nhị phân.

    Returns:
        (line1, line2) sắp xếp theo centroid y tăng dần (trên → dưới),
        hoặc None nếu không tìm đủ hai đường.
    """
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

    # Lọc theo diện tích và sắp xếp
    valid = [c for c in contours if cv2.contourArea(c) >= MIN_CONTOUR_AREA]
    if len(valid) < 2:
        return None

    # Chọn hai contour lớn nhất
    valid.sort(key=cv2.contourArea, reverse=True)
    top2 = valid[:2]

    lines = []
    for c in top2:
        lp = fit_line_from_contour(c)
        if lp is None:
            return None
        lines.append(lp)

    # Sắp xếp theo y0 (trên → dưới)
    lines.sort(key=lambda l: l[3])
    return lines[0], lines[1]
