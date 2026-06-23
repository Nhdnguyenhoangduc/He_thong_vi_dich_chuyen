"""
ransac.py — RANSAC nội suy cạnh tấm vi điện cực

Thuật toán:
  1. Lấy ngẫu nhiên 2 điểm → đường thẳng tạm thời.
  2. Đếm inliers (khoảng cách vuông góc < ε).
  3. Giữ mô hình inlier-max qua N vòng.
  4. Tái nội suy (SVD) trên toàn bộ inliers của mô hình tốt nhất.
  5. Lặp để tìm cặp cạnh song song.
"""

import cv2
import numpy as np
from typing import Optional, List, Tuple

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import (
    RANSAC_ITERATIONS, RANSAC_INLIER_THRESH,
    RANSAC_MAX_SIDES, RANSAC_PARALLEL_DEG, MIN_CONTOUR_AREA,
)

LineParams = Tuple[float, float, float, float]   # (vx, vy, x0, y0)


# ─── Khoảng cách điểm–đường ────────────────────────────────────────────────────

def _point_line_dist(
    pts: np.ndarray,          # (N,2) float
    x0: float, y0: float,
    vx: float, vy: float,
) -> np.ndarray:
    """
    Khoảng cách vuông góc từ mỗi điểm đến đường thẳng P0 + t*d.
    Công thức: |cross(AP, d)| = |(px-x0)*vy - (py-y0)*vx|
    """
    dx = pts[:, 0] - x0
    dy = pts[:, 1] - y0
    return np.abs(dx * vy - dy * vx)           # vx,vy là vectơ đơn vị


def _fit_line_svd(pts: np.ndarray) -> LineParams:
    """Nội suy đường thẳng tối ưu bằng SVD (tương đương PCA 2D)."""
    mean = pts.mean(axis=0)
    centered = pts - mean
    _, _, Vt = np.linalg.svd(centered, full_matrices=False)
    vx, vy = float(Vt[0, 0]), float(Vt[0, 1])
    # Chuẩn hóa chiều
    if vx < 0 or (vx == 0 and vy < 0):
        vx, vy = -vx, -vy
    return vx, vy, float(mean[0]), float(mean[1])


# ─── RANSAC core ───────────────────────────────────────────────────────────────

def ransac_line(
    pts: np.ndarray,
    n_iter: int = RANSAC_ITERATIONS,
    thresh: float = RANSAC_INLIER_THRESH,
) -> Tuple[Optional[LineParams], np.ndarray]:
    """
    RANSAC tìm đường thẳng tốt nhất từ tập điểm pts (N,2).

    Returns:
        (line_params, inlier_mask) — line_params là None nếu thất bại.
    """
    if len(pts) < 2:
        return None, np.zeros(len(pts), dtype=bool)

    best_inliers = np.zeros(len(pts), dtype=bool)
    best_count   = 0
    rng = np.random.default_rng(seed=42)

    for _ in range(n_iter):
        idx = rng.choice(len(pts), 2, replace=False)
        p1, p2 = pts[idx[0]], pts[idx[1]]
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        length = np.hypot(dx, dy)
        if length < 1e-6:
            continue
        vx, vy = dx / length, dy / length

        dists   = _point_line_dist(pts, p1[0], p1[1], vx, vy)
        inliers = dists < thresh
        count   = inliers.sum()

        if count > best_count:
            best_count   = count
            best_inliers = inliers

    if best_count < 2:
        return None, best_inliers

    # Tái nội suy bằng SVD trên toàn bộ inliers
    line = _fit_line_svd(pts[best_inliers])
    # Cập nhật inlier mask theo mô hình tái nội suy
    vx, vy, x0, y0 = line
    dists = _point_line_dist(pts, x0, y0, vx, vy)
    final_mask = dists < thresh
    return line, final_mask


# ─── Tìm cặp cạnh song song ─────────────────────────────────────────────────────

