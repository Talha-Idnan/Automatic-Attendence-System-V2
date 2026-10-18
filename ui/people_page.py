"""People page: enrolled faces, sample quality, similarity heatmap, enroll / clean / delete."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from core.config import settings as cfg
from core.facestore import pretty
from ui import theme
from ui.widgets import HeatDelegate, NameDelegate, PageHeader, PillDelegate, make_card, make_table


class PeoplePage(QWidget):
    enroll_requested = Signal(str)       # "" = new person, otherwise add samples to that person
    changed = Signal()
    notify = Signal(str)

    def __init__(self, store):
        super().__init__()
        self.store = store
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(18)

        header = PageHeader("People", "Enrolled faces and the quality of their data")
        self.b_new = QPushButton("Enroll new person")
        self.b_new.setObjectName("primary")
        self.b_add = QPushButton("Add samples")
        self.b_clean = QPushButton("Clean samples")
        self.b_del = QPushButton("Delete")
        self.b_del.setObjectName("danger")
        for b in (self.b_clean, self.b_add, self.b_del, self.b_new):
            header.actions.addWidget(b)
        root.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(18)
        root.addLayout(body, 1)

        card, lay = make_card(margins=(8, 8, 8, 8))
        self.table = make_table(["Person", "Samples", "Avg fit", "Weakest", "Data quality"],
                                ["stretch", 90, 90, 90, 190])
        self._d1, self._d2 = NameDelegate(self.table), PillDelegate(self.table)
        self.table.setItemDelegateForColumn(0, self._d1)
        self.table.setItemDelegateForColumn(4, self._d2)
        lay.addWidget(self.table)
        body.addWidget(card, 3)

        card, lay = make_card()
        sec = QLabel("Face similarity")
        sec.setObjectName("section")
        cap = QLabel("How alike the model finds two people (0-1). Lower is safer. "
                     "Siblings often score 0.6-0.8, which the margin rule handles.")
        cap.setObjectName("caption")
        cap.setWordWrap(True)
        self.grid = QTableWidget()
        self.grid.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.grid.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.grid.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.grid.setShowGrid(False)
        self.grid.setStyleSheet("QTableWidget::item { padding: 0; border: none; } "
                                "QHeaderView::section { padding: 8px 0; font-size: 10px; }")
        self._heat = HeatDelegate(self.grid)
        self.grid.setItemDelegate(self._heat)
        self.grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.grid.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.grid.verticalHeader().setDefaultSectionSize(42)
        self.grid.verticalHeader().setFixedWidth(84)
        self.grid.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.legend = QLabel("")
        self.legend.setObjectName("caption")
        self.legend.setWordWrap(True)
        lay.addWidget(sec)
        lay.addWidget(cap)
        lay.addWidget(self.grid, 1)
        lay.addWidget(self.legend)
        card.setFixedWidth(350)
        body.addWidget(card, 0)

        self.b_new.clicked.connect(lambda: self.enroll_requested.emit(""))
        self.b_add.clicked.connect(self._add)
        self.b_clean.clicked.connect(self._clean)
        self.b_del.clicked.connect(self._delete)

    def showEvent(self, e):
        self.refresh()
        super().showEvent(e)

    def selected(self):
        r = self.table.currentRow()
        it = self.table.item(r, 0) if r >= 0 else None
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def refresh(self):
        info = self.store.consistency()
        names = self.store.names()
        self.table.setRowCount(len(names))
        for i, n in enumerate(names):
            d = info[n]
            if d["n"] < 20:
                q, kind = "Add more samples", "warn"
            elif d["min"] < 0.6:
                q, kind = "Clean needed", "warn"
            else:
                q, kind = "Good", "ok"
            vals = [pretty(n), str(d["n"]), f"{d['avg']:.2f}", f"{d['min']:.2f}", q]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c == 0:
                    it.setData(Qt.ItemDataRole.UserRole, n)
                if c == 4:
                    it.setData(Qt.ItemDataRole.UserRole, kind)
                self.table.setItem(i, c, it)
        self._fill_grid(names)

    def _fill_grid(self, names):
        names, M = self.store.similarity_matrix()
        self.grid.clear()
        self.grid.setRowCount(len(names))
        self.grid.setColumnCount(len(names))
        labels = [pretty(n).split()[0][:6] for n in names]
        self.grid.setHorizontalHeaderLabels(labels)
        self.grid.setVerticalHeaderLabels(labels)
        risky = 0
        for i in range(len(names)):
            for j in range(len(names)):
                it = QTableWidgetItem()
                if i != j:
                    v = float(M[i][j])
                    it.setData(Qt.ItemDataRole.UserRole, v)
                    risky += v >= cfg.similar_warn and i < j
                self.grid.setItem(i, j, it)
        if len(names) < 2:
            self.legend.setText("Enroll at least two people to compare them.")
        elif risky:
            self.legend.setText(f"{risky} pair(s) look very alike. If they are not relatives, "
                                "re-enroll one of them with only that person in frame.")
        else:
            self.legend.setText("All pairs are clearly separated.")

    # ---- actions
    def _add(self):
        n = self.selected()
        if not n:
            QMessageBox.information(self, "Add samples", "Select a person in the table first.")
            return
        self.enroll_requested.emit(n)

    def _clean(self):
        if not self.store.people:
            return
        res = self.store.clean()
        self.store.save()
        removed = sum(b - a for b, a in res.values())
        self.refresh()
        self.changed.emit()
        self.notify.emit(f"Cleaned: removed {removed} weak sample(s)")

    def _delete(self):
        n = self.selected()
        if not n:
            QMessageBox.information(self, "Delete", "Select a person in the table first.")
            return
        if QMessageBox.question(self, "Delete person",
                                f"Delete {pretty(n)} and all face samples?\nTheir past attendance records are kept.",
                                defaultButton=QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.store.delete(n)
            self.store.save()
            self.refresh()
            self.changed.emit()
            self.notify.emit(f"{pretty(n)} deleted")
