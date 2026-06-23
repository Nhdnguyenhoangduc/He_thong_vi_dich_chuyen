"""
test_serial.py — Kiểm tra giao thức ACK với Arduino (không cần camera)

Phù hợp với firmware stepper_controller.ino:
  - Gửi "<N>b\\n"   → Arduino di chuyển N vi-bước, phản hồi "OK\\n"
  - Gửi "e\\n"      → Enable driver
  - Gửi "d\\n"      → Disable driver
  - Gửi "<N>b\\n"   với N âm → chiều ngược lại

Cách dùng:
    python scripts/test_serial.py --port COM5 --steps 500
    python scripts/test_serial.py --port /dev/ttyACM0 --steps 1000
"""

import sys, os, argparse, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def send_command(ser, cmd: str, wait_ok: bool = True, timeout: float = 10.0) -> str | None:
    """Gửi lệnh và đọc tất cả dòng phản hồi cho đến khi nhận "OK" hoặc timeout."""
    msg = cmd.strip() + "\n"
    ser.write(msg.encode("ascii"))
    ser.flush()
    print(f"  TX → {repr(msg.strip())}")

    if not wait_ok:
        return None

    deadline = time.monotonic() + timeout
    responses = []
    while time.monotonic() < deadline:
        raw = ser.readline().decode("ascii", errors="ignore").strip()
        if raw:
            print(f"  RX ← {repr(raw)}")
            responses.append(raw)
        if raw == "OK":
            return "OK"

    print(f"  [TIMEOUT] Không nhận được OK trong {timeout}s")
    return None


def main():
    parser = argparse.ArgumentParser(description="Test giao thức Serial ACK với Arduino")
    parser.add_argument("--port",    default="COM5",  help="Cổng Serial (vd: COM5, /dev/ttyACM0)")
    parser.add_argument("--baud",    type=int, default=115_200)
    parser.add_argument("--steps",   type=int, default=500,   help="Số vi-bước test")
    parser.add_argument("--timeout", type=float, default=10.0, help="ACK timeout (giây)")
    args = parser.parse_args()

    try:
        import serial
    except ImportError:
        print("pyserial chưa cài. Chạy: pip install pyserial")
        sys.exit(1)

    print(f"\nKết nối {args.port} @ {args.baud} baud ...")
    try:
        ser = serial.Serial(args.port, args.baud, timeout=args.timeout)
    except serial.SerialException as e:
        print(f"[ERR] Không mở được cổng: {e}")
        sys.exit(1)

    print("Chờ Arduino khởi động (2s)...")
    time.sleep(2.0)
    ser.reset_input_buffer()

    # Đọc banner khởi động Arduino
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        raw = ser.readline().decode("ascii", errors="ignore").strip()
        if raw:
            print(f"  Arduino: {raw}")

    print("\n--- Test 1: Enable driver ---")
    send_command(ser, "e", wait_ok=False)
    time.sleep(0.5)

    print(f"\n--- Test 2: Di chuyển +{args.steps} vi-bước ---")
    t0  = time.monotonic()
    ack = send_command(ser, f"{args.steps}b", wait_ok=True, timeout=args.timeout)
    dt  = time.monotonic() - t0
    print(f"  → {'OK' if ack else 'TIMEOUT'}  ({dt*1000:.0f} ms)")

    time.sleep(0.5)

    print(f"\n--- Test 3: Di chuyển -{args.steps} vi-bước (chiều ngược lại) ---")
    t0  = time.monotonic()
    ack = send_command(ser, f"{-args.steps}b", wait_ok=True, timeout=args.timeout)
    dt  = time.monotonic() - t0
    print(f"  → {'OK' if ack else 'TIMEOUT'}  ({dt*1000:.0f} ms)")

    time.sleep(0.5)

    print("\n--- Test 4: Disable driver ---")
    send_command(ser, "d", wait_ok=False)

    ser.close()
    print("\n[Done] Đã đóng Serial.")


if __name__ == "__main__":
    main()
