# src/log_watcher.py
import time
import threading
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class FileWatcher:
    """
    Tails a file and calls `on_line(line)` for each new line appended.
    """
    def __init__(self, path: Path, on_line, poll_interval: float = 0.5):
        self.path = path
        self.on_line = on_line
        self.poll = poll_interval
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"Started watching {self.path}")

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
        logger.info(f"Stopped watching {self.path}")

    def _run(self):
        try:
            # Wait for file to exist
            while not self.path.exists() and not self._stop.is_set():
                time.sleep(self.poll)
            with self.path.open('r', encoding='utf-8') as f:
                # Seek to end
                f.seek(0, 2)
                while not self._stop.is_set():
                    line = f.readline()
                    if line:
                        self.on_line(line.rstrip('\n'))
                    else:
                        time.sleep(self.poll)
        except Exception as e:
            logger.exception("Error watching log file")
            self._stop.set()