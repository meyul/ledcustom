"""Face identity confirmation and delayed absence control; no hardware imports."""
from time import ticks_diff

ABSENCE_MS = 60000
CONFIRM_MS = 1000
MAX_SAMPLE_GAP_MS = 2000


class Presence:
    def __init__(self, now):
        self.awake = True  # Allow reading and face acquisition at boot.
        self.profile_id = 0
        self.last_seen = now
        self.last_sample = now
        self.candidate = None
        self.candidate_since = now

    def update(self, blocks, now):
        gap = ticks_diff(now, self.last_sample)
        self.last_sample = now
        if blocks is None:
            # Faults are NOT successful empty frames; pause the absence clock.
            if self.awake:
                self.last_seen = now
            self.candidate = None
            return
        if gap > MAX_SAMPLE_GAP_MS and self.awake:
            self.last_seen = now
            self.candidate = None
        if not blocks:
            self.candidate = None
            if ticks_diff(now, self.last_seen) >= ABSENCE_MS:
                self.awake = False
                self.profile_id = 0
            return
        was_awake = self.awake
        self.awake = True
        self.last_seen = now
        if not was_awake:
            self.profile_id = 0
        # Retain active user if several people are visible; otherwise largest face.
        matching = [b for b in blocks if b[4] == self.profile_id and b[4] > 0]
        selected = max(matching or blocks, key=lambda b: b[2] * b[3])
        identity = selected[4]
        if identity <= 0:
            # An unknown face still keeps the lamp on. Brief ID loss retains settings.
            self.candidate = None
            return
        if self.candidate != identity:
            self.candidate = identity
            self.candidate_since = now
        elif ticks_diff(now, self.candidate_since) >= CONFIRM_MS:
            self.profile_id = identity
