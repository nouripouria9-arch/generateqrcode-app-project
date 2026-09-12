"""Universal QR Code Generator.

Run with Python 3.10+ after installing PySide6 and qrcode[pil].
"""

from __future__ import annotations

import json
import logging
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import qrcode
from qrcode.constants import ERROR_CORRECT_H

from PySide6.QtCore import Qt, QStandardPaths, QSize, Signal
from PySide6.QtGui import QClipboard, QFont, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


APP_NAME = "Universal QR Code Generator"
LOGGER = logging.getLogger(APP_NAME)


def configure_logging() -> None:
    """Keep technical errors in a local log without logging URL contents."""
    log_dir = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_dir / "qr_generator.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def validate_url(value: str) -> tuple[bool, str, str]:
    """Return validity, normalized input, and a user-facing error message."""
    normalized = value.strip()
    if not normalized:
        return False, normalized, "Please enter a URL."

    try:
        parsed = urlparse(normalized)
        if parsed.scheme.lower() not in {"http", "https"}:
            return False, normalized, "URL must start with http:// or https://."
        if not parsed.netloc or parsed.username or parsed.password:
            return False, normalized, "Please enter a valid web URL."
        if any(character.isspace() for character in normalized):
            return False, normalized, "The URL cannot contain spaces."
        hostname = parsed.hostname
        if not hostname or "." not in hostname and hostname.lower() != "localhost":
            return False, normalized, "Please include a valid domain name."
        parsed.port  # Trigger validation for malformed ports.
    except (ValueError, UnicodeError):
        return False, normalized, "Please enter a valid URL."
    return True, normalized, ""


