# src/logging_config.py
import logging
import sys
from pathlib import Path

def setup_logging(
    log_file: Path = None,
    level: int = logging.DEBUG,
    fmt: str = '%(asctime)s %(levelname)s [%(name)s] %(message)s',
    datefmt: str = '%Y-%m-%d %H:%M:%S'
):
    """
    Configure root logger with a console handler (stdout) and optional file handler.
    Call this once at application startup.
    """
    root = logging.getLogger()
    root.setLevel(level)

    formatter = logging.Formatter(fmt, datefmt=datefmt)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(formatter)
    root.addHandler(ch)

    # File handler
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(level)
        fh.setFormatter(formatter)
        root.addHandler(fh)
