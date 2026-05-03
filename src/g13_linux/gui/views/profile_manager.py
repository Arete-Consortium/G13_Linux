"""
Profile Manager Widget

UI for managing G13 button configuration profiles.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ProfileManagerWidget(QWidget):
    """Profile management UI"""

    profile_selected = pyqtSignal(str)  # Profile name
    profile_saved = pyqtSignal(str)  # Profile name
    profile_deleted = pyqtSignal(str)  # Profile name
    profile_export_requested = pyqtSignal(str, str)  # Profile name, export path
    profile_import_requested = pyqtSignal(str)  # Import file path

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_profiles = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header
        header = QLabel("Profiles")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(header)

        helper = QLabel("Create or select a profile, map keys in the device view, then save.")
        helper.setWordWrap(True)
        helper.setStyleSheet("color: #888;")
        layout.addWidget(helper)

        self.profile_filter = QLineEdit()
        self.profile_filter.setPlaceholderText("Filter profiles...")
        self.profile_filter.textChanged.connect(self._apply_profile_filter)
        layout.addWidget(self.profile_filter)

        # Profile list
        self.profile_list = QListWidget()
        self.profile_list.itemClicked.connect(lambda item: self.profile_selected.emit(item.text()))
        self.profile_list.itemSelectionChanged.connect(self._update_action_buttons)
        layout.addWidget(self.profile_list)

        # Buttons
        btn_layout = QHBoxLayout()

        new_btn = QPushButton("New Profile")
        new_btn.clicked.connect(self._on_new_profile)
        new_btn.setToolTip("Create a new blank profile")
        btn_layout.addWidget(new_btn)

        self.save_btn = QPushButton("Save Selected")
        self.save_btn.clicked.connect(self._on_save_profile)
        self.save_btn.setToolTip("Save current mappings to the selected profile")
        btn_layout.addWidget(self.save_btn)

        self.save_as_btn = QPushButton("Save Copy As...")
        self.save_as_btn.clicked.connect(self._on_save_as_profile)
        self.save_as_btn.setToolTip("Save current mappings to a new profile name")
        btn_layout.addWidget(self.save_as_btn)

        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.clicked.connect(self._on_delete_profile)
        self.delete_btn.setToolTip("Delete the selected profile")
        btn_layout.addWidget(self.delete_btn)

        layout.addLayout(btn_layout)

        # Import/Export buttons
        io_layout = QHBoxLayout()

        import_btn = QPushButton("Import...")
        import_btn.clicked.connect(self._on_import_profile)
        io_layout.addWidget(import_btn)

        self.export_btn = QPushButton("Export Selected...")
        self.export_btn.clicked.connect(self._on_export_profile)
        io_layout.addWidget(self.export_btn)

        io_layout.addStretch()
        layout.addLayout(io_layout)

        self._update_action_buttons()

    def update_profile_list(self, profiles: list):
        """Update the profile list"""
        current_selection = (
            self.profile_list.currentItem().text() if self.profile_list.currentItem() else None
        )
        self._all_profiles = list(profiles)
        self._apply_profile_filter(preferred_selection=current_selection)

    def _apply_profile_filter(self, preferred_selection=None):
        """Apply profile name filter to the list."""
        filter_text = self.profile_filter.text().strip().lower()
        if not filter_text:
            filtered = self._all_profiles
        else:
            filtered = [name for name in self._all_profiles if filter_text in name.lower()]

        self.profile_list.clear()
        self.profile_list.addItems(filtered)

        if preferred_selection and preferred_selection in filtered:
            items = self.profile_list.findItems(preferred_selection, Qt.MatchFlag.MatchExactly)
            if items:
                self.profile_list.setCurrentItem(items[0])
        elif filtered:
            self.profile_list.setCurrentRow(0)

        self._update_action_buttons()

    def _update_action_buttons(self):
        """Enable or disable actions based on selection state."""
        has_selection = self.profile_list.currentItem() is not None
        self.save_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
        self.export_btn.setEnabled(has_selection)

    def _on_new_profile(self):
        """Create new profile"""
        name, ok = QInputDialog.getText(self, "New Profile", "Profile name:")
        if ok and name:
            self.profile_selected.emit(name)

    def _on_save_profile(self):
        """Save current profile"""
        current = self.profile_list.currentItem()
        if current:
            self.profile_saved.emit(current.text())
        else:
            self._on_save_as_profile()

    def _on_save_as_profile(self):
        """Save as new profile"""
        name, ok = QInputDialog.getText(self, "Save As", "Profile name:")
        if ok and name:
            self.profile_saved.emit(name)

    def _on_delete_profile(self):
        """Delete selected profile"""
        current = self.profile_list.currentItem()
        if current:
            reply = QMessageBox.question(
                self,
                "Delete Profile",
                f'Delete profile "{current.text()}"?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.profile_deleted.emit(current.text())

    def _on_import_profile(self):
        """Import profile from file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Profile",
            "",
            "G13 Profiles (*.json);;All Files (*)",
        )
        if file_path:
            self.profile_import_requested.emit(file_path)

    def _on_export_profile(self):
        """Export selected profile to file"""
        current = self.profile_list.currentItem()
        if not current:
            QMessageBox.warning(
                self,
                "Export Profile",
                "Please select a profile to export.",
            )
            return

        profile_name = current.text()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Profile",
            f"{profile_name}.json",
            "G13 Profiles (*.json);;All Files (*)",
        )
        if file_path:
            self.profile_export_requested.emit(profile_name, file_path)
