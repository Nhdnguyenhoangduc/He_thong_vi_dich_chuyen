"""
plot_results.py — Vẽ lại đồ thị PID response từ file CSV đã lưu

Đồ thị khớp hoàn toàn với phần plt trong main() của vision_pipeline.py:
  - Trục X : Thời gian (s)
  - Trục Y : Sai lệch vị trí (px)
  - Đường xanh   : sai lệch thực tế (error_log)
  - Đường đỏ nét đứt : setpoint = 0
  - Box góc trên phải: Kp, Ki, Kd

CSV format (xuất bởi --save khi chạy main với flag):
    time_s,error_px,pid_output_px

Cách dùng:
    python scripts/plot_results.py --csv results/pid_response.csv
    python scripts/plot_results.py --csv results/pid_response.csv --save
"""

import argparse, csv, sys


def load_csv(path: str) -> tuple[list, list, list]:
    time_log, error_log, output_log = [], [], []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            time_log.append(float(row["time_s"]))
            error_log.append(float(row["error_px"]))
            if "pid_output_px" in row:
                output_log.append(float(row["pid_output_px"]))
    return time_log, error_log, output_log


def main():
    parser = argparse.ArgumentParser(description="Vẽ đồ thị PID response")
    parser.add_argument("--csv",  default="results/pid_response.csv")
    parser.add_argument("--kp",   type=float, default=0.2)
    parser.add_argument("--ki",   type=float, default=0.01)
    parser.add_argument("--kd",   type=float, default=0.0)
    parser.add_argument("--save", action="store_true", help="Lưu PNG thay vì hiển thị")
    args = parser.parse_args()

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib chưa cài. Chạy: pip install matplotlib")
        sys.exit(1)

    try:
        time_log, error_log, output_log = load_csv(args.csv)
    except FileNotFoundError:
        print(f"Không tìm thấy: {args.csv}")
        sys.exit(1)

    fig, ax = plt.subplots(figsize=(10, 5))

    # Đường đáp ứng thực tế (xanh lam) — khớp với main()
    ax.plot(time_log, error_log,
            color="steelblue", linewidth=1.8, label="Sai lệch thực tế")

    # Setpoint (đỏ nét đứt) — khớp với main()
    ax.axhline(y=0.0, color="red", linestyle="--", linewidth=1.4, label="Setpoint = 0")

    ax.set_xlabel("Thời gian (s)", fontsize=12)
    ax.set_ylabel("Sai lệch vị trí (px)", fontsize=12)
    ax.set_title("Đáp ứng hệ thống PID – Sai lệch vị trí theo thời gian", fontsize=13)
    ax.legend(loc="upper left", fontsize=10)
    ax.grid(True, linestyle=":", alpha=0.6)

    # Box tham số PID — khớp với main()
    pid_text = f"Kp = {args.kp}\nKi = {args.ki}\nKd = {args.kd}"
    ax.text(
        0.98, 0.97, pid_text,
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="top",
        horizontalalignment="right",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="lightyellow", alpha=0.8),
    )

    plt.tight_layout()

    if args.save:
        import os
        out = os.path.splitext(args.csv)[0] + "_plot.png"
        fig.savefig(out, dpi=150)
        print(f"Đã lưu: {out}")
    else:
        plt.show()


if __name__ == "__main__":
    main()
