"""
test_pid.py — Unit tests cho PIDController
Dựa trên class PIDController trong vision_pipeline.py
"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import numpy as np
import pytest
from vision_pipeline import PIDController


def test_zero_error_zero_output():
    """Không sai lệch → u ≈ 0 (chỉ đúng khi Ki=Kd=0)."""
    pid = PIDController(kp=1.0, ki=0.0, kd=0.0)
    u = pid.update(0.0)
    assert abs(u) < 1e-9


def test_proportional_component():
    """Kp * error = P term khi Ki=Kd=0 và dt=0 (bước đầu tiên)."""
    pid = PIDController(kp=2.0, ki=0.0, kd=0.0)
    # Bước đầu: dt=0 → chỉ P, không có I và D
    u = pid.update(10.0)
    assert abs(u - 20.0) < 1e-6


def test_integral_accumulates_over_time():
    """Ki > 0: tích phân phải tăng dần theo thời gian."""
    pid = PIDController(kp=0.0, ki=1.0, kd=0.0, integral_limit=1e9)
    for _ in range(5):
        pid.update(10.0)
        time.sleep(0.01)
    assert pid._integral > 0.4   # ~5 * 10 * 0.01 = 0.5 – margin


def test_integral_clamp():
    """Tích phân không vượt integral_limit."""
    pid = PIDController(kp=0.0, ki=1.0, kd=0.0, integral_limit=50.0)
    for _ in range(200):
        pid.update(1000.0)
        time.sleep(0.001)
    assert abs(pid._integral) <= 50.0


def test_output_clamp():
    """Đầu ra không vượt output_limit."""
    pid = PIDController(kp=100.0, ki=0.0, kd=0.0, output_limit=99.0)
    u = pid.update(9999.0)
    assert abs(u) <= 99.0


def test_reset_clears_state():
    """Sau reset() toàn bộ trạng thái về 0."""
    pid = PIDController(kp=0.0, ki=1.0, kd=0.0)
    for _ in range(5):
        pid.update(100.0)
        time.sleep(0.005)
    pid.reset()
    assert pid._integral  == 0.0
    assert pid._pre_error == 0.0
    assert pid._pre_time  is None


def test_sign_convention():
    """
    PID output phải có cùng dấu với error (Kp>0, Ki=Kd=0).
    Trong main(), control = -pid.update(avg_dist), nhưng class tự nó
    trả về cùng dấu với error — kiểm tra điều đó.
    """
    pid = PIDController(kp=1.0, ki=0.0, kd=0.0)
    assert pid.update(+50.0) > 0
    pid.reset()
    assert pid.update(-50.0) < 0


def test_default_params_match_main():
    """Tham số mặc định trong main(): kp=0.2, ki=0.01, kd=0."""
    pid = PIDController(kp=0.2, ki=0.01, kd=0.0,
                        integral_limit=5_000.0, output_limit=150_000.0)
    assert pid.kp == 0.2
    assert pid.ki == 0.01
    assert pid.kd == 0.0
    assert pid.integral_limit  == 5_000.0
    assert pid.output_limit    == 150_000.0
