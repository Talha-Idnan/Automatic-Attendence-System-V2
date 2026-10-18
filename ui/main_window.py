"""Main window: sidebar navigation + pages. Wires pages together."""
from PySide6.QtWidgets import (QButtonGroup, QDialog, QHBoxLayout, QLabel, QMainWindow, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

from core.engine import Engine
from core.facestore import FaceStore, pretty
from ui.attendance_page import AttendancePage
from ui.enroll_dialog import EnrollDialog
from ui.live_page import LivePage
from ui.people_page import PeoplePage
from ui.reports_page import ReportsPage
from ui.settings_page import SettingsPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Face Attendance")
        self.resize(1360, 840)
        self.setMinimumSize(1240, 720)

        self.engine, self.store = Engine(), FaceStore()
        self.live = LivePage(self.engine, self.store)
        self.attendance = AttendancePage(self.store)
        self.people = PeoplePage(self.store)
        self.reports = ReportsPage(self.store)
        self.settings = SettingsPage()
        pages = [("Live", self.live), ("Attendance", self.attendance), ("People", self.people),
                 ("Reports", self.reports), ("Settings", self.settings)]

        root = QWidget()
        root.setObjectName("root")
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(232)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(16, 24, 16, 18)
        sl.setSpacing(4)
        brand, sub = QLabel("Face Attendance"), QLabel("Recognition + liveness")
        brand.setObjectName("brand")
        sub.setObjectName("brandSub")
        sl.addWidget(brand)
        sl.addWidget(sub)
        sl.addSpacing(22)

        self.stack = QStackedWidget()
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for i, (label, page) in enumerate(pages):
            b = QPushButton(label)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(b.cursor())
            self.group.addButton(b, i)
            sl.addWidget(b)
            self.stack.addWidget(page)
        self.group.button(0).setChecked(True)
        self.group.idClicked.connect(self.stack.setCurrentIndex)
        sl.addStretch()
        self.device = QLabel("Model: not loaded")
        self.device.setObjectName("caption")
        self.device.setWordWrap(True)
        sl.addWidget(self.device)

        h.addWidget(side)
        h.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        # wiring
        self.live.device_known.connect(lambda n: self.device.setText(f"Device: {n}"))
        self.live.attendance_marked.connect(lambda n, t: self.statusBar().showMessage(f"{pretty(n)} marked present at {t}", 6000))
        for p in (self.live, self.attendance, self.people, self.reports, self.settings):
            if hasattr(p, "notify"):
                p.notify.connect(lambda m: self.statusBar().showMessage(m, 8000))
        self.people.enroll_requested.connect(self.run_enroll)
        self.people.changed.connect(self._gallery_changed)
        self.attendance.changed.connect(self.live.refresh)
        self.statusBar().showMessage("Ready")

    def _gallery_changed(self):
        if self.live.is_running():                    # restart so the new gallery is loaded
            self.live.stop_camera()
            self.live.start_camera()
        self.live.refresh()

    def run_enroll(self, name):
        was_running = self.live.is_running()
        self.live.stop_camera()                       # the camera can only be used by one thing
        dlg = EnrollDialog(self.engine, self.store, name, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            key, total = self.store.add(dlg.name, dlg.samples)
            self.store.save()
            self.people.refresh()
            self.statusBar().showMessage(f"{pretty(key)} saved ({total} samples)", 8000)
        if was_running:
            self.live.start_camera()
        self.live.refresh()

    def closeEvent(self, e):
        self.live.stop_camera()
        super().closeEvent(e)
