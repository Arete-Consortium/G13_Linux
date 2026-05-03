"""Setup assistant dialog for G13 connection and permission troubleshooting."""

from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

UDEV_SETUP_COMMANDS = (
    "sudo cp udev/99-logitech-g13.rules /etc/udev/rules.d/\n"
    "sudo udevadm control --reload-rules && sudo udevadm trigger"
)
LIBUSB_LAUNCH_COMMAND = "sudo g13-linux-gui --libusb"
DOCTOR_COMMAND = "g13-linux doctor"


class SetupAssistantDialog(QDialog):
    """Guided setup assistant with diagnostics output and copy-ready commands."""

    def __init__(self, diagnostics_text: str, has_available_backend: bool, parent=None):
        super().__init__(parent)
        self._diagnostics_text = diagnostics_text
        self._has_available_backend = has_available_backend
        self._copy_status_label = QLabel("")
        self._init_ui()

    def _init_ui(self):
        """Build setup assistant UI."""
        self.setWindowTitle("G13 Setup Assistant")
        self.setMinimumSize(720, 460)

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        heading = QLabel("Connection Setup Assistant")
        heading.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(heading)

        summary = QLabel(self._summary_text())
        summary.setWordWrap(True)
        summary.setStyleSheet("color: #b6c2d1;")
        layout.addWidget(summary)

        diagnostics_label = QLabel("Diagnostics Report")
        diagnostics_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(diagnostics_label)

        diagnostics_view = QTextEdit()
        diagnostics_view.setReadOnly(True)
        diagnostics_view.setPlainText(self._diagnostics_text)
        diagnostics_view.setStyleSheet(
            "font-family: monospace; font-size: 11px; background: #1f232a; color: #d7dde8;"
        )
        layout.addWidget(diagnostics_view, 1)

        quick_actions = QLabel("Quick Actions")
        quick_actions.setStyleSheet("font-weight: bold;")
        layout.addWidget(quick_actions)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        copy_udev = QPushButton("Copy udev Commands")
        copy_udev.clicked.connect(
            lambda: self._copy_text(UDEV_SETUP_COMMANDS, "Copied udev commands")
        )
        action_row.addWidget(copy_udev)

        copy_libusb = QPushButton("Copy libusb Launch")
        copy_libusb.clicked.connect(
            lambda: self._copy_text(LIBUSB_LAUNCH_COMMAND, "Copied libusb launch command")
        )
        action_row.addWidget(copy_libusb)

        copy_doctor = QPushButton("Copy Doctor Command")
        copy_doctor.clicked.connect(
            lambda: self._copy_text(DOCTOR_COMMAND, "Copied doctor command")
        )
        action_row.addWidget(copy_doctor)

        copy_report = QPushButton("Copy Full Report")
        copy_report.clicked.connect(
            lambda: self._copy_text(self._diagnostics_text, "Copied diagnostics report")
        )
        action_row.addWidget(copy_report)

        action_row.addStretch()
        layout.addLayout(action_row)

        self._copy_status_label.setStyleSheet("color: #8ecb8e;")
        layout.addWidget(self._copy_status_label)

        buttons = QHBoxLayout()
        buttons.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        self.setLayout(layout)

    def _summary_text(self) -> str:
        """Generate summary message from backend availability."""
        if self._has_available_backend:
            return (
                "At least one backend can open the G13. "
                "If button input is still not working, try libusb mode and run diagnostics again."
            )
        return (
            "No backend can currently open the G13. "
            "Use the quick actions below, then reconnect the device and rerun diagnostics."
        )

    def _copy_text(self, text: str, status_message: str):
        """Copy provided text into the clipboard and show confirmation."""
        app = QApplication.instance()
        if app is None:
            return
        clipboard = app.clipboard()
        if clipboard is None:
            return
        clipboard.setText(text)
        self._copy_status_label.setText(status_message)
