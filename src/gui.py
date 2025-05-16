# src/gui.py

import socket
import subprocess
import sys
import threading
from pathlib import Path
import typing
import webbrowser

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFormLayout, QVBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QComboBox,
    QTextEdit, QMessageBox
)
from PyQt5.QtCore import Qt, QMetaObject
from PyQt5.QtGui import QCloseEvent

# application modules
from log_watcher import FileWatcher
from logging_config import setup_logging
from utils import save_backup, save_tag_file, unzip_project, clear_generated
from compose_generator import build_config, render_compose, render_env
from docker_manager import DockerManager
from errors import AppError, DockerManagerError

# Constants for directories
BASE_DIR     = Path(__file__).resolve().parent.parent
BACKUPS_DIR  = BASE_DIR / 'backups'
PROJECTS_DIR = BASE_DIR / 'projects'
TAGS_DIR     = BASE_DIR / 'tags'
GENERATED    = BASE_DIR / 'generated'


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ignition Dev Gateway Admin Panel")
        self.resize(800, 1000)
        self.setMinimumSize(800, 800)

        # Central widget & layout
        central = QWidget()
        self.setCentralWidget(central)
        self.form = QFormLayout()
        layout = QVBoxLayout()
        layout.addLayout(self.form)
        central.setLayout(layout)

        # Mode selector
        self.mode_cb = QComboBox()
        self.mode_cb.addItems(["clean", "backup"])
        self.form.addRow("Gateway Mode:", self.mode_cb)
        self.mode_cb.currentTextChanged.connect(self._on_mode_change)

        # Backup picker
        self.backup_le = QLineEdit()
        self.backup_btn = QPushButton("Browse…")
        self.backup_btn.clicked.connect(self._pick_backup)
        self.form.addRow("Backup (.gwbk):", self._hbox(self.backup_le, self.backup_btn))


        # Project ZIP picker
        self.project_le = QLineEdit()
        self.project_btn = QPushButton("Browse…")
        self.project_btn.clicked.connect(self._pick_project)
        self.form.addRow("Project ZIP:", self._hbox(self.project_le, self.project_btn))


        # Tag file picker
        self.tag_le = QLineEdit()
        self.tag_btn = QPushButton("Browse…")
        self.tag_btn.clicked.connect(self._pick_tag)
        self.form.addRow("Tag JSON/XML:", self._hbox(self.tag_le, self.tag_btn))


        # Ports & credentials
        self.http_le    = QLineEdit("8088")
        self.https_le   = QLineEdit("8043")
        self.admin_le   = QLineEdit("admin")
        self.pass_le    = QLineEdit()
        self.pass_le.setEchoMode(QLineEdit.Password)
        self.gateway_le = QLineEdit("dev-gateway")
        self.edition_le = QLineEdit("standard")
        self.tz_le      = QLineEdit("America/Chicago")

        self.form.addRow("HTTP Port:", self.http_le)
        self.form.addRow("HTTPS Port:", self.https_le)
        self.form.addRow("Admin Username:", self.admin_le)
        self.form.addRow("Admin Password:", self.pass_le)
        self.form.addRow("Gateway Name:", self.gateway_le)
        self.form.addRow("Edition:", self.edition_le)
        self.form.addRow("Timezone:", self.tz_le)

        # Buttons
        self.spin_btn = QPushButton("Spin Up Gateway")
        self.spin_btn.clicked.connect(self.on_spin_up)
        self.down_btn = QPushButton("Tear Down Gateway")
        self.down_btn.clicked.connect(self.on_tear_down)
        self.purge_btn = QPushButton("Purge All Docker Resources")
        self.purge_btn.clicked.connect(self.on_purge_all)
        self.clear_btn = QPushButton("Clear Logs")
        self.clear_btn.clicked.connect(self.on_clear_logs)
        self.open_btn = QPushButton("Open Gateway")
        self.open_btn.clicked.connect(self.on_open_gateway)
    

        self.down_btn.setEnabled(False)
        self.purge_btn.setEnabled(True)
        self.spin_btn.setEnabled(True)
        self.open_btn.setEnabled(False)

        layout.addWidget(self.clear_btn)
        layout.addWidget(self.spin_btn)
        layout.addWidget(self.down_btn)
        layout.addWidget(self.purge_btn) 
        layout.addWidget(self.open_btn)

        # Log console
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        layout.addWidget(QLabel("Gateway Logs:"))
        layout.addWidget(self.log_console, 1)

        # Initial state
        self._on_mode_change(self.mode_cb.currentText())

        # Docker manager & stop event
        self.docker_mgr = None
        self.stop_evt   = None
        self.log_thread = None
        self.file_watcher = None

    def _hbox(self, *widgets):
        """Helper to put widgets in an inline layout."""
        from PyQt5.QtWidgets import QHBoxLayout
        box = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        for w in widgets:
            layout.addWidget(w)
        box.setLayout(layout)
        return box

    def _on_mode_change(self, mode: str):
        is_backup = (mode == "backup")
        self.backup_le.setEnabled(is_backup)
        self.backup_btn.setEnabled(is_backup)
        self.project_le.setEnabled(not is_backup)
        self.project_btn.setEnabled(not is_backup)
        self.tag_le.setEnabled(not is_backup)
        self.tag_btn.setEnabled(not is_backup)

    def _pick_backup(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Gateway Backup", str(BACKUPS_DIR), "Gateway Backup (*.gwbk)")
        if path:
            self.backup_le.setText(path)

    def _pick_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Project ZIP", str(PROJECTS_DIR), "ZIP Archive (*.zip)")
        if path:
            self.project_le.setText(path)

    def _pick_tag(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Tag JSON/XML", str(TAGS_DIR), "Tags (*.json *.xml)")
        if path:
            self.tag_le.setText(path)

    def append_log(self, line: str):
        """Thread-safe append to log console."""
        # Must be invoked via Qt event loop
        self.log_console.append(line)

    def find_free_port(self):
        with socket.socket() as s:
            s.bind(('', 0))
            return s.getsockname()[1]

    def is_port_free(self, port, timeout=0.5):
        with socket.socket() as s:
            s.settimeout(timeout)
            return s.connect_ex(('127.0.0.1', port)) != 0

    def on_spin_up(self):
        """Spin up the Ignition dev gateway."""
        try:
            clear_generated()  # Prepare filesystem

            # Check if ports are free
            if not self.http_le.text().strip():
                http_port = self.find_free_port()
                self.http_le.setText(str(http_port))
            else:
                http_port = int(self.http_le.text().strip())

            if not self.is_port_free(http_port):
                raise AppError(f"Host port {http_port} is already in use.")

            # Save user inputs to known dirs
            mode = self.mode_cb.currentText()
            raw = {
                'mode': mode,
                'backups_dir': str(BACKUPS_DIR),
                'projects_dir': str(PROJECTS_DIR),
                'tags_dir': str(TAGS_DIR),
                'http_port': self.http_le.text(),
                'https_port': self.https_le.text(),
                'admin_user': self.admin_le.text(),
                'admin_pass': self.pass_le.text(),
                'gateway_name': self.gateway_le.text(),
                'edition': self.edition_le.text(),
                'timezone': self.tz_le.text(),
            }

            # backup/project/tag handling
            if mode == 'backup':
                backup_file = save_backup(self.backup_le.text())
                raw['backup_name'] = backup_file
            if self.project_le.text():
                proj_name = unzip_project(self.project_le.text())
                raw['project_name'] = proj_name
            if self.tag_le.text():
                tag_file = save_tag_file(self.tag_le.text())
                raw['tag_name'] = tag_file

            # Build config and render compose & env
            cfg = build_config(raw)
            compose_path = render_compose(cfg)      # writes generated/docker-compose.yml
            env_path     = render_env(cfg)          # writes generated/.env

            # Start Docker
            self.docker_mgr = DockerManager(
                compose_file=compose_path,
                env_file=env_path,
                service_name='ignition-dev'
            )
            self.docker_mgr.up()

            # in on_spin_up(), after self.docker_mgr.up():
            if self.docker_mgr.wait_for_gateway(http_port):
                self.log_console.append("Gateway is up and responding on HTTP.")
                self.open_btn.setEnabled(True)
            else:
                self.log_console.append("Gateway did not respond within timeout.")
                # show a warning
                QMessageBox.warning(self, "Warning", "Gateway did not respond within timeout.")
                self.open_btn.setEnabled(False)

            # Update button states
            self.spin_btn.setEnabled(False)
            self.down_btn.setEnabled(True)
            self.open_btn.setEnabled(True)

            # Start file watcher for logs
            log_path = BASE_DIR / 'logs' / 'ignition-admin.log'
            self.file_watcher = FileWatcher(log_path, self.append_log)
            self.file_watcher.start()

            self.log_console.append("Gateway started successfully.")
            self.log_console.append("Waiting for logs…")

            # Stream logs
            self.stop_evt = threading.Event()

            self.log_thread = threading.Thread(
                target=self.docker_mgr.stream_logs,
                args=(self.append_log, self.stop_evt),
                daemon=True
            )
            self.log_thread.start()

        except AppError as e:
            QMessageBox.critical(self, "Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Unexpected Error", str(e))
    
    def on_open_gateway(self):
        url = f"http://localhost:{self.http_le.text().strip()}"
        webbrowser.open_new_tab(url)

    def on_tear_down(self):
        """Tear down the Compose stack."""
        try:
            if self.stop_evt:
                self.stop_evt.set()
            if self.docker_mgr:
                self.docker_mgr.down()
                self.log_console.append("Gateway torn down successfully.")

            if self.log_thread:
                self.log_thread.join(timeout=5.0)
                self.log_console.append("Log streaming stopped.")

            self.down_btn.setEnabled(False)
            self.spin_btn.setEnabled(True)
            self.open_btn.setEnabled(False)

            self.log_console.append("Gateway is shutting down…")
            self.log_console.append("Waiting for logs to finish…")
            
            if self.file_watcher:
                self.file_watcher.stop()

            self.open_btn.setEnabled(False)

        except KeyboardInterrupt:
            self.log_console.append("Tear down interrupted.")
        except DockerManagerError as e:
            QMessageBox.critical(self, "Error", str(e))
        except AppError as e:
            QMessageBox.critical(self, "Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Unexpected Error", str(e))

    def on_purge_all(self):
        reply = QMessageBox.question(
            self, "Confirm Purge",
            "This will remove all Docker containers, images, volumes, and networks. Continue?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            subprocess.run(
                ["docker", "system", "prune", "-a", "-f", "--volumes"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            QMessageBox.information(self, "Purge Complete", "All Docker resources have been pruned.")
            self.log_console.append("All Docker resources have been pruned.")
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, "Purge Failed", f"Error: {e.stderr.strip()}")
            self.log_console.append(f"Error during purge: {e.stderr.strip()}")
        except Exception as e:
            QMessageBox.critical(self, "Purge Failed", str(e))

    def closeEvent(self, a0: typing.Optional[QCloseEvent]) -> None:
        """
        Prompt teardown if a gateway is running when the window is closed.
        """
        if self.docker_mgr:
            resp = QMessageBox.question(
                self, "Exit",
                "A gateway is still running. Tear it down before exiting?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if resp == QMessageBox.Cancel:
                if a0 is not None:
                    a0.ignore()
                return
            if resp == QMessageBox.Yes:
                self.on_tear_down()

        # Call the base implementation (accepts by default)
        super().closeEvent(a0)
    
    def on_clear_logs(self):
        # Clear the QTextEdit
        self.log_console.clear()

        # Truncate the on-disk log file (if it exists)
        log_path = BASE_DIR / 'logs' / 'ignition-admin.log'
        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                # Truncate the file to zero length
                f.truncate(0)
        except Exception as e:
            # If you want to inform the user on failure:
            QMessageBox.warning(self, "Clear Logs", f"Could not clear log file:\n{e}")



def main():
    setup_logging(log_file=BASE_DIR / 'logs' / 'ignition-admin.log')
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

