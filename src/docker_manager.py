# src/docker_manager.py

import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional

import logging

from errors import DockerManagerError

logger = logging.getLogger(__name__)

class DockerManager:
    """
    Manages Docker Compose lifecycle for the Ignition dev gateway.
    """

    def __init__(
        self,
        compose_file: Path,
        env_file: Optional[Path] = None,
        service_name: str = 'ignition-dev',
    ):
        self.compose_file = compose_file
        self.env_file = env_file
        self.service = service_name

    def _build_base_cmd(self):
        cmd = ['docker', 'compose', '-f', str(self.compose_file)]
        if self.env_file:
            cmd += ['--env-file', str(self.env_file)]
        return cmd

    def up(self) -> None:
        """
        docker compose up -d
        """
        cmd = self._build_base_cmd() + ['up', '-d']
        logger.info("Starting containers with: %s", ' '.join(cmd))
        try:
            cp = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            logger.debug("Compose up stdout: %s", cp.stdout.strip())
            logger.debug("Compose up stderr: %s", cp.stderr.strip())
        except subprocess.CalledProcessError as e:
            logger.error("Compose up failed: %s", e.stderr.strip())
            raise DockerManagerError(f"'docker compose up' failed: {e.stderr.strip()}")

    def down(self) -> None:
        """
        docker compose down -v
        """
        cmd = self._build_base_cmd() + ['down', '-v']
        logger.info("Tearing down containers with: %s", ' '.join(cmd))
        try:
            cp = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            logger.debug("Compose down stdout: %s", cp.stdout.strip())
            logger.debug("Compose down stderr: %s", cp.stderr.strip())
        except subprocess.CalledProcessError as e:
            logger.error("Compose down failed: %s", e.stderr.strip())
            raise DockerManagerError(f"'docker compose down' failed: {e.stderr.strip()}")

    def stream_logs(self, on_line: Callable[[str], None], stop_event: threading.Event) -> None:
        """
        docker compose logs -f <service_name>
        Streams each line to the provided callback until stop_event is set.
        """
        cmd = self._build_base_cmd() + ['logs', '-f', self.service]
        logger.info("Streaming logs with: %s", ' '.join(cmd))
        try:
            # Start the process
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            logger.exception("Failed to start log streaming process")
            raise DockerManagerError(f"Could not start log streaming: {e}")

        # Read lines in a separate thread or in the calling thread
        try:
            if proc.stdout is None:
                raise DockerManagerError("Failed to capture logs: stdout is None")
            for line in proc.stdout:
                clean = line.rstrip()
                logger.debug("Log> %s", clean)
                on_line(clean)
                if stop_event.is_set():
                    logger.info("Stop event set, terminating log stream")
                    proc.terminate()
                    break
        except Exception as e:
            logger.exception("Error while streaming logs")
            proc.terminate()
            raise DockerManagerError(f"Error streaming logs: {e}")
        finally:
            proc.wait()
            logger.info("Log streaming process ended with code %s", proc.returncode)