def _angle_between(vx1: float, vy1: float, vx2: float, vy2: float) -> float:
    """Góc (độ) giữa hai vectơ, kết quả trong [0°, 90°]."""
    cos_val = abs(vx1 * vx2 + vy1 * vy2)
    cos_val = min(1.0, cos_val)
    return float(np.degrees(np.arccos(cos_val)))


def find_rectangle_sides(
    mask: np.ndarray,
) -> Optional[Tuple[LineParams, LineParams]]:
    """
    Tìm hai cạnh dài song song của tấm vi điện cực từ mặt nạ nhị phân.

    Returns:
        (left_side, right_side) sắp xếp theo centroid x tăng dần,
        hoặc None nếu không tìm được.
    """
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    valid = [c for c in contours if cv2.contourArea(c) >= MIN_CONTOUR_AREA]
    if not valid:
        return None

    # Lấy contour lớn nhất
    biggest = max(valid, key=cv2.contourArea)
    pts_all = biggest.reshape(-1, 2).astype(np.float32)

    found_sides: List[Tuple[LineParams, np.ndarray]] = []   # (line, inlier_mask)
    remaining   = pts_all.copy()
    used_mask   = np.zeros(len(pts_all), dtype=bool)

    for _ in range(RANSAC_MAX_SIDES):
        if len(remaining) < 2:
            break
        line, inliers = ransac_line(remaining)
        if line is None or inliers.sum() < 5:
            break
        found_sides.append((line, inliers))
        # Loại bỏ inliers khỏi tập điểm
        remaining = remaining[~inliers]

    if len(found_sides) < 2:
        return None

    # Tìm cặp song song tốt nhất
    best_pair = None
    best_score = -1.0

    for i in range(len(found_sides)):
        for j in range(i + 1, len(found_sides)):
            l1, m1 = found_sides[i]
            l2, m2 = found_sides[j]
            vx1, vy1 = l1[0], l1[1]
            vx2, vy2 = l2[0], l2[1]

            angle_diff = _angle_between(vx1, vy1, vx2, vy2)
            if angle_diff > RANSAC_PARALLEL_DEG:
                continue

            # Khoảng cách giữa hai centroid
            cx1, cy1 = l1[2], l1[3]
            cx2, cy2 = l2[2], l2[3]
            dist = np.hypot(cx2 - cx1, cy2 - cy1)

            # Chiều dài trung bình (proxy = sqrt(số inliers))
            len_avg = (np.sqrt(m1.sum()) + np.sqrt(m2.sum())) / 2
            score = dist / (len_avg + 1e-6)

            if score > best_score:
                best_score = score
                best_pair  = (l1, l2)

    if best_pair is None:
        return None

    # Sắp xếp: trái (x nhỏ hơn) → phải
    l1, l2 = best_pair
    if l1[2] > l2[2]:
        l1, l2 = l2, l1
    return l1, l2


def compute_virtual_centerline(
    left: LineParams, right: LineParams
) -> LineParams:
    """
    Tính đường trung tâm ảo của tấm vi điện cực bằng cách trung bình
    điểm neo và vectơ chỉ phương của hai cạnh song song.
    """
    vx1, vy1, x01, y01 = left
    vx2, vy2, x02, y02 = right

    # Đảm bảo hai vectơ cùng chiều trước khi trung bình
    if vx1 * vx2 + vy1 * vy2 < 0:
        vx2, vy2 = -vx2, -vy2

    vx_avg = (vx1 + vx2) / 2
    vy_avg = (vy1 + vy2) / 2
    norm   = np.hypot(vx_avg, vy_avg) + 1e-9
    vx_avg /= norm
    vy_avg /= norm

    x0_avg = (x01 + x02) / 2
    y0_avg = (y01 + y02) / 2

    if vx_avg < 0 or (vx_avg == 0 and vy_avg < 0):
        vx_avg, vy_avg = -vx_avg, -vy_avg

    return vx_avg, vy_avg, x0_avg, y0_avg
