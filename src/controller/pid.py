"""
pid.py — Bộ điều khiển PID rời rạc với anti-windup

Phương trình rời rạc hóa (Euler tiến, chu kỳ biến đổi Δt_k):

    u_P(k) = Kp * e(k)
    u_I(k) = Ki * Σ e(j)*Δt_j   (kẹp trong [-I_max, +I_max])
    u_D(k) = Kd * (e(k) - e(k-1)) / Δt_k
    u(k)   = clip(u_P + u_I + u_D, -U_max, +U_max)

Tín hiệu e(k) và u(k) đều tính bằng đơn vị micromet (µm).
"""

import time
from typing import Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import KP, KI, KD, I_MAX, U_MAX


class PIDController:
    """
    Bộ điều khiển PID rời rạc với:
      - Chu kỳ lấy mẫu biến đổi (đo bằng wall-clock)
      - Kẹp tích phân (anti-windup) theo I_max
      - Bão hòa đầu ra theo U_max
      - Reset tự động khi mất tín hiệu
    """

    def __init__(
        self,
        kp: float = KP,
        ki: float = KI,
        kd: float = KD,
        i_max: float = I_MAX,
        u_max: float = U_MAX,
    ) -> None:
        self.kp    = kp
        self.ki    = ki
        self.kd    = kd
        self.i_max = i_max
        self.u_max = u_max

        self._integral:  float          = 0.0
        self._prev_error: Optional[float] = None
        self._prev_time:  Optional[float] = None

    # ─── Public API ───────────────────────────────────────────────────────────

    def step(self, error_um: float) -> float:
        """
        Tính tín hiệu điều khiển cho một bước lấy mẫu.

        Args:
            error_um : sai lệch vị trí Δd (µm), dương khi chip lệch dương.

        Returns:
            u (µm) : lượng dịch chuyển yêu cầu trong chu kỳ này.
        """
        now = time.monotonic()

        if self._prev_time is None:
            dt = 0.033          # giả sử 30 fps cho bước đầu tiên
        else:
            dt = now - self._prev_time
            dt = max(dt, 1e-4)  # tránh chia cho 0

        # Thành phần tỉ lệ
        u_p = self.kp * error_um

        # Thành phần tích phân với kẹp anti-windup
        self._integral += error_um * dt
        self._integral  = max(-self.i_max, min(self.i_max, self._integral))
        u_i = self.ki * self._integral

        # Thành phần vi phân (tắt khi kd=0 hoặc bước đầu)
        u_d = 0.0
        if self.kd != 0.0 and self._prev_error is not None:
            u_d = self.kd * (error_um - self._prev_error) / dt

        u = u_p + u_i + u_d

        # Bão hòa đầu ra
        u = max(-self.u_max, min(self.u_max, u))

        self._prev_error = error_um
        self._prev_time  = now
        return u

    def reset(self) -> None:
        """
        Đặt lại trạng thái PID về 0.
        Gọi mỗi khi hệ thống thị giác mất nhận diện đối tượng.
        """
        self._integral   = 0.0
        self._prev_error = None
        self._prev_time  = None

    # ─── Properties ───────────────────────────────────────────────────────────

    @property
    def integral(self) -> float:
        return self._integral

    @property
    def params(self) -> dict:
        return {
            "Kp": self.kp, "Ki": self.ki, "Kd": self.kd,
            "I_max": self.i_max, "U_max": self.u_max,
        }
