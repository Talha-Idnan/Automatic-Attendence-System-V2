"""Reusable widgets: video view with overlays, stat cards, bar chart, table helpers, delegates."""
import hashlib
import math

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QFont, QFontMetrics, QPen
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFrame, QHBoxLayout, QHeaderView, QLabel,
                               QSizePolicy, QSlider, QStyle, QStyledItemDelegate, QStyleOptionViewItem,
                               QTableWidget, QVBoxLayout, QWidget)

from core.config import settings as cfg
from core.facestore import pretty
from ui import theme

KIND_COLORS = {"ok": theme.OK, "warn": theme.WARN, "bad": theme.BAD, "muted": theme.MUTED}
AVATAR_COLORS = ["#5B8CFF", "#3DD68C", "#F4B942", "#F0677A", "#B48CFF", "#4CC9F0", "#FF9F6B", "#7BD389"]
UserRole = Qt.ItemDataRole.UserRole


def color_for(name):
    h = int(hashlib.md5(str(name).lower().encode()).hexdigest(), 16)
    return QColor(AVATAR_COLORS[h % len(AVATAR_COLORS)])


def initials(name):
    parts = str(name).split()
    return "".join(p[0] for p in parts[:2]).upper() or "?"


def _font(base, px, bold=False):
    f = QFont(base)
    f.setPixelSize(px)
    f.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    return f


