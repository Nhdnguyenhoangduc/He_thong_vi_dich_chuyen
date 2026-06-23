"""
test_vision.py — Kiểm tra vision pipeline với ảnh tĩnh (không cần phần cứng)

Cách dùng:
    python scripts/test_vision.py --image assets/demo/sample_frame.png
    python scripts/test_vision.py --camera 0
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import argparse
import cv2
from vision import (get_blue_mask, get_dark_mask,
                    fit_reference_lines,
                    find_rectangle_sides, compute_virtual_centerline,
                    compute_metrics)
from utils import draw_overlay


def process_frame(frame):
    blue_mask  = get_blue_mask(frame)
    dark_mask  = get_dark_mask(frame)
    ref_lines  = fit_reference_lines(blue_mask)
    chip_sides = find_rectangle_sides(dark_mask)

    delta_d, delta_theta, center_line = None, None, None
    if ref_lines and chip_sides:
        ref1, ref2 = ref_lines
        center_line = compute_virtual_centerline(*chip_sides)
        delta_d, delta_theta = compute_metrics(ref1, ref2, center_line)
        print(f"  Δd = {delta_d:+.1f} µm  |  Δθ = {delta_theta:+.3f}°")
    else:
        print("  [!] Không nhận diện được đối tượng.")

    r1 = ref_lines[0] if ref_lines else None
    r2 = ref_lines[1] if ref_lines else None
    l  = chip_sides[0] if chip_sides else None
    r  = chip_sides[1] if chip_sides else None
    return draw_overlay(frame, r1, r2, l, r, center_line, delta_d, delta_theta), blue_mask, dark_mask


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image",  default=None, help="Đường dẫn ảnh tĩnh")
    parser.add_argument("--camera", type=int, default=None, help="Index camera")
    args = parser.parse_args()

    if args.image:
        frame = cv2.imread(args.image)
        if frame is None:
            print(f"Không đọc được ảnh: {args.image}")
            sys.exit(1)
        out, bm, dm = process_frame(frame)
        cv2.imshow("Result", out)
        cv2.imshow("Blue mask", bm)
        cv2.imshow("Dark mask", dm)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    elif args.camera is not None:
        cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            out, bm, dm = process_frame(frame)
            cv2.imshow("Vision test", out)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        cap.release()
        cv2.destroyAllWindows()
    else:
        print("Cần truyền --image <path> hoặc --camera <index>.")
        sys.exit(1)


if __name__ == "__main__":
    main()
