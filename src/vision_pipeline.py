from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

SCALE_UM_PER_PX: float = 10_000 / 300

SERIAL_PORT     = "COM5"
SERIAL_BAUDRATE = 115_200
SERIAL_ENABLE   = True
ACK_TIMEOUT_S   = 10.0

@dataclass(slots=True)
class LineInfo:
    pt1: tuple[int, int]
    pt2: tuple[int, int]
    vx:  float
    vy:  float
    x0:  float
    y0:  float

line_info = LineInfo

def build_mask_color(
    frame: np.ndarray,
    h_low: int, s_low: int, v_low: int,
    h_up:  int, s_up:  int, v_up:  int,
) -> np.ndarray:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    return cv2.inRange(
        hsv,
        np.array([h_low, s_low, v_low]),
        np.array([h_up,  s_up,  v_up]),
    )

def build_mask_blue(frame: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, np.array([90, 100, 0]), np.array([130, 255, 255]))

def repair_mask(
    mask: np.ndarray,
    dilate_ksize: int = 5,
    close_ksize:  int = 5,
) -> np.ndarray:
    k_dil = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_ksize, dilate_ksize))
    k_cls = cv2.getStructuringElement(cv2.MORPH_RECT,    (close_ksize,  close_ksize))
    mask  = cv2.dilate(mask, k_dil, iterations=1)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k_cls)

def filter_contours(
    mask: np.ndarray,
    min_area: int = 300,
) -> tuple[np.ndarray, list]:
    clean = np.zeros_like(mask)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid = [c for c in cnts if cv2.contourArea(c) >= min_area]
    cv2.drawContours(clean, valid, -1, 255, -1)
    return clean, valid

def _canonicalize(vx: float, vy: float) -> tuple[float, float]:
    if abs(vy) >= abs(vx):
        if vy < 0:
            vx, vy = -vx, -vy
    else:
        if vx < 0:
            vx, vy = -vx, -vy
    return vx, vy

def _extend_to_frame(
    x0: float, y0: float,
    vx: float, vy: float,
    img_h: int, img_w: int,
) -> tuple[tuple[int, int], tuple[int, int]]:
    EPS = 1e-6
    if abs(vy) >= EPS:
        t_top = -y0 / vy
        t_bot = (img_h - 1 - y0) / vy
        pt1 = (int(round(x0 + t_top * vx)), 0)
        pt2 = (int(round(x0 + t_bot * vx)), img_h - 1)
    elif abs(vx) >= EPS:
        t_left  = -x0 / vx
        t_right = (img_w - 1 - x0) / vx
        pt1 = (0,         int(round(y0 + t_left  * vy)))
        pt2 = (img_w - 1, int(round(y0 + t_right * vy)))
    else:
        pt1 = pt2 = (int(round(x0)), int(round(y0)))
    return pt1, pt2

def fit_line_from_points(
    points: np.ndarray,
    img_h: int,
    img_w: int,
) -> LineInfo | None:
    if len(points) < 10:
        return None

    vx, vy, x0, y0 = cv2.fitLine(
        points.astype(np.float32), cv2.DIST_L2, 0, 0.001, 0.001
    ).flatten()

    vx, vy = _canonicalize(float(vx), float(vy))

    norm = math.hypot(float(vx), float(vy))
    if norm < 1e-9:
        return None
    vx /= norm
    vy /= norm

    pt1, pt2 = _extend_to_frame(float(x0), float(y0), vx, vy, img_h, img_w)
    return LineInfo(pt1=pt1, pt2=pt2, vx=vx, vy=vy, x0=float(x0), y0=float(y0))

def cluster_and_fit(
    mask: np.ndarray,
    img_h: int,
    img_w: int,
    min_contour_area: int = 300,
    min_pts_per_line: int = 10,
) -> list[LineInfo]:
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return []

    valid = sorted(
        (c for c in cnts if cv2.contourArea(c) >= min_contour_area),
        key=cv2.contourArea,
        reverse=True,
    )

    lines: list[LineInfo] = []
    for contour in valid[:2]:

        pts    = contour.reshape(-1, 2)
        result = fit_line_from_points(pts, img_h, img_w)
        if result is not None:
            lines.append(result)

    return lines

