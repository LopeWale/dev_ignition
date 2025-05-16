# src/docker_manager.py

import subprocess
import threading
import logging
import time
from pathlib import Path
from typing import Callable, Optional

import requests

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
        working_dir: Optional[Path] = None,
    ):
        self.compose_file = compose_file
        self.env_file = env_file
        self.service = service_name
        # Where to run docker compose from (so volumes resolve correctly)
        self.working_dir = working_dir or compose_file.parent

    def _build_base_cmd(self) -> list:
        cmd = ['docker', 'compose', '-f', str(self.compose_file)]
        if self.env_file:
            cmd += ['--env-file', str(self.env_file)]
        return cmd

    def up_stream(self, on_line: Callable[[str], None]) -> None:
        """
        Runs `docker compose up` (foreground) and streams stdout/stderr
        to the provided callback.
        """
        cmd = self._build_base_cmd() + ['up']
        logger.info("Streaming compose up with: %s", ' '.join(cmd))
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.working_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            logger.exception("Failed to start docker compose up")
            raise DockerManagerError(f"Could not start docker compose up: {e}")

        # Stream lines
        try:
            if proc.stdout is None:
                raise DockerManagerError("Failed to capture compose output: stdout is None")
            for line in proc.stdout:
                clean = line.rstrip()
                logger.debug("ComposeUp> %s", clean)
                on_line(clean)
        except Exception as e:
            logger.exception("Error while streaming compose up")
            proc.terminate()
            raise DockerManagerError(f"Error during compose up streaming: {e}")
        finally:
            ret = proc.wait()
            if ret != 0:
                raise DockerManagerError(f"docker compose up exited with code {ret}")
            logger.info("Compose up completed successfully.")

    def up_detached(self) -> None:
        """
        Runs `docker compose up -d` detached.
        """
        cmd = self._build_base_cmd() + ['up', '-d']
        logger.info("Starting containers (detached) with: %s", ' '.join(cmd))
        try:
            cp = subprocess.run(
                cmd,
                cwd=str(self.working_dir),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            logger.debug("Compose up -d stdout: %s", cp.stdout.strip())
            logger.debug("Compose up -d stderr: %s", cp.stderr.strip())
        except subprocess.CalledProcessError as e:
            logger.error("Compose up -d failed: %s", e.stderr.strip())
            raise DockerManagerError(f"'docker compose up -d' failed: {e.stderr.strip()}")

    def wait_for_gateway(self, port: int, timeout: int = 30) -> bool:
        url = f'http://localhost:{port}/main/system/status/Ping'
        end = time.time() + timeout
        while time.time() < end:
            try:
                r = requests.get(url, timeout=2)
                if r.status_code == 200:
                    return True
            except Exception:
                pass
            time.sleep(1)
        return False

    def down(self) -> None:
        """
        Runs `docker compose down -v` to tear down the stack.
        """
        cmd = self._build_base_cmd() + ['down', '-v']
        logger.info("Tearing down containers with: %s", ' '.join(cmd))
        try:
            cp = subprocess.run(
                cmd,
                cwd=str(self.working_dir),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            logger.debug("Compose down stdout: %s", cp.stdout.strip())
            logger.debug("Compose down stderr: %s", cp.stderr.strip())
        except subprocess.CalledProcessError as e:
            logger.error("Compose down failed: %s", e.stderr.strip())
            raise DockerManagerError(f"'docker compose down' failed: {e.stderr.strip()}")

    def stream_logs(self, on_line: Callable[[str], None], stop_event: threading.Event) -> None:
        """
        docker compose logs -f <service_name>
        Streams each line into the callback until stop_event is set.
        """
        cmd = self._build_base_cmd() + ['logs', '-f', self.service]
        logger.info("Streaming logs with: %s", ' '.join(cmd))
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=str(self.working_dir),
            )
        except Exception as e:
            logger.exception("Failed to start log streaming process")
            raise DockerManagerError(f"Could not start log streaming: {e}")

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