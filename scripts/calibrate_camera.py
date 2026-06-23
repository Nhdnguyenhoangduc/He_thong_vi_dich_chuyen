"""
calibrate_camera.py — Đo hệ số tỷ lệ không gian SCALE_UM_PER_PX

Quy trình:
  1. Chụp frame từ camera.
  2. Click hai đầu vật chuẩn có chiều dài đã biết.
  3. Tính SCALE_UM_PER_PX = length_um / distance_px

Cách dùng:
    python scripts/calibrate_camera.py --length 10000 --camera 1
"""

import sys, os, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import cv2
import numpy as np


points: list = []


def on_mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN and len(points) < 2:
        points.append((x, y))
        print(f"  Điểm {len(points)}: ({x}, {y})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--length", type=float, default=10_000,
                        help="Chiều dài vật chuẩn (µm). Mặc định 10000 µm = 10 mm")
    parser.add_argument("--camera", type=int, default=1,
                        help="Index camera (mặc định 1, khớp với main())")
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not cap.isOpened():
        print(f"Không mở được camera index={args.camera}")
        sys.exit(1)

    print("Nhấn SPACE để chụp ảnh, ESC để thoát.")
    frame = None
    while True:
        ret, f = cap.read()
        if not ret:
            continue
        cv2.imshow("Camera — nhấn SPACE để chụp", f)
        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            cap.release(); cv2.destroyAllWindows(); sys.exit(0)
        if key == 32:
            frame = f.copy()
            break

    cap.release()
    cv2.destroyAllWindows()

    print("\nClick hai đầu vật chuẩn trên ảnh (2 điểm):")
    cv2.namedWindow("Hiệu chuẩn")
    cv2.setMouseCallback("Hiệu chuẩn", on_mouse)

    while True:
        disp = frame.copy()
        for p in points:
            cv2.circle(disp, p, 5, (0, 255, 0), -1)
        if len(points) == 2:
            cv2.line(disp, points[0], points[1], (0, 255, 0), 2)
        cv2.imshow("Hiệu chuẩn", disp)
        key = cv2.waitKey(20) & 0xFF
        if key == 27 or len(points) == 2:
            break

    cv2.destroyAllWindows()

    if len(points) < 2:
        print("Chưa đủ 2 điểm.")
        sys.exit(1)

    px_dist = np.hypot(points[1][0] - points[0][0],
                       points[1][1] - points[0][1])
    scale   = args.length / px_dist

    print(f"\n{'─'*50}")
    print(f"  Khoảng cách đo được : {px_dist:.2f} px")
    print(f"  Chiều dài thực tế   : {args.length:.1f} µm")
    print(f"  SCALE_UM_PER_PX     = {scale:.6f}  µm/px")
    print(f"{'─'*50}")
    print(f"\nCập nhật trong src/vision_pipeline.py:")
    print(f"  SCALE_UM_PER_PX: float = {scale:.6f}")


if __name__ == "__main__":
    main()
