# src/gui.py

import socket
import subprocess
import sys
import threading
import typing
import webbrowser

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFormLayout, QVBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QComboBox,
    QTextEdit, QMessageBox
)
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt, QMetaObject, Q_ARG, QTimer
from PyQt5.QtGui import QCloseEvent, QTextCursor

# application modules
from log_watcher import FileWatcher
from logging_config import setup_logging
from utils import clear_generated, save_backup, save_tag_file, unzip_project
from compose_generator import build_config, render_compose, render_env
from docker_manager import DockerManager
from errors import AppError, DockerManagerError
from paths import BACKUPS_DIR, BASE_DIR, LOGS_DIR, PROJECTS_DIR, TAGS_DIR


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
        self.http_le    = QLineEdit("8089")
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

        # Connection Type selector
        self.conn_type_cb = QComboBox()
        self.conn_type_cb.addItems(["Ethernet", "Serial"])
        self.form.addRow("Device Connection:", self.conn_type_cb)
        self.conn_type_cb.currentTextChanged.connect(self._on_conn_change)

        # Ethernet fields
        self.dev_ip_le   = QLineEdit()
        self.dev_port_le = QLineEdit()
        self.form.addRow("Device IP:",   self.dev_ip_le)
        self.form.addRow("Device Port:", self.dev_port_le)

        # Serial fields
        self.com_le      = QLineEdit()
        self.baud_le     = QLineEdit()
        self.form.addRow("Serial Port:",     self.com_le)
        self.form.addRow("Serial Baudrate:", self.baud_le)

        # Initialize showing only Ethernet by default
        self._on_conn_change(self.conn_type_cb.currentText())
        layout.addLayout(self.form)
        central.setLayout(layout)

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
        """Thread-safe append to log console and auto-scroll to the bottom."""
        # Append the line in the Qt event loop
        QMetaObject.invokeMethod(
            self.log_console,
            "append",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, line)
        )
        # Use QTimer.singleShot to scroll after appending
        def _scroll():
            cursor = self.log_console.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.log_console.setTextCursor(cursor)
            self.log_console.ensureCursorVisible()
        QTimer.singleShot(0, _scroll)

    def find_free_port(self):
        with socket.socket() as s:
            s.bind(('', 0))
            return s.getsockname()[1]

    def is_port_free(self, port, timeout=10):
        with socket.socket() as s:
            s.settimeout(timeout)
            return s.connect_ex(('127.0.0.1', port)) != 0
    
    def start_log_stream(self):
        """Begin tailing container logs after compose up."""
        self.stop_evt = threading.Event()
        if self.docker_mgr is not None:
            self.log_thread = threading.Thread(
                target=self.docker_mgr.stream_logs,
                args=(self.append_log, self.stop_evt),
                daemon=True
            )
            self.log_thread.start()
            self.append_log("▶ Streaming container logs…")
        else:
            self.append_log("❌ Docker manager is not initialized. Cannot stream logs.")

    def _on_conn_change(self, mode: str):
        """Show IP fields or COM fields depending on connection type."""
        is_eth = (mode == "Ethernet")

        # show Ethernet rows
        self.dev_ip_le     .setVisible(is_eth)
        self.dev_port_le   .setVisible(is_eth)

        # hide Serial rows
        self.com_le        .setVisible(not is_eth)
        self.baud_le       .setVisible(not is_eth)

    def _gather_connection(self, raw: dict):
        """When building the raw dict, add only the relevant keys."""
        conn = self.conn_type_cb.currentText().lower()
        raw['conn_type'] = conn
        if conn == 'ethernet':
            raw['device_ip']    = self.dev_ip_le.text().strip()
            raw['device_port']  = self.dev_port_le.text().strip()
        else:
            raw['com_port']     = self.com_le.text().strip()
            raw['baud_rate']    = self.baud_le.text().strip()


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

            # Gather connection info
            self._gather_connection(raw)

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
            self.log_console.append(f"Generated compose file: {compose_path}")
            self.log_console.append(f"Generated env file: {env_path}")
            self.log_console.append("Starting Docker containers…")

            # initialize the manager (with working_dir baked in if needed)
            self.docker_mgr = DockerManager(
                compose_file=compose_path,
                env_file=env_path,
                service_name='ignition-dev',
                working_dir=BASE_DIR
            )

            # Clear existing console and show progress
            self.log_console.clear()
            self.log_console.append("▶ Starting Docker Compose…")
            # Run `docker compose up` in the foreground and stream its lines
            def do_compose_up():
                try:
                    if self.docker_mgr is not None:
                        self.docker_mgr.up_stream(self.append_log)
                        self.append_log("✅ Compose up completed.")
                    else:
                        self.append_log("❌ Docker manager is not initialized.")
                        QMessageBox.critical(self, "Docker Error", "Docker manager is not initialized.")
                        return

                    # Now fall back to HTTP readiness probe
                    port = int(self.http_le.text().strip())
                    if self.docker_mgr.wait_for_gateway(port):
                        self.append_log("✔️ Gateway responded on HTTP.")
                        self.open_btn.setEnabled(True)
                    else:
                        self.append_log("❗ Gateway did not respond within timeout.")
                        QMessageBox.warning(self, "Warning",
                            "Gateway did not respond within timeout.")
                        self.open_btn.setEnabled(False)

                    # After compose up, still start the container-log tail
                    self.start_log_stream()

                except DockerManagerError as e:
                    self.append_log(f"❌ Compose up failed: {e}")
                    QMessageBox.critical(self, "Docker Error", str(e))
                    # revert button state
                    self.spin_btn.setEnabled(True)
                    self.down_btn.setEnabled(False)

            
            threading.Thread(target=do_compose_up, daemon=True).start()

            # Update button states
            self.open_btn.setEnabled(True)
            self.spin_btn.setEnabled(False)
            self.down_btn.setEnabled(True)
            self.log_console.append("Gateway is starting up…")

        except AppError as e:
            QMessageBox.critical(self, "Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Unexpected Error", str(e))
    
    def on_open_gateway(self):
        url = f"http://localhost:{self.http_le.text().strip()}/web/"
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
        log_path = LOGS_DIR / 'ignition-admin.log'
        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                # Truncate the file to zero length
                f.truncate(0)
        except Exception as e:
            # If you want to inform the user on failure:
            QMessageBox.warning(self, "Clear Logs", f"Could not clear log file:\n{e}")



