"""
Face engine: camera, MTCNN detection, FaceNet embeddings, matching and the liveness tracker.

Pipeline per frame:
  detect (MTCNN) -> quality gate -> align -> embed face + mirrored face (FaceNet) -> match
Torch is imported lazily (first call to Engine.load) so the UI can start instantly.
"""
import random
import threading
import time
from collections import Counter, deque

import cv2
import numpy as np

from core.config import settings as cfg
from core.facestore import pretty


# ---------------------------------------------------------------- camera
class Camera:
    """Reads frames in a background thread so the main loop never waits on the webcam."""

    def __init__(self, index=0):
        self.cap = None
        for backend in (cv2.CAP_MSMF, cv2.CAP_DSHOW, cv2.CAP_ANY):
            for idx in dict.fromkeys([index, 0, 1, 2]):
                cap = cv2.VideoCapture(idx, backend)
                if cap.isOpened():
                    ok, _ = cap.read()
                    if ok:
                        self.cap = cap
                        break
                cap.release()
            if self.cap:
                break
        if self.cap is None:
            raise RuntimeError("No camera found. Check that the webcam is plugged in, that Windows "
                               "camera privacy settings allow desktop apps, and that no other app "
                               "(Zoom, Teams, browser) is using it.")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.frame, self.seq, self.running = None, 0, True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self.running:
            ok, f = self.cap.read()
            if ok:
                self.frame = f
                self.seq += 1

    def read(self, last_seq=-1):
        """Returns (seq, frame). frame is None if there is nothing new since last_seq."""
        s, f = self.seq, self.frame
        if f is None or s == last_seq:
            return s, None
        return s, f.copy()

    def release(self):
        self.running = False
        time.sleep(0.1)
        self.cap.release()


# ---------------------------------------------------------------- model
class Engine:
    def __init__(self):
        self.ready = False
        self.device_name = "not loaded"
        self.names, self.gallery = [], []
        self._lock = threading.Lock()

    def load(self):
        """Loads the models once. Safe to call repeatedly. Returns the device name."""
        with self._lock:
            if self.ready:
                return self.device_name
            import torch
            from facenet_pytorch import MTCNN, InceptionResnetV1
            self.torch = torch
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            torch.backends.cudnn.benchmark = True
            self.mtcnn = MTCNN(keep_all=True, device=self.device, min_face_size=60,
                               factor=0.8, post_process=False)
            self.resnet = InceptionResnetV1(pretrained="vggface2").eval().to(self.device)
            with torch.no_grad():                                   # warm-up pass
                self.resnet(torch.zeros(2, 3, 160, 160, device=self.device))
            self.device_name = (torch.cuda.get_device_name(0) if self.device.type == "cuda"
                                else "CPU (slow)")
            self.ready = True
            return self.device_name

    def set_gallery(self, people):
        self.names = list(people.keys())
        self.gallery = [self.torch.from_numpy(np.asarray(people[n])).float().to(self.device)
                        for n in self.names]

    # ---- detection + embedding
    def detect_and_embed(self, frame):
        """
        Returns (boxes, embeddings, rejected, yaws)
          boxes      : boxes of faces that passed the quality gate
          embeddings : (N,512) L2-normalized tensor (aligned + flip-averaged), or None
          rejected   : list of (box, reason, yaw_or_None) for faces that failed the gate
          yaws       : signed head-turn value for each accepted face
        """
        torch = self.torch
        with torch.no_grad():
            h, w = frame.shape[:2]
            scale = cfg.detect_width / w
            small = cv2.resize(frame, (cfg.detect_width, int(h * scale)))
            boxes, probs, lms = self.mtcnn.detect(cv2.cvtColor(small, cv2.COLOR_BGR2RGB), landmarks=True)
            if boxes is None:
                return [], None, [], []

            rgb_full = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            crops, good, rejected, yaws = [], [], [], []
            for box, p, lm in zip(boxes, probs, lms):
                if p is None or p < cfg.min_conf:
                    continue
                x1, y1, x2, y2 = (box / scale).astype(int)
                lm = lm / scale
                bw, bh = x2 - x1, y2 - y1
                rect = (max(x1, 0), max(y1, 0), min(x2, w), min(y2, h))

                if min(bw, bh) < cfg.min_face:                       # gate 1: size
                    rejected.append((rect, "too far", None))
                    continue

                le, re, nose = lm[0], lm[1], lm[2]                   # gate 2: head pose
                eye_dist = max(float(np.linalg.norm(re - le)), 1e-6)
                yaw = (nose[0] - (le[0] + re[0]) / 2) / eye_dist     # signed: + = nose toward image-right
                if abs(yaw) > cfg.yaw_max:
                    rejected.append((rect, "face the camera", float(yaw)))
                    continue

                angle = float(np.degrees(np.arctan2(re[1] - le[1], re[0] - le[0])))   # alignment
                if abs(angle) > 2:
                    M = cv2.getRotationMatrix2D(((x1 + x2) / 2.0, (y1 + y2) / 2.0), angle, 1.0)
                    src = cv2.warpAffine(rgb_full, M, (w, h), flags=cv2.INTER_LINEAR,
                                         borderMode=cv2.BORDER_REPLICATE)
                else:
                    src = rgb_full
                mw, mh = int(bw * cfg.crop_margin), int(bh * cfg.crop_margin)
                crop = cv2.resize(src[max(y1 - mh, 0):min(y2 + mh, h), max(x1 - mw, 0):min(x2 + mw, w)],
                                  (160, 160))

                sharp = cv2.Laplacian(cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY), cv2.CV_64F).var()
                if sharp < cfg.blur_min:                             # gate 3: sharpness
                    rejected.append((rect, "blurry", None))
                    continue

                crops.append(crop)
                good.append(rect)
                yaws.append(float(yaw))

            if not crops:
                return [], None, rejected, []

            batch = torch.from_numpy(np.stack(crops)).permute(0, 3, 1, 2).float().to(self.device)
            batch = (batch - 127.5) / 128.0
            n = batch.shape[0]
            both = torch.cat([batch, torch.flip(batch, dims=[3])])   # face + mirrored face
            e = torch.nn.functional.normalize(self.resnet(both), dim=1)
            return good, torch.nn.functional.normalize(e[:n] + e[n:], dim=1), rejected, yaws

    # ---- matching
    def scores(self, emb):
        """(F,P) score per face per enrolled person = mean of their top-K similarities."""
        cols = []
        for E in self.gallery:
            sims = emb @ E.T
            k = min(cfg.top_k, sims.shape[1])
            cols.append(sims.topk(k, dim=1).values.mean(dim=1))
        return self.torch.stack(cols, dim=1).cpu().numpy()

    def decide(self, row):
        """Returns (candidate_name_or_None, best_score)."""
        order = np.argsort(row)[::-1]
        best = float(row[order[0]])
        if best < cfg.threshold:
            return None, best
        if len(order) > 1 and best - row[order[1]] < cfg.margin:
            return None, best                                        # too close to call
        return self.names[order[0]], best


