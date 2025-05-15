# src/gui.py

import sys
import threading
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFormLayout, QVBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QComboBox,
    QTextEdit, QMessageBox
)
from PyQt5.QtCore import Qt, QMetaObject

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
        self.resize(800, 600)
        self.file_watcher = None

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

        # start with teardown disabled
        self.down_btn.setEnabled(False)

        layout.addWidget(self.spin_btn)
        layout.addWidget(self.down_btn)

        # Log console
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        layout.addWidget(QLabel("Gateway Logs:"))
        layout.addWidget(self.log_console, 1)

        # Initial state
        self._on_mode_change(self.mode_cb.currentText())

        # Docker manager & stop event placeholder
        self.docker_mgr = None
        self.stop_evt   = None
        self.log_thread = None

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

    def on_spin_up(self):
        """Spin up the Ignition dev gateway."""
        try:
            # 1) Prepare filesystem
            clear_generated()

            # 2) Save user inputs to known dirs
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

            # 3) Build config
            cfg = build_config(raw)

            # 4) Render compose & env
            compose_path = render_compose(cfg)      # writes generated/docker-compose.yml
            env_path     = render_env(cfg)          # writes generated/.env

            # 5) Start Docker
            self.docker_mgr = DockerManager(
                compose_file=compose_path,
                env_file=env_path,
                service_name='ignition-dev'
            )
            self.docker_mgr.up()
            log_path = BASE_DIR / 'logs' / 'ignition-dev.log'
            self.file_watcher = FileWatcher(log_path, self.append_log)
            self.file_watcher.start()
            self.spin_btn.setEnabled(False)
            self.down_btn.setEnabled(True)
            self.log_console.append("Gateway started successfully.")
            self.log_console.append("Waiting for logs…")

            # 6) Stream logs
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

    def on_tear_down(self):
        """Tear down the Compose stack."""
        try:
            if self.stop_evt:
                self.stop_evt.set()
            if self.docker_mgr:
                self.docker_mgr.down()
            if self.log_thread:
                self.log_thread.join(timeout=5)
            self.down_btn.setEnabled(False)
            self.spin_btn.setEnabled(True)
            self.log_console.append("Gateway torn down successfully.")
            if self.file_watcher:
                self.file_watcher.stop()
        except KeyboardInterrupt:
            self.log_console.append("Tear down interrupted.")
        except DockerManagerError as e:
            QMessageBox.critical(self, "Error", str(e))
        except AppError as e:
            QMessageBox.critical(self, "Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Unexpected Error", str(e))


def main():
    setup_logging(log_file=BASE_DIR / 'logs' / 'ignition-admin.log')
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