def main():
    setup_logging(log_file=LOGS_DIR / 'ignition-admin.log')
    app = QApplication(sys.argv)
    
    dark = QPalette()
    dark.setColor(QPalette.Window,        QColor(53, 53, 53))
    dark.setColor(QPalette.WindowText,    QColor(255, 255, 255))
    dark.setColor(QPalette.Base,          QColor(42, 42, 42))
    dark.setColor(QPalette.AlternateBase, QColor(66, 66, 66))
    dark.setColor(QPalette.ToolTipBase,   QColor(255, 255, 220))
    dark.setColor(QPalette.ToolTipText,   QColor(255, 255, 255))
    dark.setColor(QPalette.Text,          QColor(255, 255, 255))
    dark.setColor(QPalette.Button,        QColor(53, 53, 53))
    dark.setColor(QPalette.ButtonText,    QColor(255, 255, 255))
    dark.setColor(QPalette.BrightText,    QColor(255, 0, 0))
    dark.setColor(QPalette.Link,          QColor(42, 130, 218))
    dark.setColor(QPalette.Highlight,     QColor(42, 130, 218))
    dark.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
    app.setPalette(dark)
    app.setStyle("Fusion")
    app.setStyleSheet("""
        /* Background for all QWidgets */
        QWidget {
          background-color: #2b2b2b;
          color: #dddddd;
        }

        /* Line edits & text areas */
        QLineEdit, QTextEdit {
          background-color: #3c3c3c;
          border: 1px solid #555555;
          border-radius: 4px;
          padding: 4px;
          color: #ffffff;
        }

        /* ComboBoxes */
        QComboBox {
          background-color: #3c3c3c;
          border: 1px solid #555555;
          border-radius: 4px;
          padding: 2px 6px;
          color: #ffffff;
        }

        /* Buttons */
        QPushButton {
          background-color: #5c5c5c;
          border: 1px solid #444444;
          border-radius: 4px;
          padding: 6px 12px;
        }
        QPushButton:hover {
          background-color: #6d6d6d;
        }
        QPushButton:pressed {
          background-color: #4a4a4a;
        }
        QPushButton:disabled {
          background-color: #3b3b3b;
          color: #777777;
        }

        /* Scrollbars */
        QScrollBar:vertical {
          background: #2b2b2b;
          width: 12px;
          margin: 0px;
        }
        QScrollBar::handle:vertical {
          background: #555555;
          min-height: 20px;
        }
        QScrollBar::handle:vertical:hover {
          background: #666666;
        }
    """)

    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