# ---------------------------------------------------------------- liveness tracker
class Tracker:
    """
    Follows each face across frames. Every face is in one of three states:
      id        -> voting on a name (needs vote_needed of the last vote_len frames)
      challenge -> liveness: turn head to a random side, then look back at the camera
      verified  -> identity + liveness confirmed -> attendance allowed
    update() returns one (label, kind, verified_name_or_None) per observation,
    where kind is one of "ok", "warn", "bad", "muted".
    """

    TRACK_TTL = 1.5          # seconds a face may vanish before its track is dropped
    BACK_FRONTAL = "ok"

    def __init__(self):
        self.tracks = []

    def _assign(self, box, used):
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        best, bd = None, 1e9
        for t in self.tracks:
            if id(t) in used:
                continue
            d = ((t["c"][0] - cx) ** 2 + (t["c"][1] - cy) ** 2) ** 0.5
            if d < bd:
                best, bd = t, d
        if best is None or bd > 120:
            best = {"state": "id", "hist": deque(maxlen=cfg.vote_len), "name": None,
                    "score": 0.0, "msg": None}
            self.tracks.append(best)
        best["c"] = (cx, cy)
        return best

    @staticmethod
    def _reset(t, msg=None, now=0.0):
        t["state"], t["name"] = "id", None
        t["hist"].clear()
        t["msg"] = (msg, now + 2.0) if msg else None

    def update(self, obs, verified):
        now = time.time()
        self.tracks = [t for t in self.tracks if now - t.get("t", now) < self.TRACK_TTL]
        used, out = set(), []
        for o in obs:
            t = self._assign(o["box"], used)
            t["t"] = now
            used.add(id(t))
            out.append(self._step(t, o, now, verified))
        return out

    def _label(self, t):
        return f"{pretty(t['name'])}  {t['score']:.2f}"

    def _step(self, t, o, now, verified):
        if o["frontal"]:
            t["score"] = o["score"]

        if t["state"] == "verified":                      # reset if a different person appears
            if o["frontal"] and o["cand"] and o["cand"] != t["name"]:
                self._reset(t)
            else:
                verified[t["name"]] = now
                return self._label(t), "ok", t["name"]

        if t["state"] == "challenge":
            name = t["name"]
            if now > t["deadline"]:
                self._reset(t, "Liveness failed", now)
                return "Liveness failed", "bad", None
            sign = 1 if t["dir"] == "left" else -1
            if cfg.flip_directions:
                sign = -sign
            if not t["turned"] and sign * o["yaw"] >= cfg.turn_min:
                t["turned"] = True
            if t["turned"]:
                if o["frontal"] and abs(o["yaw"]) <= cfg.back_max:
                    if o["cand"] == name:
                        t["state"] = "verified"
                        verified[name] = now
                        return self._label(t), "ok", name
                    if o["cand"] is not None:             # someone else came back
                        self._reset(t, "Person changed", now)
                        return "Person changed", "bad", None
                return f"{pretty(name)} - now look at the camera", "warn", None
            left = int(t["deadline"] - now) + 1
            return f"{pretty(name)} - turn your head {t['dir'].upper()} ({left}s)", "warn", None

        if t["msg"] and now < t["msg"][1]:
            return t["msg"][0], "bad", None
        if not o["frontal"]:
            return "face the camera", "muted", None
        t["hist"].append(o["cand"] or "Unknown")
        top, n = Counter(t["hist"]).most_common(1)[0]
        if top != "Unknown" and n >= cfg.vote_needed:
            if (not cfg.liveness) or now - verified.get(top, 0) < cfg.verify_valid:
                t["state"], t["name"] = "verified", top
                verified[top] = now
                return self._label(t), "ok", top
            t.update(state="challenge", name=top, dir=random.choice(("left", "right")),
                     deadline=now + cfg.challenge_timeout, turned=False)
            return f"{pretty(top)} - turn your head {t['dir'].upper()}", "warn", None
        if o["cand"]:
            return f"checking...  {o['score']:.2f}", "warn", None
        return f"Unknown  {o['score']:.2f}", "bad", None
