"""Reports page: attendance trend chart, per-person summary and CSV exports."""
import os
from collections import defaultdict
from datetime import datetime, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLabel, QPushButton, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from core import database
from core.config import EXPORT_DIR
from core.facestore import pretty
from ui import theme
from ui.widgets import BarChart, NameDelegate, PageHeader, ProgressDelegate, StatCard, make_card, make_table

RANGES = {"Last 7 days": 7, "Last 14 days": 14, "Last 30 days": 30, "Last 90 days": 90}


class ReportsPage(QWidget):
    notify = Signal(str)

    def __init__(self, store):
        super().__init__()
        self.store = store
        self._summary = []
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(18)

        header = PageHeader("Reports", "Attendance trends and per-person summary")
        self.range = QComboBox()
        self.range.addItems(RANGES)
        self.range.setCurrentText("Last 14 days")
        self.range.setFixedWidth(150)
        self.b_sum = QPushButton("Export summary")
        self.b_all = QPushButton("Export all records")
        for w in (self.range, self.b_sum, self.b_all):
            header.actions.addWidget(w)
        root.addWidget(header)

        stats = QHBoxLayout()
        stats.setSpacing(14)
        self.s_days = StatCard("Session days", "0", "days with any attendance")
        self.s_avg = StatCard("Average attendance", "–", color=theme.ACCENT)
        self.s_checks = StatCard("Total check-ins", "0")
        self.s_top = StatCard("Best attendance", "–", color=theme.OK)
        for s in (self.s_days, self.s_avg, self.s_checks, self.s_top):
            stats.addWidget(s)
        root.addLayout(stats)

        body = QHBoxLayout()
        body.setSpacing(18)
        root.addLayout(body, 1)

        card, lay = make_card()
        sec = QLabel("People present per day")
        sec.setObjectName("section")
        self.chart = BarChart()
        lay.addWidget(sec)
        lay.addWidget(self.chart, 1)
        body.addWidget(card, 5)

        card, lay = make_card(margins=(8, 14, 8, 8))
        sec = QLabel("  Per person")
        sec.setObjectName("section")
        self.table = make_table(["Person", "Days", "Attendance", "Avg check-in"], ["stretch", 70, 190, 110])
        self._d1, self._d2 = NameDelegate(self.table), ProgressDelegate(self.table)
        self.table.setItemDelegateForColumn(0, self._d1)
        self.table.setItemDelegateForColumn(2, self._d2)
        lay.addWidget(sec)
        lay.addWidget(self.table, 1)
        body.addWidget(card, 6)

        self.range.currentIndexChanged.connect(self.refresh)
        self.b_sum.clicked.connect(self.export_summary)
        self.b_all.clicked.connect(self.export_all)

    def showEvent(self, e):
        self.refresh()
        super().showEvent(e)

    def _range(self):
        days = RANGES[self.range.currentText()]
        end = datetime.now().date()
        return end - timedelta(days=days - 1), end

    def refresh(self, *_):
        start, end = self._range()
        recs = database.records_between(start.isoformat(), end.isoformat())
        per_day = defaultdict(int)
        by_person = defaultdict(list)
        for r in recs:
            per_day[r["date"]] += 1
            by_person[r["name"]].append(r)
        session_days = len(per_day)

        # chart: every calendar day in range
        n = (end - start).days + 1
        data = []
        for i in range(n):
            d = start + timedelta(days=i)
            data.append((f"{d.day} {d.strftime('%b')}" if n > 7 else d.strftime("%a %d"), per_day.get(d.isoformat(), 0)))
        self.chart.set_data(data)

        # per person
        people = list(dict.fromkeys(self.store.names() + list(by_person)))
        summary = []
        for name in people:
            rows = by_person.get(name, [])
            pct = 100 * len(rows) / session_days if session_days else 0.0
            secs = [int(datetime.strptime(r["first_seen"], "%H:%M:%S").hour * 3600
                        + datetime.strptime(r["first_seen"], "%H:%M:%S").minute * 60
                        + datetime.strptime(r["first_seen"], "%H:%M:%S").second) for r in rows]
            avg = f"{int(sum(secs) / len(secs)) // 3600:02d}:{(int(sum(secs) / len(secs)) % 3600) // 60:02d}" if secs else "–"
            summary.append((name, len(rows), pct, avg))
        summary.sort(key=lambda x: (-x[2], x[0].lower()))
        self._summary = summary

        self.table.setRowCount(len(summary))
        for i, (name, days, pct, avg) in enumerate(summary):
            for c, v in enumerate([pretty(name), str(days), f"{pct:.0f}%", avg]):
                it = QTableWidgetItem(v)
                if c == 0:
                    it.setData(Qt.ItemDataRole.UserRole, name)
                if c == 2:
                    it.setData(Qt.ItemDataRole.UserRole, pct)
                self.table.setItem(i, c, it)

        self.s_days.set(session_days)
        self.s_checks.set(len(recs))
        if summary and session_days:
            self.s_avg.set(f"{sum(s[2] for s in summary) / len(summary):.0f}%")
            top = summary[0]
            self.s_top.set(pretty(top[0]), f"{top[2]:.0f}% of session days")
        else:
            self.s_avg.set("–")
            self.s_top.set("–", "")

    def _save_path(self, name):
        path, _ = QFileDialog.getSaveFileName(self, "Export", os.path.join(EXPORT_DIR, name), "CSV files (*.csv)")
        return path

    def export_summary(self):
        path = self._save_path(f"summary_{database.today()}.csv")
        if path:
            database.export_csv(path, ["Name", "Days present", "Attendance %", "Avg check-in"],
                                [(pretty(n), d, f"{p:.1f}", a) for n, d, p, a in self._summary])
            self.notify.emit(f"Summary exported to {path}")

    def export_all(self):
        path = self._save_path(f"attendance_all_{database.today()}.csv")
        if path:
            recs = database.records_between("0000-01-01", "9999-12-31")
            database.export_csv(path, ["Date", "Name", "Check-in", "Last seen", "Duration"],
                                [(r["date"], pretty(r["name"]), r["first_seen"], r["last_seen"],
                                  database.duration_text(r["first_seen"], r["last_seen"])) for r in recs])
            self.notify.emit(f"Exported {len(recs)} records to {path}")
