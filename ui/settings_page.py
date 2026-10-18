"""Settings page: every tunable value of the recognition pipeline, saved to data/settings.json."""
import os
import shutil
from datetime import datetime

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

from core.config import DATA_DIR, EXPORT_DIR, FACES_FILE, settings as cfg
from ui.widgets import PageHeader, SliderRow, divider, make_card

# (attribute, title, description, lo, hi, step, format)
RECOGNITION = [
    ("threshold", "Match threshold", "Minimum similarity to accept a person. Higher = stricter.", 0.40, 0.90, 0.01, "{:.2f}"),
    ("margin", "Winner margin", "The best match must beat the runner-up by this much (protects against look-alikes).", 0.00, 0.30, 0.01, "{:.2f}"),
    ("vote_needed", "Frames to confirm", "How many of the last 7 frames must agree on a name.", 1, 7, 1, "{:d}"),
    ("cooldown", "Update interval (s)", "How often an already-present person's last-seen time is refreshed.", 1.0, 30.0, 0.5, "{:.1f}"),
]
LIVENESS = [
    ("challenge_timeout", "Challenge time (s)", "Time allowed to complete the head turn.", 3.0, 20.0, 0.5, "{:.1f}"),
    ("turn_min", "Turn sensitivity", "How far the head must turn. Lower = easier.", 0.10, 0.50, 0.01, "{:.2f}"),
    ("verify_valid", "Skip challenge for (s)", "A verified person is not asked again for this long.", 5.0, 120.0, 5.0, "{:.0f}"),
]
QUALITY = [
    ("min_face", "Minimum face size (px)", "Faces smaller than this are ignored (too far away).", 30, 200, 5, "{:d}"),
    ("blur_min", "Sharpness requirement", "Blurry frames below this are ignored.", 0.0, 100.0, 1.0, "{:.0f}"),
    ("yaw_max", "Max head angle", "Faces turned further than this are not used for recognition.", 0.15, 0.60, 0.01, "{:.2f}"),
]


class SettingsPage(QWidget):
    notify = Signal(str)

    def __init__(self):
        super().__init__()
        self.rows = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(18)

        header = PageHeader("Settings", "Tune recognition, liveness and image quality")
        b_reset = QPushButton("Restore defaults")
        b_save = QPushButton("Save changes")
        b_save.setObjectName("primary")
        header.actions.addWidget(b_reset)
        header.actions.addWidget(b_save)
        root.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 8, 0)
        col.setSpacing(16)
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        col.addWidget(self._section("Recognition", RECOGNITION))

        # liveness card (toggle + sliders)
        card, lay = make_card(spacing=4)
        sec = QLabel("Liveness check")
        sec.setObjectName("section")
        lay.addWidget(sec)
        self.chk_live = QCheckBox("Require a random head-turn before marking attendance")
        self.chk_flip = QCheckBox('Flip left / right (enable if "LEFT" feels like your right)')
        lay.addWidget(self.chk_live)
        lay.addWidget(self.chk_flip)
        lay.addWidget(divider())
        self._add_rows(lay, LIVENESS)
        col.addWidget(card)

        col.addWidget(self._section("Image quality gate", QUALITY))

        # camera + data
        card, lay = make_card(spacing=8)
        sec = QLabel("Camera & data")
        sec.setObjectName("section")
        lay.addWidget(sec)
        row = QHBoxLayout()
        lab = QLabel("Camera index")
        self.cam = QComboBox()
        self.cam.addItems([str(i) for i in range(5)])
        self.cam.setFixedWidth(100)
        cap = QLabel("Restart the camera after changing this.")
        cap.setObjectName("caption")
        row.addWidget(lab)
        row.addWidget(cap, 1)
        row.addWidget(self.cam)
        lay.addLayout(row)
        lay.addWidget(divider())
        row = QHBoxLayout()
        b_open = QPushButton("Open data folder")
        b_backup = QPushButton("Back up face data")
        row.addWidget(b_open)
        row.addWidget(b_backup)
        row.addStretch()
        lay.addLayout(row)
        path = QLabel(f"Data folder: {DATA_DIR}")
        path.setObjectName("caption")
        path.setWordWrap(True)
        lay.addWidget(path)
        col.addWidget(card)
        col.addStretch()

        b_save.clicked.connect(self.save)
        b_reset.clicked.connect(self.reset)
        b_open.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(DATA_DIR)))
        b_backup.clicked.connect(self.backup)
        self.load()

    def _section(self, title, spec):
        card, lay = make_card(spacing=4)
        sec = QLabel(title)
        sec.setObjectName("section")
        lay.addWidget(sec)
        self._add_rows(lay, spec)
        return card

    def _add_rows(self, lay, spec):
        for attr, title, desc, lo, hi, step, fmt in spec:
            row = SliderRow(title, desc, lo, hi, step, getattr(cfg, attr), fmt)
            self.rows[attr] = row
            lay.addWidget(row)

    def load(self):
        for attr, row in self.rows.items():
            row.set_value(getattr(cfg, attr))
        self.chk_live.setChecked(cfg.liveness)
        self.chk_flip.setChecked(cfg.flip_directions)
        self.cam.setCurrentIndex(min(cfg.cam_index, 4))

    def save(self):
        for attr, row in self.rows.items():
            setattr(cfg, attr, row.value())
        cfg.liveness = self.chk_live.isChecked()
        cfg.flip_directions = self.chk_flip.isChecked()
        cfg.cam_index = self.cam.currentIndex()
        cfg.save()
        self.notify.emit("Settings saved. Most changes apply immediately; restart the camera for camera changes.")

    def reset(self):
        cfg.reset()
        cfg.save()
        self.load()
        self.notify.emit("Defaults restored")

    def backup(self):
        if not os.path.exists(FACES_FILE):
            self.notify.emit("No face data to back up yet")
            return
        dest = os.path.join(EXPORT_DIR, f"faces_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl")
        shutil.copy(FACES_FILE, dest)
        self.notify.emit(f"Backup saved: {dest}")
