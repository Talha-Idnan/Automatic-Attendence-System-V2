"""Enrollment dialog: live camera, quality feedback, auto/manual capture, name entry."""
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar,
                               QPushButton, QVBoxLayout, QWidget)

from core.config import settings as cfg
from core.facestore import pretty
from ui import theme
from ui.widgets import VideoWidget, divider, make_card
from ui.workers import RecognitionWorker

TARGET = 50


class EnrollDialog(QDialog):
    def __init__(self, engine, store, name="", parent=None):
        super().__init__(parent)
        self.store, self.name, self.samples = store, "", None
        self.setWindowTitle("Add samples" if name else "Enroll new person")
        self.resize(1100, 680)

        root = QHBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(20)
        self.video = VideoWidget()
        self.video.set_placeholder("Starting camera…", "Loading the face model")
        root.addWidget(self.video, 1)

        card, lay = make_card(spacing=10)
        card.setFixedWidth(340)
        title = QLabel("Add samples" if name else "Enroll new person")
        title.setObjectName("section")
        self.name_edit = QLineEdit(pretty(name) if name else "")
        self.name_edit.setPlaceholderText("Person's name")
        if name:
            self.name_edit.setReadOnly(True)
        self.count = QLabel("0")
        self.count.setObjectName("bigNumber")
        of = QLabel(f"samples  ·  {TARGET} recommended")
        of.setObjectName("caption")
        self.bar = QProgressBar()
        self.bar.setRange(0, TARGET)
        self.feedback = QLabel("Starting…")
        self.feedback.setStyleSheet(f"color: {theme.MUTED}; font-weight: 600;")
        self.auto = QCheckBox("Auto-capture while the face is good")
        self.auto.setChecked(True)
        self.b_capture = QPushButton("Capture sample  (Space)")
        self.b_capture.setObjectName("primary")
        self.b_capture.setMinimumHeight(40)
        self.b_reset = QPushButton("Reset samples")
        tips = QLabel("Tips: only one person in frame · light on your face, not behind you · "
                      "slowly turn your head a little, change distance, with and without glasses.")
        tips.setObjectName("caption")
        tips.setWordWrap(True)

        lay.addWidget(title)
        lay.addWidget(self.name_edit)
        lay.addWidget(divider())
        lay.addWidget(self.count)
        lay.addWidget(of)
        lay.addWidget(self.bar)
        lay.addWidget(self.feedback)
        lay.addWidget(self.auto)
        lay.addWidget(self.b_capture)
        lay.addWidget(self.b_reset)
        lay.addStretch()
        lay.addWidget(tips)
        lay.addWidget(divider())
        row = QHBoxLayout()
        b_cancel = QPushButton("Cancel")
        self.b_save = QPushButton("Save person")
        self.b_save.setObjectName("primary")
        row.addWidget(b_cancel)
        row.addWidget(self.b_save)
        lay.addLayout(row)
        root.addWidget(card)

        self.worker = RecognitionWorker(engine, store, "enroll")
        self.worker.frame_ready.connect(self.video.set_frame)
        self.worker.sample_added.connect(self._count)
        self.worker.feedback.connect(self._feedback)
        self.worker.failed.connect(self._failed)
        self.worker.auto = True

        self.auto.toggled.connect(lambda v: setattr(self.worker, "auto", v))
        self.b_capture.clicked.connect(self.worker.request_sample)
        self.b_reset.clicked.connect(self.worker.reset_samples)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, activated=self.worker.request_sample)
        b_cancel.clicked.connect(self.reject)
        self.b_save.clicked.connect(self._save)
        self.worker.start()

    def _count(self, n):
        self.count.setText(str(n))
        self.bar.setValue(min(n, TARGET))

    def _feedback(self, msg, ok):
        self.feedback.setText(("● " if ok else "○ ") + msg)
        self.feedback.setStyleSheet(f"color: {theme.OK if ok else theme.WARN}; font-weight: 600;")

    def _failed(self, msg):
        self.video.clear()
        self.video.set_placeholder("Could not start the camera", msg[:160])

    def _save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Name needed", "Please type the person's name.")
            return
        self.worker.auto = False
        n = len(self.worker.samples)
        if n < 10:
            QMessageBox.warning(self, "Not enough samples", f"Only {n} samples captured. Capture at least 10 (50 is ideal).")
            return
        samples = np.stack(self.worker.samples)
        key = self.store.resolve(name)
        similar = self.store.similar_to(samples, exclude=key, min_sim=cfg.similar_warn)
        if similar:
            txt = "\n".join(f"  · {pretty(k)}  (similarity {s:.2f})" for k, s in similar)
            ans = QMessageBox.question(
                self, "Very similar face",
                f"These samples look very similar to:\n{txt}\n\nDifferent people normally score below 0.5, "
                "siblings 0.6-0.8. Was someone else in the frame, or are they related?\n\nSave anyway?",
                defaultButton=QMessageBox.StandardButton.No)
            if ans != QMessageBox.StandardButton.Yes:
                return
        self.name, self.samples = name, samples
        self.accept()

    def done(self, r):
        self.worker.stop()
        super().done(r)
