"""Background thread: camera + detection + recognition (or enrollment capture)."""
import time
from datetime import datetime

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from core import database
from core.config import settings as cfg
from core.engine import Camera, Tracker

_ENROLL_HINTS = {"too far": "Move closer", "face the camera": "Face the camera",
                 "blurry": "Hold still / add light"}


class RecognitionWorker(QThread):
    frame_ready = Signal(object, object, float)     # QImage, overlays, fps
    attendance_marked = Signal(str, str)            # name, time  (first sighting of the day only)
    device_ready = Signal(str)
    failed = Signal(str)
    sample_added = Signal(int)                      # enroll mode: samples captured so far
    feedback = Signal(str, bool)                    # enroll mode: message, ok

    def __init__(self, engine, store, mode="recognize", parent=None):
        super().__init__(parent)
        self.engine, self.store, self.mode = engine, store, mode
        self._running = True
        self.samples = []
        self.auto = False
        self._want = False
        self._last_auto = 0.0
        self._last_fb = None
        self.tracker, self.verified, self.last_mark = Tracker(), {}, {}

    # ---- control (called from the UI thread)
    def request_sample(self):
        self._want = True

    def reset_samples(self):
        self.samples = []
        self.sample_added.emit(0)

    def stop(self):
        self._running = False
        self.wait(5000)

    # ---- thread body
    def run(self):
        cam = None
        try:
            self.device_ready.emit(self.engine.load())
            if self.mode == "recognize":
                self.engine.set_gallery(self.store.people)
            cam = Camera(cfg.cam_index)
        except Exception as e:                       # model load / camera problems
            self.failed.emit(str(e))
            return
        fps, last, last_seq = 0.0, time.time(), -1
        try:
            while self._running:
                last_seq, frame = cam.read(last_seq)
                if frame is None:
                    self.msleep(3)
                    continue
                overlays = self._recognize(frame) if self.mode == "recognize" else self._enroll(frame)
                now = time.time()
                fps = 0.9 * fps + 0.1 * (1 / max(now - last, 1e-6))
                last = now
                self.frame_ready.emit(self._to_qimage(frame), overlays, fps)
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")
        finally:
            if cam:
                cam.release()

    @staticmethod
    def _to_qimage(frame):
        rgb = np.ascontiguousarray(frame[:, :, ::-1])
        h, w, _ = rgb.shape
        return QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()

    # ---- recognition
    def _recognize(self, frame):
        e = self.engine
        boxes, emb, rejected, yaws = e.detect_and_embed(frame)
        overlays = [dict(box=r[0], label=r[1], kind="muted") for r in rejected if r[2] is None]
        obs = []
        if emb is not None:
            if e.names:
                for box, row, yw in zip(boxes, e.scores(emb), yaws):
                    cand, best = e.decide(row)
                    obs.append(dict(box=box, cand=cand, score=best, frontal=True, yaw=yw))
            else:
                overlays += [dict(box=b, label="No one enrolled", kind="muted") for b in boxes]
        if e.names:                                  # turned faces still carry their yaw (liveness)
            for box, reason, yw in rejected:
                if yw is not None:
                    obs.append(dict(box=box, cand=None, score=0.0, frontal=False, yaw=yw))
        now = time.time()
        for o, (label, kind, name) in zip(obs, self.tracker.update(obs, self.verified)):
            overlays.append(dict(box=o["box"], label=label, kind=kind))
            if name and now - self.last_mark.get(name, 0) > cfg.cooldown:
                self.last_mark[name] = now
                if database.mark_present(name):
                    self.attendance_marked.emit(name, datetime.now().strftime("%H:%M:%S"))
        return overlays

    # ---- enrollment
    def _enroll(self, frame):
        boxes, emb, rejected, _ = self.engine.detect_and_embed(frame)
        overlays = [dict(box=b, label="", kind="ok") for b in boxes]
        overlays += [dict(box=r[0], label=r[1], kind="muted") for r in rejected]
        total = len(boxes) + len(rejected)
        if total == 0:
            msg, ok = "No face detected", False
        elif total > 1:
            msg, ok = "Only one person should be in frame", False
        elif rejected:
            msg, ok = _ENROLL_HINTS.get(rejected[0][1], rejected[0][1]), False
        else:
            msg, ok = "Ready", True
        if (msg, ok) != self._last_fb:
            self._last_fb = (msg, ok)
            self.feedback.emit(msg, ok)

        now = time.time()
        if self._want or (self.auto and ok and now - self._last_auto > 0.35):
            self._want = False
            if ok:
                self.samples.append(emb[0].cpu().numpy())
                self._last_auto = now
                self.sample_added.emit(len(self.samples))
        return overlays