def detect_color_2lines(
    frame: np.ndarray,
    mask:  np.ndarray,
    colors:    tuple = ((0, 255, 0), (0, 128, 255)),
    thickness: int   = 2,
) -> tuple[np.ndarray, list[LineInfo], np.ndarray]:
    h, w = frame.shape[:2]

    repaired        = repair_mask(mask)
    cleaned, _      = filter_contours(repaired, min_area=3_000)
    lines           = cluster_and_fit(cleaned, img_h=h, img_w=w)

    output = frame.copy()
    for i, info in enumerate(lines):
        cv2.line(output, info.pt1, info.pt2, colors[i % len(colors)], thickness, cv2.LINE_AA)
    return output, lines, cleaned

def _fit_line_svd(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    centroid = points.mean(axis=0)
    _, _, Vt = np.linalg.svd(points - centroid, full_matrices=False)
    return centroid, Vt[0]

def _orthogonal_distances_vec(
    points: np.ndarray,
    anchor: np.ndarray,
    direction: np.ndarray,
) -> np.ndarray:
    diff = points - anchor

    return np.abs(diff[:, 0] * direction[1] - diff[:, 1] * direction[0])

def _angle_diff(a1: float, a2: float) -> float:
    d = abs(a1 - a2) % 180
    return min(d, 180 - d)

def _line_extent(
    inliers:   np.ndarray,
    centroid:  np.ndarray,
    direction: np.ndarray,
) -> float:
    proj = (inliers - centroid) @ direction
    return float(proj.max() - proj.min())

def _line_separation(l1: dict, l2: dict) -> float:
    return abs(float((l2["centroid"] - l1["centroid"]) @ l1["normal"]))

def ransac_one_line(
    points:  np.ndarray,
    n_iter:  int   = 300,
    thresh:  float = 2.0,
) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]:
    n = len(points)
    best_mask:  np.ndarray | None = None
    best_count: int               = 0

    rng = np.random.default_rng(seed=0)

    for _ in range(n_iter):
        i, j = rng.choice(n, 2, replace=False)
        d    = points[j] - points[i]
        norm = np.linalg.norm(d)
        if norm < 1e-6:
            continue
        d /= norm

        dists = _orthogonal_distances_vec(points, points[i], d)
        mask  = dists < thresh
        count = int(mask.sum())
        if count > best_count:
            best_count = count
            best_mask  = mask

    if best_mask is None or best_mask.sum() < 4:
        return None, None, None

    centroid, direction = _fit_line_svd(points[best_mask])
    return centroid, direction, best_mask

def _best_parallel_pair(lines: list[dict], parallel_tol: float) -> dict | None:
    best_score: float      = -1.0
    best_pair:  list | None = None

    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            if _angle_diff(lines[i]["angle_deg"], lines[j]["angle_deg"]) > parallel_tol:
                continue
            sep      = _line_separation(lines[i], lines[j])
            mean_ext = (lines[i]["extent"] + lines[j]["extent"]) / 2.0
            if mean_ext < 1e-6:
                continue
            score = sep / mean_ext
            if score > best_score:
                best_score = score
                best_pair  = [lines[i], lines[j]]

    return {"pair": best_pair, "score": best_score} if best_pair else None

def _sort_pair_by_x(pair: list[dict]) -> list[dict]:
    return sorted(pair, key=lambda ln: (float(ln["centroid"][0]),
                                        float(ln["centroid"][1])))

