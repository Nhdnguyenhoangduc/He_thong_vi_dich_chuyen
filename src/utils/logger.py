"""
logger.py — Cấu hình logging cho toàn bộ project
"""

import logging
import sys


def setup_logger(level: int = logging.INFO) -> None:
    """
    Cấu hình root logger với format và handler chuẩn.
    Gọi một lần duy nhất ở đầu main.py.
    """
    fmt = "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