def make_qr_image(url: str) -> QImage:
    """Create a high-resolution QR image containing exactly ``url``."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=14,
        border=5,
    )
    qr.add_data(url)
    qr.make(fit=True)
    pil_image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    image = QImage(
        pil_image.tobytes(),
        pil_image.width,
        pil_image.height,
        pil_image.width * 3,
        QImage.Format_RGB888,
    )
    return image.copy()


class Preview(QFrame):
    clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("preview")
        self.setMinimumSize(360, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_label = QLabel("Enter a URL and click Generate QR Code")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setWordWrap(True)
        self.image_label.setObjectName("emptyPreview")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(self.image_label)
        self._image: Optional[QImage] = None

    def set_image(self, image: QImage) -> None:
        self._image = image
        self._refresh()

    def clear_image(self) -> None:
        self._image = None
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText("Enter a URL and click Generate QR Code")
        self.image_label.setObjectName("emptyPreview")
        self.image_label.style().unpolish(self.image_label)
        self.image_label.style().polish(self.image_label)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        if self._image is None:
            return
        size = min(self.width() - 48, self.height() - 48)
        pixmap = QPixmap.fromImage(self._image).scaled(
            QSize(max(1, size), max(1, size)),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self.image_label.setText("")
        self.image_label.setPixmap(pixmap)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(920, 640)
        self.resize(1080, 720)
        self.current_image: Optional[QImage] = None
        self.history_path = self._history_file()
        self.history: list[str] = self._load_history()
        self._build_ui()
        self._apply_style()
        self._update_actions(False)
        LOGGER.info("Application started")

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(36, 30, 36, 24)
        root.setSpacing(18)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel(APP_NAME)
        title.setObjectName("title")
        subtitle = QLabel("Turn any web address into a clean, scannable QR code.")
        subtitle.setObjectName("subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()
        root.addLayout(header)

        input_row = QHBoxLayout()
        input_row.setSpacing(10)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/page?id=123")
        self.url_input.setClearButtonEnabled(True)
        self.url_input.setAccessibleName("URL input")
        self.url_input.returnPressed.connect(self.generate_qr)
        input_row.addWidget(self.url_input, 1)
        self.generate_button = self._button("Generate QR", "Generate a QR code from the URL")
        self.generate_button.clicked.connect(self.generate_qr)
        input_row.addWidget(self.generate_button)
        root.addLayout(input_row)

        content = QHBoxLayout()
        content.setSpacing(22)
        self.preview = Preview()
        content.addWidget(self.preview, 3)

        side = QVBoxLayout()
        side.setSpacing(10)
        side.addWidget(QLabel("Recent URLs", objectName="sectionLabel"))
        self.history_list = QListWidget()
        self.history_list.setToolTip("Double-click a URL to load it")
        self.history_list.itemDoubleClicked.connect(self._load_history_item)
        side.addWidget(self.history_list, 1)
        history_buttons = QHBoxLayout()
        self.remove_history_button = self._button("Remove", "Remove selected URL from history")
        self.remove_history_button.clicked.connect(self._remove_history_item)
        self.clear_history_button = self._button("Clear history", "Clear recent URL history")
        self.clear_history_button.clicked.connect(self._clear_history)
        history_buttons.addWidget(self.remove_history_button)
        history_buttons.addWidget(self.clear_history_button)
        side.addLayout(history_buttons)
        content.addLayout(side, 2)
        root.addLayout(content, 1)

        actions = QHBoxLayout()
        self.open_button = self._button("Open URL", "Open the current URL in your default browser")
        self.open_button.clicked.connect(self.open_url)
        self.copy_button = self._button("Copy URL", "Copy the current URL to the clipboard")
        self.copy_button.clicked.connect(self.copy_url)
        self.save_button = self._button("Save QR Code", "Save the QR code as a PNG or JPEG image")
        self.save_button.clicked.connect(self.save_qr)
        self.clear_button = self._button("Clear", "Clear the URL and QR preview")
        self.clear_button.clicked.connect(self.clear_all)
        actions.addWidget(self.open_button)
        actions.addWidget(self.copy_button)
        actions.addStretch()
        actions.addWidget(self.save_button)
        actions.addWidget(self.clear_button)
        root.addLayout(actions)

        self.status = QLabel("Ready")
        self.status.setObjectName("status")
        root.addWidget(self.status)
        self._refresh_history()

    @staticmethod
    def _button(text: str, tooltip: str) -> QPushButton:
        button = QPushButton(text)
        button.setToolTip(tooltip)
        button.setMinimumHeight(42)
        return button

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QWidget { background: #f4f7fb; color: #172033; font-size: 14px; }
            #title { color: #14213d; font-size: 28px; font-weight: 700; }
            #subtitle { color: #667085; font-size: 14px; }
            QLineEdit { background: white; border: 1px solid #cbd5e1; border-radius: 9px; padding: 10px 13px; font-size: 15px; }
            QLineEdit:focus { border: 2px solid #2878c8; padding: 9px 12px; }
            QPushButton { background: white; border: 1px solid #cbd5e1; border-radius: 8px; padding: 0 16px; font-weight: 600; }
            QPushButton:hover { background: #eaf3fc; border-color: #2878c8; }
            QPushButton:pressed { background: #d7e9fa; }
            QPushButton:disabled { color: #a0a8b5; background: #edf0f4; }
            #preview { background: white; border: 1px solid #d9e1eb; border-radius: 14px; }
            #emptyPreview { color: #98a2b3; font-size: 16px; padding: 25px; }
            #sectionLabel { color: #344054; font-weight: 700; }
            QListWidget { background: white; border: 1px solid #d9e1eb; border-radius: 9px; padding: 5px; }
            QListWidget::item { padding: 10px 8px; border-radius: 6px; }
            QListWidget::item:selected { background: #dceeff; color: #14213d; }
            #status { color: #475467; padding-top: 2px; }
            """
        )

    @staticmethod
    def _history_file() -> Path:
        location = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        path = Path(location)
        path.mkdir(parents=True, exist_ok=True)
        return path / "history.json"

    def _load_history(self) -> list[str]:
        try:
            values = json.loads(self.history_path.read_text(encoding="utf-8"))
            return [item for item in values if isinstance(item, str)][:12]
        except (OSError, ValueError):
            return []

    def _save_history(self) -> None:
        try:
            self.history_path.write_text(json.dumps(self.history, ensure_ascii=False), encoding="utf-8")
        except OSError:
            LOGGER.exception("Could not save history")

    def _refresh_history(self) -> None:
        self.history_list.clear()
        for url in self.history:
            item = QListWidgetItem(url)
            item.setToolTip(url)
            self.history_list.addItem(item)

    def _update_actions(self, has_qr: bool) -> None:
        self.save_button.setEnabled(has_qr)
        self.open_button.setEnabled(bool(self.url_input.text().strip()))
        self.copy_button.setEnabled(bool(self.url_input.text().strip()))

    def _validated_url(self) -> Optional[str]:
        valid, url, message = validate_url(self.url_input.text())
        if not valid:
            self.status.setText(message)
            self.status.setStyleSheet("color: #b42318;")
            return None
        return url

    def generate_qr(self) -> None:
        url = self._validated_url()
        if url is None:
            return
        try:
            self.current_image = make_qr_image(url)
            self.preview.set_image(self.current_image)
            self.status.setText("QR Code generated successfully.")
            self.status.setStyleSheet("color: #067647;")
            self.history = [url] + [item for item in self.history if item != url]
            self.history = self.history[:12]
            self._save_history()
            self._refresh_history()
            self._update_actions(True)
        except Exception:
            LOGGER.exception("QR generation failed")
            self.status.setText("Unable to generate QR Code.")
            self.status.setStyleSheet("color: #b42318;")

    def save_qr(self) -> None:
        if self.current_image is None:
            return
        filename, selected_filter = QFileDialog.getSaveFileName(
            self, "Save QR Code", "qr_code.png", "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg)"
        )
        if not filename:
            return
        if "JPEG" in selected_filter and not filename.lower().endswith((".jpg", ".jpeg")):
            filename += ".jpg"
        elif "PNG" in selected_filter and not filename.lower().endswith(".png"):
            filename += ".png"
        try:
            if not self.current_image.save(filename):
                raise OSError("Qt could not save the image")
            self.status.setText("QR Code saved successfully.")
            self.status.setStyleSheet("color: #067647;")
        except OSError:
            LOGGER.exception("QR save failed")
            self.status.setText("Unable to save the QR Code.")
            self.status.setStyleSheet("color: #b42318;")

    def open_url(self) -> None:
        url = self._validated_url()
        if url is None:
            return
        try:
            if not webbrowser.open(url):
                raise OSError("Browser rejected the URL")
            self.status.setText("URL opened in your default browser.")
            self.status.setStyleSheet("color: #067647;")
        except OSError:
            LOGGER.exception("Browser opening failed")
            self.status.setText("Unable to open the URL.")
            self.status.setStyleSheet("color: #b42318;")

    def copy_url(self) -> None:
        url = self._validated_url()
        if url is None:
            return
        QApplication.clipboard().setText(url, QClipboard.Mode.Clipboard)
        self.status.setText("URL copied to clipboard.")
        self.status.setStyleSheet("color: #067647;")

    def clear_all(self) -> None:
        self.url_input.clear()
        self.current_image = None
        self.preview.clear_image()
        self.status.setText("Ready")
        self.status.setStyleSheet("")
        self._update_actions(False)
        self.url_input.setFocus()

    def _load_history_item(self, item: QListWidgetItem) -> None:
        self.url_input.setText(item.text())
        self.generate_qr()

    def _remove_history_item(self) -> None:
        item = self.history_list.currentItem()
        if item is None:
            return
        self.history.remove(item.text())
        self._save_history()
        self._refresh_history()

    def _clear_history(self) -> None:
        if not self.history:
            return
        answer = QMessageBox.question(self, "Clear history", "Remove all recent URLs?")
        if answer == QMessageBox.StandardButton.Yes:
            self.history.clear()
            self._save_history()
            self._refresh_history()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setFont(QFont("Segoe UI", 10))
    configure_logging()
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
