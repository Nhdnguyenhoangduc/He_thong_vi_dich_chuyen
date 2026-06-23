"""
serial_manager.py — Giao tiếp Serial với Arduino và giao thức ACK

Giao thức stop-and-wait:
  1. PC gửi: "X,<N_step>\\n"  (N_step: số nguyên dương/âm)
  2. Arduino thực hiện dịch chuyển
  3. Arduino gửi lại: "ACK\\n"
  4. PC tiếp tục chỉ khi nhận được ACK hợp lệ trong timeout

Nếu ACK không đến trong ACK_TIMEOUT_S giây → SerialTimeoutError.
"""

import serial
import serial.tools.list_ports
import logging
import math
from typing import Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import SERIAL_PORT, SERIAL_BAUD, ACK_TIMEOUT_S, D_STEP_UM

logger = logging.getLogger(__name__)


class SerialTimeoutError(Exception):
    """ACK không nhận được trong thời gian cho phép."""


class SerialManager:
    """
    Quản lý kết nối Serial đến Arduino Uno.

    Usage:
        sm = SerialManager()
        sm.connect()
        sm.send_move_um(delta_um=500.0)
        sm.disconnect()

    Hoặc dùng context manager:
        with SerialManager() as sm:
            sm.send_move_um(500.0)
    """

    def __init__(
        self,
        port: str       = SERIAL_PORT,
        baud: int       = SERIAL_BAUD,
        timeout: float  = ACK_TIMEOUT_S,
        d_step: float   = D_STEP_UM,
    ) -> None:
        self.port    = port
        self.baud    = baud
        self.timeout = timeout
        self.d_step  = d_step          # µm/vi-bước
        self._ser: Optional[serial.Serial] = None

    # ─── Kết nối ──────────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Mở cổng Serial và chờ Arduino khởi động."""
        self._ser = serial.Serial(
            port=self.port,
            baudrate=self.baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.timeout,
        )
        import time; time.sleep(2.0)   # chờ Arduino reset
        self._ser.reset_input_buffer()
        logger.info("Serial connected: %s @ %d baud", self.port, self.baud)

    def disconnect(self) -> None:
        if self._ser and self._ser.is_open:
            self._ser.close()
            logger.info("Serial disconnected.")

    def is_connected(self) -> bool:
        return self._ser is not None and self._ser.is_open

    # ─── Gửi lệnh ─────────────────────────────────────────────────────────────

    def send_move_steps(self, n_steps: int, axis: str = "X") -> None:
        """
        Gửi lệnh dịch chuyển N vi-bước trên trục axis và chờ ACK.

        Args:
            n_steps : số bước (dương = một chiều, âm = chiều ngược lại)
            axis    : ký tự trục ("X", "Y", …)

        Raises:
            SerialTimeoutError : khi ACK không đến trong thời gian timeout.
            RuntimeError       : khi Serial chưa kết nối.
        """
        if not self.is_connected():
            raise RuntimeError("Serial chưa kết nối. Gọi connect() trước.")

        cmd = f"{axis},{n_steps}\n"
        self._ser.write(cmd.encode("ascii"))
        self._ser.flush()
        logger.debug("TX → %s", cmd.strip())

        # Chờ ACK
        response = self._ser.readline().decode("ascii", errors="ignore").strip()
        if response != "ACK":
            raise SerialTimeoutError(
                f"Không nhận được ACK (nhận: '{response}') sau {self.timeout}s"
            )
        logger.debug("RX ← ACK")

    def send_move_um(self, delta_um: float, axis: str = "X") -> int:
        """
        Chuyển đổi lượng dịch chuyển µm sang số bước và gửi lệnh.

            N_step = round(delta_um / d_step)

        Returns:
            Số bước thực sự gửi đi.
        """
        n_steps = int(math.floor(delta_um / self.d_step + 0.5))
        if n_steps == 0:
            return 0
        self.send_move_steps(n_steps, axis)
        return n_steps

    # ─── Context manager ──────────────────────────────────────────────────────

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.disconnect()

    # ─── Tiện ích ─────────────────────────────────────────────────────────────

    @staticmethod
    def list_ports() -> list:
        """Liệt kê các cổng Serial khả dụng."""
        return [p.device for p in serial.tools.list_ports.comports()]
