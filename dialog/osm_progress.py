# -*- coding: utf-8 -*-
"""Visible, platform-independent progress dialog for OSM downloads."""

from qgis.PyQt.QtCore import Qt  # type: ignore
from qgis.PyQt.QtWidgets import (  # type: ignore
    QDialog,
    QFrame,
    QLabel,
    QProgressBar,
    QVBoxLayout,
)


class OsmDownloadProgressDialog(QDialog):
    """Frameless busy dialog with a controlled 12 px panel radius."""

    def __init__(self, parent=None):
        super().__init__(parent)
        window_types = getattr(Qt, "WindowType", Qt)
        widget_attributes = getattr(Qt, "WidgetAttribute", Qt)
        window_modalities = getattr(Qt, "WindowModality", Qt)
        alignments = getattr(Qt, "AlignmentFlag", Qt)

        self.setWindowTitle("Downloading airport map elements")
        self.setWindowFlag(window_types.FramelessWindowHint, True)
        self.setAttribute(widget_attributes.WA_TranslucentBackground, True)
        self.setWindowModality(window_modalities.WindowModal)
        self.setMinimumSize(520, 96)
        self.resize(520, 96)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self.panel = QFrame(self)
        self.panel.setObjectName("osmDownloadPanel")
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(20, 16, 20, 16)
        panel_layout.setSpacing(12)

        self.status_label = QLabel(
            "Starting the airport map download…",
            self.panel,
        )
        self.status_label.setAlignment(alignments.AlignCenter)
        panel_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar(self.panel)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        panel_layout.addWidget(self.progress_bar)
        outer_layout.addWidget(self.panel)

        self.setStyleSheet(
            """
            QFrame#osmDownloadPanel {
                background-color: white;
                border: 1px solid rgba(80, 80, 80, 90);
                border-radius: 12px;
            }
            QLabel {
                color: #202124;
                font-size: 14px;
                border: none;
                background: transparent;
            }
            QProgressBar {
                min-height: 18px;
                border: 1px solid #7a8793;
                border-radius: 4px;
                background-color: #edf2f7;
            }
            QProgressBar::chunk {
                border-radius: 3px;
                background-color: #2296e8;
            }
            """
        )

    def setLabelText(self, text: str):
        """Match the QProgressDialog label-update API used by the workflow."""
        self.status_label.setText(text)
