"""
main.py — Entry point hệ vi dịch chuyển phản hồi thị giác

Vòng điều khiển chính:
    Camera → Vision pipeline → PID → Serial ACK → repeat

Phím tắt trong cửa sổ OpenCV:
    q  : Thoát
    r  : Reset PID integral
    d  : Toggle debug mask windows
    c  : Chụp ảnh kết quả
"""

import cv2
import logging
import sys
import time
from pathlib import Path

# ── Thêm thư mục src vào path ──────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    CAMERA_INDEX, FRAME_WIDTH, FRAME_HEIGHT, TARGET_FPS,
    TOLERANCE_UM, SERIAL_PORT,
)
from vision      import (get_blue_mask, get_dark_mask,
                          fit_reference_lines,
                          find_rectangle_sides, compute_virtual_centerline,
                          compute_metrics)
from controller  import PIDController
from communication import SerialManager, SerialTimeoutError
from utils       import setup_logger, draw_overlay

setup_logger(logging.INFO)
logger = logging.getLogger("main")


def run():
    # ── Camera ────────────────────────────────────────────────────────────────
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
    if not cap.isOpened():
        logger.error("Không mở được camera index=%d", CAMERA_INDEX)
        sys.exit(1)

    # ── Serial ────────────────────────────────────────────────────────────────
    sm  = SerialManager(port=SERIAL_PORT)
    pid = PIDController()

    try:
        sm.connect()
    except Exception as exc:
        logger.warning("Không kết nối được Serial (%s). Chạy ở chế độ không phần cứng.", exc)
        sm = None

    debug_mode  = False
    frame_count = 0
    results_log = []

    logger.info("Hệ thống khởi động. Nhấn 'q' để thoát.")

    while True:
        ret, frame = cap.read()
        if not ret:
            logger.error("Mất tín hiệu camera.")
            break

        frame_count += 1
        t0 = time.monotonic()

        # ── Vision pipeline ───────────────────────────────────────────────────
        blue_mask = get_blue_mask(frame)
        dark_mask = get_dark_mask(frame)

        ref_lines  = fit_reference_lines(blue_mask)
        chip_sides = find_rectangle_sides(dark_mask)

        delta_d, delta_theta, u, n_step = None, None, None, None
        center_line = None

        if ref_lines is not None and chip_sides is not None:
            ref1, ref2 = ref_lines
            left, right = chip_sides
            center_line = compute_virtual_centerline(left, right)

            delta_d, delta_theta = compute_metrics(ref1, ref2, center_line)

            # ── PID ───────────────────────────────────────────────────────────
            u = pid.step(delta_d)

            # ── Serial ────────────────────────────────────────────────────────
            if sm is not None and abs(delta_d) > TOLERANCE_UM:
                try:
                    n_step = sm.send_move_um(u)
                except SerialTimeoutError as exc:
                    logger.warning("Serial timeout: %s", exc)

            # ── Log ───────────────────────────────────────────────────────────
            elapsed = time.monotonic() - t0
            logger.info(
                "Frame %04d | Δd=%+7.1f µm | Δθ=%+.3f° | u=%+7.1f µm | step=%s | dt=%.0f ms",
                frame_count, delta_d, delta_theta, u,
                str(n_step) if n_step else "--",
                elapsed * 1000,
            )
            results_log.append({
                "frame": frame_count,
                "time":  time.time(),
                "delta_d_um": delta_d,
                "delta_theta_deg": delta_theta,
                "u_um": u,
                "n_step": n_step,
            })
        else:
            # Mất nhận diện → reset PID
            pid.reset()
            logger.debug("Frame %04d: không nhận diện được đối tượng.", frame_count)

        # ── Hiển thị ─────────────────────────────────────────────────────────
        ref1_disp = ref_lines[0] if ref_lines else None
        ref2_disp = ref_lines[1] if ref_lines else None
        l_disp    = chip_sides[0] if chip_sides else None
        r_disp    = chip_sides[1] if chip_sides else None

        display = draw_overlay(
            frame, ref1_disp, ref2_disp, l_disp, r_disp, center_line,
            delta_d, delta_theta, u, n_step,
        )
        cv2.imshow("Micro-Positioning System", display)

        if debug_mode:
            cv2.imshow("Blue mask", blue_mask)
            cv2.imshow("Dark mask", dark_mask)

        # ── Phím tắt ─────────────────────────────────────────────────────────
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r'):
            pid.reset()
            logger.info("PID reset.")
        elif key == ord('d'):
            debug_mode = not debug_mode
            if not debug_mode:
                cv2.destroyWindow("Blue mask")
                cv2.destroyWindow("Dark mask")
        elif key == ord('c'):
            fname = f"results/capture_{frame_count:04d}.png"
            cv2.imwrite(fname, display)
            logger.info("Đã lưu ảnh: %s", fname)

    # ── Dọn dẹp ──────────────────────────────────────────────────────────────
    cap.release()
    cv2.destroyAllWindows()
    if sm:
        sm.disconnect()

    # Lưu log kết quả
    if results_log:
        _save_results_csv(results_log)


def _save_results_csv(log: list) -> None:
    import csv
    path = "results/pid_response.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=log[0].keys())
        writer.writeheader()
        writer.writerows(log)
    logger.info("Đã lưu kết quả: %s (%d dòng)", path, len(log))


if __name__ == "__main__":
    run()