def find_rectangle_sides(
    mask_clean:   np.ndarray,
    n_iter:       int   = 300,
    thresh:       float = 2.0,
    min_inliers:  int   = 20,
    max_attempts: int   = 6,
    parallel_tol: float = 15.0,
    extent_range: tuple = (0, float("inf")),
) -> list[dict]:
    extent_min, extent_max = extent_range

    cnts, _ = cv2.findContours(mask_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return []

    points    = max(cnts, key=cv2.contourArea).reshape(-1, 2).astype(np.float64)
    remaining = points.copy()
    all_lines: list[dict] = []

    for _ in range(max_attempts):
        if len(remaining) < min_inliers:
            break

        centroid, direction, mask = ransac_one_line(remaining, n_iter, thresh)
        if centroid is None or mask.sum() < min_inliers:
            break

        inliers   = remaining[mask]
        remaining = remaining[~mask]

        normal    = np.array([-direction[1], direction[0]])
        angle_deg = np.degrees(np.arctan2(direction[1], direction[0])) % 180
        extent    = _line_extent(inliers, centroid, direction)

        if not (extent_min <= extent <= extent_max):
            continue

        all_lines.append({
            "centroid"  : centroid,
            "direction" : direction,
            "normal"    : normal,
            "inliers"   : inliers,
            "angle_deg" : angle_deg,
            "n_inliers" : int(mask.sum()),
            "extent"    : extent,
        })

        if len(all_lines) >= 2:
            best = _best_parallel_pair(all_lines, parallel_tol)
            if best is not None and best["score"] > 0.15:
                return _sort_pair_by_x(best["pair"])

    if len(all_lines) < 2:
        return all_lines

    best = _best_parallel_pair(all_lines, parallel_tol)
    raw  = best["pair"] if best else all_lines[:2]
    return _sort_pair_by_x(raw)

def build_midline_from_pair(
    pair:  list[dict],
    img_h: int,
    img_w: int,
) -> LineInfo | None:
    if pair is None or len(pair) < 2:
        return None

    l1, l2 = pair[0], pair[1]
    c1 = np.asarray(l1["centroid"],  dtype=np.float64).flatten()
    c2 = np.asarray(l2["centroid"],  dtype=np.float64).flatten()
    d1 = np.asarray(l1["direction"], dtype=np.float64).flatten()
    d2 = np.asarray(l2["direction"], dtype=np.float64).flatten()

    if any(v.shape != (2,) for v in (c1, c2, d1, d2)):
        return None

    x0, y0 = (c1 + c2) / 2.0

    d1x, d1y = _canonicalize(float(d1[0]), float(d1[1]))
    d1 = np.array([d1x, d1y], dtype=np.float64)

    if np.dot(d1, d2) < 0:
        d2 = -d2

    dir_sum  = d1 + d2
    dir_norm = np.linalg.norm(dir_sum)

    if dir_norm < 1e-9:

        dir_sum  = d1 if l1.get("n_inliers", 0) >= l2.get("n_inliers", 0) else d2
        dir_norm = np.linalg.norm(dir_sum)
        if dir_norm < 1e-9:
            return None

    vx = float(dir_sum[0]) / dir_norm
    vy = float(dir_sum[1]) / dir_norm

    vx, vy = _canonicalize(vx, vy)

    pt1, pt2 = _extend_to_frame(float(x0), float(y0), vx, vy, img_h, img_w)
    return LineInfo(pt1=pt1, pt2=pt2, vx=vx, vy=vy, x0=float(x0), y0=float(y0))

def draw_rectangle_sides(frame: np.ndarray, lines: list[dict]) -> np.ndarray:
    colors = [(0, 255, 0), (0, 120, 255)]
    out    = frame.copy()
    for i, line in enumerate(lines):
        color = colors[i % len(colors)]
        c, d  = line["centroid"], line["direction"]
        proj  = (line["inliers"] - c) @ d
        p1    = (int(round(c[0] + proj.min() * d[0])), int(round(c[1] + proj.min() * d[1])))
        p2    = (int(round(c[0] + proj.max() * d[0])), int(round(c[1] + proj.max() * d[1])))
        cv2.line(out, p1, p2, color, 2, cv2.LINE_AA)
        for pt in line["inliers"][::3]:
            cv2.circle(out, (int(pt[0]), int(pt[1])), 1, color, -1)
        cv2.putText(
            out,
            f"ang={line['angle_deg']:.1f}  ext={line['extent']:.0f}px  n={line['n_inliers']}",
            (int(c[0]) + 6, int(c[1]) - 6),
            cv2.FONT_HERSHEY_SIMPLEX, 0.40, color, 1,
        )
    return out

def signed_angle_deg(line1: LineInfo, line2: LineInfo) -> float:
    cross = line1.vx * line2.vy - line1.vy * line2.vx
    dot   = line1.vx * line2.vx + line1.vy * line2.vy
    delta = math.degrees(math.atan2(cross, dot))
    if   delta >  90: delta -= 180
    elif delta < -90: delta += 180
    return delta

def signed_distance_px(line1: LineInfo, line2: LineInfo) -> float:
    return line2.vy * (line1.x0 - line2.x0) - line2.vx * (line1.y0 - line2.y0)

def px_to_um(distance_px: float, scale: float = SCALE_UM_PER_PX) -> float:
    return distance_px * scale

def compute_metrics(
    line1: LineInfo,
    lines2: list[LineInfo],
) -> tuple[float, float] | tuple[None, None]:
    if not lines2:
        return None, None

    vx2 = np.array([l.vx for l in lines2])
    vy2 = np.array([l.vy for l in lines2])
    x2  = np.array([l.x0 for l in lines2])
    y2  = np.array([l.y0 for l in lines2])

    cross  = line1.vx * vy2 - line1.vy * vx2
    dot    = line1.vx * vx2 + line1.vy * vy2
    deltas = np.degrees(np.arctan2(cross, dot))
    deltas = np.where(deltas >  90, deltas - 180, deltas)
    deltas = np.where(deltas < -90, deltas + 180, deltas)

    dists = vy2 * (line1.x0 - x2) - vx2 * (line1.y0 - y2)

    return float(deltas.mean()), float(dists.mean())

class SerialSender:

    def __init__(self, port: str, baudrate: int, enable: bool = True) -> None:
        self.enable      = enable
        self._ser        = None
        self._pending_um: int | None = None
        self._lock       = threading.Lock()
        self._send_event = threading.Event()
        self._stop_flag  = threading.Event()
        self.status_text = "Initing Serial"

        if not enable:
            self.status_text = "Mode: DRY-run"
            print("[Serial] Mode: DRY-run")
        else:
            try:
                import serial
                self._ser = serial.Serial(port, baudrate, timeout=0.1)
                print("[Serial] Waiting for Arduino boot...")
                time.sleep(2.0)
                self._ser.reset_input_buffer()
                self.status_text = f"Serial: OK ({port})"
                print(f"[Serial] Opened {port}")
            except Exception as exc:
                self.status_text = f"Serial: ERR ({exc})"
                print(f"[Serial] Cannot open {port}: {exc} → DRY-run")
                self._ser = None

        self._thread = threading.Thread(
            target=self._ack_worker, daemon=True, name="serial-ack"
        )
        self._thread.start()

    def update(self, avg_dist_px: float) -> None:
        val_um = int(round(px_to_um(avg_dist_px)))
        with self._lock:
            self._pending_um = val_um
        self._send_event.set()

    def _ack_worker(self) -> None:
        print("[Serial-worker] Started")
        while not self._stop_flag.is_set():
            if not self._send_event.wait(timeout=0.5):
                continue

            with self._lock:
                value_um = self._pending_um
            self._send_event.clear()

            if not value_um:
                continue

            msg = f"{value_um}b"
            self.status_text = f"Serial: sent {msg}"
            print(f"[Serial] Send: {msg}")

            if self._ser is not None:
                try:
                    self._ser.reset_input_buffer()
                    self._ser.write((msg + "\n").encode("ascii"))
                except Exception as exc:
                    print(f"[Serial] Write error: {exc}")
                    self.status_text = "Serial: Write ERR"
                    continue

                self.status_text = "Serial: waiting ACK"
                ack_received = False
                deadline     = time.monotonic() + ACK_TIMEOUT_S

                while time.monotonic() < deadline:
                    if self._stop_flag.is_set():
                        return
                    try:
                        raw = self._ser.readline().decode("ascii", errors="ignore").strip()
                    except Exception as exc:
                        print(f"[Serial] Read error: {exc}")
                        break
                    if raw == "OK":
                        ack_received = True
                        break
                    if raw:
                        print(f"[Arduino] {raw}")

                with self._lock:
                    self._pending_um = None

                if ack_received:
                    print("[Serial] OK – ready for next command")
                    self.status_text = "Serial: ready"
                else:
                    print(f"[Serial] TIMEOUT – no OK after {ACK_TIMEOUT_S}s")
                    self.status_text = "Serial: TIMEOUT"
            else:
                self.status_text = f"Serial: DRY {msg}"
                time.sleep(0.5)
                print("[Serial] DRY-RUN OK")
                self.status_text = "Serial: ready(dry)"

        print("[Serial-Worker] Stopped")

    def close(self) -> None:
        self._stop_flag.set()
        self._send_event.set()
        self._thread.join(timeout=2.0)
        if self._ser and self._ser.is_open:
            self._ser.close()
            print("[Serial] Port closed")

class PIDController:

    def __init__(
        self,
        kp: float = 1.0,
        ki: float = 0.0,
        kd: float = 0.0,
        integral_limit: float = 5_000.0,
        output_limit:   float = 10_000.0,
    ) -> None:
        self.kp             = kp
        self.ki             = ki
        self.kd             = kd
        self.integral_limit = integral_limit
        self.output_limit   = output_limit

        self._integral : float      = 0.0
        self._pre_error: float      = 0.0
        self._pre_time : float|None = None

        self.last_p   : float = 0.0
        self.last_i   : float = 0.0
        self.last_d   : float = 0.0
        self.last_out : float = 0.0

    def update(self, error: float) -> float:
        now = time.time()
        dt  = 0.0 if self._pre_time is None else max(now - self._pre_time, 1e-6)
        self._pre_time = now

        p = self.kp * error

        if dt > 0:
            self._integral += error * dt
        self._integral = np.clip(self._integral, -self.integral_limit, self.integral_limit)
        i = self.ki * self._integral

        d = self.kd * ((error - self._pre_error) / dt) if dt > 0 else 0.0
        self._pre_error = error

        raw           = p + i + d
        out           = float(np.clip(raw, -self.output_limit, self.output_limit))
        self.last_p, self.last_i, self.last_d, self.last_out = p, i, d, out
        return out

    def reset(self) -> None:
        self._integral  = 0.0
        self._pre_error = 0.0
        self._pre_time  = None

PID_Controller = PIDController

def main() -> None:
    cap = cv2.VideoCapture(1)
    cap.set(cv2.CAP_PROP_BUFFERSIZE,    1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    sender = SerialSender(
        port     = SERIAL_PORT,
        baudrate = SERIAL_BAUDRATE,
        enable   = SERIAL_ENABLE,
    )
    pid = PIDController(
        kp             = 0.2,
        ki             = 0.01,
        kd             = 0.0,
        integral_limit = 5_000.0,
        output_limit   = 150_000.0,
    )

    print("Press Q to quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        h, w = frame.shape[:2]

        mask_blue = build_mask_color(frame, 110, 61, 0, 180, 255, 255)
        mask_blue, _ = filter_contours(mask_blue, min_area=10000)
        frame, lines_blue, dbg_blue = detect_color_2lines(frame, mask_blue)

        mask_rect          = build_mask_color(frame, 0, 70, 0, 179, 255, 70)
        mask_rect_repair   = repair_mask(mask_rect, dilate_ksize=3, close_ksize=17)
        mask_rect_clean, _ = filter_contours(mask_rect_repair, min_area=15000)

        rect_sides = find_rectangle_sides(
            mask_clean   = mask_rect_clean,
            n_iter       = 150,
            thresh       = 2.0,
            min_inliers  = 20,
            max_attempts = 6,
            parallel_tol = 15.0,
            extent_range = (270, 280),
        )

        vcl: LineInfo | None = None
        if len(rect_sides) == 2:
            vcl = build_midline_from_pair(rect_sides, h, w)

        if rect_sides:
            frame = draw_rectangle_sides(frame, rect_sides)
        if vcl:
            cv2.line(frame, vcl.pt1, vcl.pt2, (0, 0, 255), 2, cv2.LINE_AA)
            cv2.circle(frame, (int(vcl.x0), int(vcl.y0)), 5, (0, 0, 255), -1)

        if vcl and lines_blue:
            avg_angle, avg_dist = compute_metrics(vcl, lines_blue)

            cv2.putText(
                frame,
                f"Angle: {avg_angle:+.3f} deg   "
                f"Dist: {avg_dist:+.1f} px = {px_to_um(avg_dist):+.3f} um",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2,
            )

            for i, blue in enumerate(lines_blue):
                a = signed_angle_deg(vcl, blue)
                d = signed_distance_px(vcl, blue)
                cv2.putText(
                    frame,
                    f"  B{i+1}: angle={a:+.3f}  dist={d:+.0f}px",
                    (10, 60 + i * 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1,
                )

            control = - pid.update(avg_dist)
            sender.update(control)

            pid_y = 60 + len(lines_blue) * 25 + 10
            cv2.putText(
                frame,
                f"PID out={pid.last_out:+.1f}px  "
                f"P={pid.last_p:+.1f}  "
                f"I={pid.last_i:+.1f}  "
                f"D={pid.last_d:+.1f}",
                (10, pid_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 200, 0), 1,
            )
        else:
            missing = []
            if not vcl:        missing.append("RECT-MIDLINE")
            if not lines_blue: missing.append("BLUE")
            cv2.putText(
                frame,
                f"Missing: {', '.join(missing)}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 100, 255), 2,
            )
            pid.reset()

        cv2.putText(
            frame, sender.status_text,
            (10, frame.shape[0] - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1,
        )

        cv2.imshow("1 - frame",     frame)
        cv2.imshow("2 - mask_blue", dbg_blue)
        cv2.imshow("3 - mask_rect", mask_rect_clean)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    sender.close()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()