# ---------------------------------------------------------------- video
class VideoWidget(QWidget):
    """Shows a camera frame with modern face-box overlays, a HUD and a liveness banner."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(480, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._img, self._overlays, self._fps = None, [], 0.0
        self._placeholder = ("Camera is off", "Press Start camera to begin")

    def set_placeholder(self, title, sub=""):
        self._placeholder = (title, sub)
        self.update()

    def clear(self):
        self._img, self._overlays = None, []
        self.update()

    def set_frame(self, img, overlays, fps):
        self._img, self._overlays, self._fps = img, overlays, fps
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        clip = QPainterPath()
        clip.addRoundedRect(rect, 14, 14)
        p.setClipPath(clip)
        p.fillRect(rect, QColor("#090C12"))
        AC = Qt.AlignmentFlag.AlignCenter

        if self._img is None:
            title, sub = self._placeholder
            p.setPen(QColor(theme.TEXT))
            p.setFont(_font(self.font(), 18, True))
            p.drawText(rect.adjusted(0, -16, 0, 0), AC, title)
            p.setPen(QColor(theme.MUTED))
            p.setFont(_font(self.font(), 13))
            p.drawText(rect.adjusted(0, 34, 0, 0), AC, sub)
        else:
            iw, ih = self._img.width(), self._img.height()
            s = min(rect.width() / iw, rect.height() / ih)
            w, h = iw * s, ih * s
            ox, oy = rect.left() + (rect.width() - w) / 2, rect.top() + (rect.height() - h) / 2
            p.drawImage(QRectF(ox, oy, w, h), self._img)
            for ov in self._overlays:
                self._draw_face(p, ov, ox, oy, s)
            self._draw_banner(p, ox, oy, w, h)
            self._draw_hud(p, rect)

        p.setClipping(False)
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 14, 14)

    def _draw_face(self, p, ov, ox, oy, s):
        x1, y1, x2, y2 = ov["box"]
        b = QRectF(ox + x1 * s, oy + y1 * s, (x2 - x1) * s, (y2 - y1) * s)
        col = QColor(KIND_COLORS[ov["kind"]])
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), 80), 1))
        p.drawRoundedRect(b, 6, 6)
        L = min(b.width(), b.height()) * 0.22
        p.setPen(QPen(col, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for cx, cy, dx, dy in ((b.left(), b.top(), 1, 1), (b.right(), b.top(), -1, 1),
                               (b.left(), b.bottom(), 1, -1), (b.right(), b.bottom(), -1, -1)):
            p.drawLine(QPointF(cx, cy), QPointF(cx + dx * L, cy))
            p.drawLine(QPointF(cx, cy), QPointF(cx, cy + dy * L))
        text = ov["label"]
        if text:
            f = _font(self.font(), 12, True)
            tw = QFontMetrics(f).horizontalAdvance(text)
            pill = QRectF(b.left(), b.top() - 31, tw + 20, 24)
            if pill.top() < oy + 4:
                pill.moveTop(b.top() + 8)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(col.red(), col.green(), col.blue(), 235))
            p.drawRoundedRect(pill, 12, 12)
            p.setPen(QColor("#0D1016"))
            p.setFont(f)
            p.drawText(pill, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_banner(self, p, ox, oy, w, h):
        for ov in self._overlays:
            t = ov["label"].lower()
            if "turn your head" in t or "look at the camera" in t:
                f = _font(self.font(), 18, True)
                tw = QFontMetrics(f).horizontalAdvance(ov["label"])
                box = QRectF(ox + (w - tw - 44) / 2, oy + h - 74, tw + 44, 46)
                p.setPen(QPen(QColor(theme.WARN), 1.5))
                p.setBrush(QColor(9, 12, 18, 225))
                p.drawRoundedRect(box, 23, 23)
                p.setPen(QColor(theme.WARN))
                p.setFont(f)
                p.drawText(box, Qt.AlignmentFlag.AlignCenter, ov["label"])
                return

    def _draw_hud(self, p, rect):
        f = _font(self.font(), 12, True)
        for text, color, right in (("●  LIVE", theme.ACCENT, False),
                                   (f"{self._fps:.0f} FPS", theme.OK if self._fps >= 30 else theme.WARN, True)):
            tw = QFontMetrics(f).horizontalAdvance(text)
            x = rect.right() - tw - 38 if right else rect.left() + 14
            pill = QRectF(x, rect.top() + 14, tw + 24, 26)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(9, 12, 18, 190))
            p.drawRoundedRect(pill, 13, 13)
            p.setPen(QColor(color))
            p.setFont(f)
            p.drawText(pill, Qt.AlignmentFlag.AlignCenter, text)


# ---------------------------------------------------------------- cards / headers
class StatCard(QFrame):
    def __init__(self, title, value="–", sub="", color=None):
        super().__init__()
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(2)
        self._t = QLabel(title.upper())
        self._t.setObjectName("cardTitle")
        self._v = QLabel(str(value))
        self._v.setObjectName("cardValue")
        if color:
            self._v.setStyleSheet(f"color: {color};")
        self._s = QLabel(sub)
        self._s.setObjectName("caption")
        for w in (self._t, self._v, self._s):
            lay.addWidget(w)

    def set(self, value, sub=None):
        self._v.setText(str(value))
        if sub is not None:
            self._s.setText(sub)


def make_card(inner_layout_cls=QVBoxLayout, margins=(20, 18, 20, 18), spacing=12):
    card = QFrame()
    card.setObjectName("card")
    lay = inner_layout_cls(card)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    return card, lay


class PageHeader(QWidget):
    def __init__(self, title, subtitle=""):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        left = QVBoxLayout()
        left.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("title")
        s = QLabel(subtitle)
        s.setObjectName("subtitle")
        left.addWidget(t)
        left.addWidget(s)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(10)
        lay.addLayout(left)
        lay.addStretch()
        lay.addLayout(self.actions)


# ---------------------------------------------------------------- bar chart
class BarChart(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(240)
        self._data = []

    def set_data(self, data):
        """data: list of (label, value)."""
        self._data = list(data)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        left, right, top, bottom = 34, 6, 18, 28
        plot = QRectF(left, top, W - left - right, H - top - bottom)
        small = _font(self.font(), 11)
        p.setFont(small)
        if not self._data or max(v for _, v in self._data) == 0:
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRectF(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, "No attendance recorded in this range")
            return
        vmax = max(4, math.ceil(max(v for _, v in self._data) / 4) * 4)
        for i in range(5):                                           # grid + y labels
            y = plot.bottom() - plot.height() * i / 4
            p.setPen(QPen(QColor(theme.ROW_LINE if i else theme.BORDER), 1))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRectF(0, y - 9, left - 8, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{vmax * i / 4:g}")
        n = len(self._data)
        slot = plot.width() / n
        bw = min(slot * 0.56, 38)
        step = max(1, math.ceil(n / 12))
        for i, (label, v) in enumerate(self._data):
            cx = plot.left() + slot * (i + 0.5)
            if v > 0:
                bh = plot.height() * v / vmax
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(theme.ACCENT))
                p.drawRoundedRect(QRectF(cx - bw / 2, plot.bottom() - bh, bw, bh), 4, 4)
                if n <= 16:
                    p.setPen(QColor(theme.TEXT))
                    p.drawText(QRectF(cx - 20, plot.bottom() - bh - 20, 40, 16), Qt.AlignmentFlag.AlignCenter, f"{v}")
            if i % step == 0:
                p.setPen(QColor(theme.MUTED))
                p.drawText(QRectF(cx - slot, plot.bottom() + 6, slot * 2, 18), Qt.AlignmentFlag.AlignCenter, label)


# ---------------------------------------------------------------- tables
def make_table(headers, modes=None):
    """modes: per column 'stretch' or a pixel width."""
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels([h.upper() for h in headers])
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(54)
    t.setShowGrid(False)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    t.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    t.horizontalHeader().setHighlightSections(False)
    t.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    modes = modes or ["stretch"] * len(headers)
    for i, m in enumerate(modes):
        if m == "stretch":
            t.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        else:
            t.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            t.setColumnWidth(i, int(m))
    return t


class _BaseDelegate(QStyledItemDelegate):
    def _base(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)


class NameDelegate(_BaseDelegate):
    """Avatar circle with initials + display name."""

    def paint(self, painter, option, index):
        self._base(painter, option, index)
        raw, text = index.data(UserRole) or index.data(), index.data()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r, d = option.rect, 32
        circle = QRectF(r.left() + 14, r.center().y() - d / 2, d, d)
        col = color_for(raw)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(col.red(), col.green(), col.blue(), 55))
        painter.drawEllipse(circle)
        painter.setPen(col.lighter(125))
        painter.setFont(_font(painter.font(), 12, True))
        painter.drawText(circle, Qt.AlignmentFlag.AlignCenter, initials(text))
        painter.setPen(QColor(theme.TEXT))
        painter.setFont(_font(painter.font(), 13))
        painter.drawText(QRectF(circle.right() + 12, r.top(), r.width() - d - 40, r.height()),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        painter.restore()


class PillDelegate(_BaseDelegate):
    """Colored status pill. Item text = label, UserRole = 'ok' | 'warn' | 'bad' | 'muted'."""

    def paint(self, painter, option, index):
        self._base(painter, option, index)
        text, kind = index.data(), index.data(UserRole) or "muted"
        col = QColor(KIND_COLORS.get(kind, theme.MUTED))
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        f = _font(painter.font(), 12, True)
        tw = QFontMetrics(f).horizontalAdvance(text)
        r = option.rect
        pill = QRectF(r.left() + 12, r.center().y() - 12, tw + 26, 24)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(col.red(), col.green(), col.blue(), 38))
        painter.drawRoundedRect(pill, 12, 12)
        painter.setBrush(col)
        painter.drawEllipse(QPointF(pill.left() + 12, pill.center().y()), 3, 3)
        painter.setPen(col)
        painter.setFont(f)
        painter.drawText(pill.adjusted(20, 0, 0, 0), Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()


class ProgressDelegate(_BaseDelegate):
    """Percent bar. UserRole = float 0..100."""

    def paint(self, painter, option, index):
        self._base(painter, option, index)
        v = float(index.data(UserRole) or 0)
        col = QColor(theme.OK if v >= 75 else theme.WARN if v >= 50 else theme.BAD)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = option.rect
        label_w = 48
        track = QRectF(r.left() + 12, r.center().y() - 4, r.width() - 24 - label_w, 8)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.BORDER))
        painter.drawRoundedRect(track, 4, 4)
        painter.setBrush(col)
        painter.drawRoundedRect(QRectF(track.left(), track.top(), max(track.width() * v / 100, 8 if v > 0 else 0), 8), 4, 4)
        painter.setPen(QColor(theme.TEXT))
        painter.setFont(_font(painter.font(), 12, True))
        painter.drawText(QRectF(track.right() + 6, r.top(), label_w, r.height()),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, f"{v:.0f}%")
        painter.restore()


class HeatDelegate(_BaseDelegate):
    """Similarity heat cell. UserRole = similarity (float) or None for the diagonal."""

    def paint(self, painter, option, index):
        v = index.data(UserRole)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(option.rect).adjusted(3, 3, -3, -3)
        if v is None:
            painter.setPen(QColor(theme.MUTED))
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, "–")
        else:
            col = QColor(theme.BAD if v >= cfg.similar_warn else theme.WARN if v >= 0.5 else theme.OK)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(col.red(), col.green(), col.blue(), 48))
            painter.drawRoundedRect(r, 7, 7)
            painter.setPen(col)
            painter.setFont(_font(painter.font(), 12, True))
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, f"{v:.2f}")
        painter.restore()


# ---------------------------------------------------------------- settings rows
class SliderRow(QWidget):
    """Title + description on the left, slider + live value on the right."""

    def __init__(self, title, desc, lo, hi, step, value, fmt="{:.2f}"):
        super().__init__()
        self.lo, self.step, self.fmt = lo, step, fmt
        self.integer = isinstance(step, int) and isinstance(lo, int)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 6)
        left = QVBoxLayout()
        left.setSpacing(2)
        t = QLabel(title)
        d = QLabel(desc)
        d.setObjectName("caption")
        d.setWordWrap(True)
        left.addWidget(t)
        left.addWidget(d)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, round((hi - lo) / step))
        self.slider.setFixedWidth(260)
        self.val = QLabel()
        self.val.setFixedWidth(60)
        self.val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.slider.valueChanged.connect(lambda _: self.val.setText(self.fmt.format(self.value())))
        lay.addLayout(left, 1)
        lay.addWidget(self.slider)
        lay.addWidget(self.val)
        self.set_value(value)

    def value(self):
        v = self.lo + self.slider.value() * self.step
        return int(round(v)) if self.integer else round(v, 4)

    def set_value(self, v):
        self.slider.setValue(round((v - self.lo) / self.step))
        self.val.setText(self.fmt.format(self.value()))


def divider():
    d = QFrame()
    d.setObjectName("divider")
    return d
