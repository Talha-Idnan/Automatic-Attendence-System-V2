"""Paths and user-adjustable settings (saved to data/settings.json)."""
import json
import os
from dataclasses import dataclass, asdict, fields

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(APP_DIR, "data")
EXPORT_DIR = os.path.join(DATA_DIR, "exports")
FACES_FILE = os.path.join(DATA_DIR, "faces_v2.pkl")      # enrolled face fingerprints
DB_FILE = os.path.join(DATA_DIR, "attendance.db")        # attendance records
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
os.makedirs(EXPORT_DIR, exist_ok=True)


@dataclass
class Settings:
    # camera
    cam_index: int = 0
    detect_width: int = 480          # frame is shrunk to this width for detection (speed)
    # recognition
    threshold: float = 0.65          # min cosine similarity to accept a person
    margin: float = 0.08             # winner must beat runner-up by this much
    top_k: int = 3                   # person score = mean of their K best-matching samples
    vote_len: int = 7                # frames remembered per face
    vote_needed: int = 5             # frames that must agree before a name is confirmed
    cooldown: float = 3.0            # seconds between attendance updates per person
    similar_warn: float = 0.70       # warn at enrollment if two people are this similar
    # liveness
    liveness: bool = True
    challenge_timeout: float = 8.0   # seconds allowed to complete the head turn
    turn_min: float = 0.30           # how far the head must turn
    back_max: float = 0.15           # how frontal the face must be again afterwards
    verify_valid: float = 30.0       # seconds a verified person can skip the challenge
    flip_directions: bool = False    # set True if "LEFT" feels like your right
    # quality gate
    min_conf: float = 0.92
    min_face: int = 60
    blur_min: float = 20.0
    yaw_max: float = 0.35
    crop_margin: float = 0.20

    @classmethod
    def load(cls):
        s = cls()
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            for fld in fields(cls):
                if fld.name in data:
                    setattr(s, fld.name, type(getattr(s, fld.name))(data[fld.name]))
        except (OSError, ValueError, TypeError):
            pass
        return s

    def save(self):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

    def reset(self):
        for fld in fields(self):
            setattr(self, fld.name, fld.default)


settings = Settings.load()
