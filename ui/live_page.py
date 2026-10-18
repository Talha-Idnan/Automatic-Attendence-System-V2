"""Live recognition page: camera view, session controls, today's counters and activity feed."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from core import database
from core.config import settings as cfg
from core.facestore import pretty
from ui.widgets import PageHeader, StatCard, VideoWidget, make_card
from ui.workers import RecognitionWorker
from ui import theme


class LivePage(QWidget):
    attendance_marked = Signal(str, str)
    device_known = Signal(str)
    notify = Signal(str)

    def __init__(self, engine, store):
        super().__init__()
        self.engine, self.store, self.worker = engine, store, None

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(18)
        root.addWidget(PageHeader("Live recognition", "Real-time attendance with a head-turn liveness check"))

        body = QHBoxLayout()
        body.setSpacing(20)
        self.video = VideoWidget()
        body.addWidget(self.video, 1)

        side = QVBoxLayout()
        side.setSpacing(16)
        side_w = QWidget()
        side_w.setFixedWidth(330)
        side_w.setLayout(side)
        body.addWidget(side_w)
        root.addLayout(body, 1)

        # session card
        card, lay = make_card()
        sec = QLabel("Session")
        sec.setObjectName("section")
        self.btn = QPushButton("Start camera")
        self.btn.setObjectName("primary")
        self.btn.setMinimumHeight(40)
        self.btn.clicked.connect(self.toggle)
        self.state = QLabel("Stopped")
        self.state.setObjectName("caption")
        self.state.setWordWrap(True)
        lay.addWidget(sec)
        lay.addWidget(self.btn)
        lay.addWidget(self.state)
        side.addWidget(card)

        # today counters
        row = QHBoxLayout()
        row.setSpacing(12)
        self.c_present = StatCard("Present today", "0", color=theme.OK)
        self.c_enrolled = StatCard("Enrolled", "0")
        row.addWidget(self.c_present)
        row.addWidget(self.c_enrolled)
        side.addLayout(row)

        # activity feed
        card, lay = make_card(spacing=6)
        sec = QLabel("Activity")
        sec.setObjectName("section")
        self.feed = QListWidget()
        self.feed.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.empty = QLabel("New check-ins appear here.")
        self.empty.setObjectName("caption")
        lay.addWidget(sec)
        lay.addWidget(self.feed, 1)
        lay.addWidget(self.empty)
        side.addWidget(card, 1)

    # ---- state
    def is_running(self):
        return self.worker is not None

    def refresh(self):
        self.c_present.set(len(database.records_for_date(database.today())))
        self.c_enrolled.set(len(self.store.names()))

    def showEvent(self, e):
        self.refresh()
        super().showEvent(e)

    # ---- camera control
    def toggle(self):
        self.stop_camera() if self.worker else self.start_camera()

    def start_camera(self):
        if self.worker:
            return
        self.video.clear()
        self.video.set_placeholder("Starting…", "Loading the face model and opening the camera" if not self.engine.ready
                                   else "Opening the camera")
        w = RecognitionWorker(self.engine, self.store, "recognize")
        w.device_ready.connect(self._device_ready)
        w.frame_ready.connect(self.video.set_frame)
        w.attendance_marked.connect(self._marked)
        w.failed.connect(self._failed)
        self.worker = w
        w.start()
        self.btn.setText("Stop camera")
        self.btn.setObjectName("danger")
        self.btn.setStyleSheet("")
        self.btn.style().unpolish(self.btn)
        self.btn.style().polish(self.btn)
        self.state.setText("Running · liveness " + ("on" if cfg.liveness else "off"))

    def stop_camera(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
        self.video.clear()
        self.video.set_placeholder("Camera is off", "Press Start camera to begin")
        self.btn.setText("Start camera")
        self.btn.setObjectName("primary")
        self.btn.style().unpolish(self.btn)
        self.btn.style().polish(self.btn)
        self.state.setText("Stopped")

    # ---- worker callbacks
    def _device_ready(self, name):
        self.device_known.emit(name)

    def _failed(self, msg):
        self.stop_camera()
        self.video.set_placeholder("Could not start", msg[:160])
        self.state.setText(msg)
        self.notify.emit("Camera stopped: " + msg[:90])

    def _marked(self, name, t):
        item = QListWidgetItem(f"{t}    {pretty(name)} marked present")
        self.feed.insertItem(0, item)
        self.empty.setVisible(False)
        self.refresh()
        self.attendance_marked.emit(name, t)
