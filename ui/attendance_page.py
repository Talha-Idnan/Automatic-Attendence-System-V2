"""Attendance page: daily roster (present / absent), search, manual edits and CSV export."""
import os
from datetime import datetime

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDateEdit, QFileDialog, QHBoxLayout, QInputDialog, QLineEdit,
                               QMessageBox, QPushButton, QTableWidgetItem, QVBoxLayout, QWidget)

from core import database
from core.config import EXPORT_DIR
from core.facestore import pretty
from ui import theme
from ui.widgets import (NameDelegate, PageHeader, PillDelegate, StatCard, make_card, make_table)

ROLE_ID = Qt.ItemDataRole.UserRole + 1


class AttendancePage(QWidget):
    changed = Signal()
    notify = Signal(str)

    def __init__(self, store):
        super().__init__()
        self.store = store
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(18)

        header = PageHeader("Attendance", "Daily roster - who is present and who is absent")
        self.btn_export = QPushButton("Export CSV")
        header.actions.addWidget(self.btn_export)
        root.addWidget(header)

        # stats
        stats = QHBoxLayout()
        stats.setSpacing(14)
        self.s_present = StatCard("Present", "0", color=theme.OK)
        self.s_absent = StatCard("Absent", "0", color=theme.BAD)
        self.s_rate = StatCard("Attendance rate", "–")
        for s in (self.s_present, self.s_absent, self.s_rate):
            stats.addWidget(s)
        root.addLayout(stats)

        # toolbar
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.prev = QPushButton("‹")
        self.next = QPushButton("›")
        for b in (self.prev, self.next):
            b.setFixedWidth(40)
        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("ddd, d MMM yyyy")
        self.date.setFixedWidth(170)
        self.btn_today = QPushButton("Today")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search person…")
        self.search.setFixedWidth(220)
        self.filter = QComboBox()
        self.filter.addItems(["All", "Present", "Absent"])
        self.filter.setFixedWidth(120)
        self.btn_mark = QPushButton("Mark present")
        self.btn_remove = QPushButton("Remove record")
        self.btn_remove.setObjectName("danger")
        for w in (self.prev, self.date, self.next, self.btn_today):
            bar.addWidget(w)
        bar.addSpacing(10)
        bar.addWidget(self.search)
        bar.addWidget(self.filter)
        bar.addStretch()
        bar.addWidget(self.btn_mark)
        bar.addWidget(self.btn_remove)
        root.addLayout(bar)

        # table
        card, lay = make_card(margins=(8, 8, 8, 8))
        self.table = make_table(["Person", "Status", "Check-in", "Last seen", "Duration"],
                                ["stretch", 170, 140, 140, 150])
        self._d1, self._d2 = NameDelegate(self.table), PillDelegate(self.table)
        self.table.setItemDelegateForColumn(0, self._d1)
        self.table.setItemDelegateForColumn(1, self._d2)
        lay.addWidget(self.table)
        root.addWidget(card, 1)

        # events
        self.date.dateChanged.connect(self.refresh)
        self.prev.clicked.connect(lambda: self.date.setDate(self.date.date().addDays(-1)))
        self.next.clicked.connect(lambda: self.date.setDate(self.date.date().addDays(1)))
        self.btn_today.clicked.connect(lambda: self.date.setDate(QDate.currentDate()))
        self.search.textChanged.connect(self.refresh)
        self.filter.currentIndexChanged.connect(self.refresh)
        self.btn_export.clicked.connect(self.export)
        self.btn_mark.clicked.connect(self.mark_present)
        self.btn_remove.clicked.connect(self.remove_record)

    def showEvent(self, e):
        self.refresh()
        super().showEvent(e)

    def day(self):
        return self.date.date().toString("yyyy-MM-dd")

    def _rows(self):
        recs = {r["name"]: r for r in database.records_for_date(self.day())}
        roster = list(dict.fromkeys(self.store.names() + list(recs)))
        rows = [(n, recs.get(n)) for n in roster]
        rows.sort(key=lambda x: (x[1] is None, x[1]["first_seen"] if x[1] else "", x[0].lower()))
        return rows

    def refresh(self, *_):
        rows = self._rows()
        total = len(rows)
        present = sum(1 for _, r in rows if r)
        self.s_present.set(present, f"of {total} enrolled")
        self.s_absent.set(total - present)
        self.s_rate.set(f"{100 * present / total:.0f}%" if total else "–")

        q, mode = self.search.text().strip().lower(), self.filter.currentText()
        shown = [(n, r) for n, r in rows if q in pretty(n).lower()
                 and (mode == "All" or (mode == "Present") == bool(r))]
        self.table.setRowCount(len(shown))
        for i, (n, r) in enumerate(shown):
            vals = [pretty(n), "Present" if r else "Absent",
                    r["first_seen"] if r else "–", r["last_seen"] if r else "–",
                    database.duration_text(r["first_seen"], r["last_seen"]) if r else "–"]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c == 0:
                    it.setData(Qt.ItemDataRole.UserRole, n)
                    it.setData(ROLE_ID, r["id"] if r else None)
                if c == 1:
                    it.setData(Qt.ItemDataRole.UserRole, "ok" if r else "bad")
                if c >= 2:
                    it.setForeground(Qt.GlobalColor.white if r else Qt.GlobalColor.gray)
                self.table.setItem(i, c, it)
        self._shown = shown

    def _selected(self):
        r = self.table.currentRow()
        return self._shown[r] if 0 <= r < len(getattr(self, "_shown", [])) else (None, None)

    # ---- actions
    def mark_present(self):
        name, rec = self._selected()
        if not name:
            QMessageBox.information(self, "Mark present", "Select a person in the table first.")
            return
        default = datetime.now().strftime("%H:%M:%S") if self.day() == database.today() else "09:00:00"
        text, ok = QInputDialog.getText(self, "Mark present", f"Check-in time for {pretty(name)} (HH:MM:SS):", text=default)
        if not ok:
            return
        try:
            datetime.strptime(text.strip(), "%H:%M:%S")
        except ValueError:
            QMessageBox.warning(self, "Invalid time", "Use the format HH:MM:SS, for example 09:15:00.")
            return
        database.add_record(name, self.day(), text.strip())
        self.refresh()
        self.changed.emit()
        self.notify.emit(f"{pretty(name)} marked present manually")

    def remove_record(self):
        name, rec = self._selected()
        if not rec:
            QMessageBox.information(self, "Remove record", "Select a person who is marked present.")
            return
        if QMessageBox.question(self, "Remove record", f"Remove {pretty(name)}'s attendance for {self.day()}?",
                                defaultButton=QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            database.delete_record(rec["id"])
            self.refresh()
            self.changed.emit()
            self.notify.emit("Record removed")

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export attendance", os.path.join(EXPORT_DIR, f"attendance_{self.day()}.csv"),
                                              "CSV files (*.csv)")
        if not path:
            return
        rows = [(self.day(), pretty(n), "Present" if r else "Absent",
                 r["first_seen"] if r else "", r["last_seen"] if r else "",
                 database.duration_text(r["first_seen"], r["last_seen"]) if r else "") for n, r in self._shown]
        database.export_csv(path, ["Date", "Name", "Status", "Check-in", "Last seen", "Duration"], rows)
        self.notify.emit(f"Exported {len(rows)} rows to {path}")
