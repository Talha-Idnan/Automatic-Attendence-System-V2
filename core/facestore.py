"""Enrolled people: name -> array of 512-number face fingerprints (embeddings)."""
import os
import pickle

import numpy as np

from core.config import FACES_FILE


def pretty(name):
    """Display name: 'talha' -> 'Talha' (names that already have capitals are kept)."""
    name = str(name)
    return name.title() if name == name.lower() else name


def centroid(emb):
    c = emb.mean(axis=0)
    return c / np.linalg.norm(c)


class FaceStore:
    def __init__(self, path=FACES_FILE):
        self.path = path
        self.people = {}
        self.load()

    # ---- persistence
    def load(self):
        self.people = {}
        if os.path.exists(self.path):
            with open(self.path, "rb") as f:
                self.people = pickle.load(f).get("people", {})

    def save(self):
        with open(self.path, "wb") as f:
            pickle.dump({"people": self.people}, f)

    # ---- people
    def names(self):
        return sorted(self.people, key=str.lower)

    def resolve(self, name):
        """Existing key for this name (case-insensitive) or the name itself."""
        return next((k for k in self.people if k.lower() == name.lower()), name)

    def add(self, name, samples):
        key = self.resolve(name.strip())
        samples = np.asarray(samples, dtype=np.float32)
        if key in self.people:
            self.people[key] = np.concatenate([self.people[key], samples])
        else:
            self.people[key] = samples
        return key, len(self.people[key])

    def delete(self, name):
        self.people.pop(name, None)

    # ---- analysis
    def similar_to(self, samples, exclude=None, min_sim=0.7):
        c = centroid(np.asarray(samples, dtype=np.float32))
        out = [(k, float(c @ centroid(v))) for k, v in self.people.items() if k != exclude]
        return sorted([x for x in out if x[1] >= min_sim], key=lambda x: -x[1])

    def consistency(self):
        out = {}
        for n, E in self.people.items():
            sims = E @ centroid(E)
            out[n] = dict(n=len(E), avg=float(sims.mean()), min=float(sims.min()))
        return out

    def similarity_matrix(self):
        names = self.names()
        if not names:
            return names, np.zeros((0, 0))
        C = np.stack([centroid(self.people[n]) for n in names])
        return names, C @ C.T

    def clean(self):
        """Drops samples that don't fit their own person. Returns {name: (before, after)}."""
        before = {n: len(E) for n, E in self.people.items()}
        for _ in range(2):
            cents = {n: centroid(E) for n, E in self.people.items()}
            for n, E in self.people.items():
                own = E @ cents[n]
                keep = own >= 0.6
                for m, c in cents.items():
                    if m != n:
                        keep &= own > (E @ c + 0.05)
                if keep.sum() >= 10:                   # never wipe a person out
                    self.people[n] = E[keep]
        return {n: (before[n], len(E)) for n, E in self.people.items()}
