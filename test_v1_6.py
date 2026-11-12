"""Host simulations only; run: python -m unittest discover -s tests -v"""
import time
import unittest
from unittest.mock import patch

# MicroPython tick API shim for host simulation.
time.ticks_ms = lambda: 0
time.ticks_diff = lambda a, b: ((a - b + (1 << 29)) % (1 << 30)) - (1 << 29)
from lamp_presence import Presence
from huskylens_uart import HuskyLens, frame

FACE1 = (160, 100, 60, 80, 1)
FACE2 = (160, 100, 70, 90, 2)
UNKNOWN = (160, 100, 60, 80, 0)


class FakeUART:
    def __init__(self):
        self.incoming = bytearray()
        self.sent = []
    def any(self):
        return len(self.incoming)
    def read(self):
        data = bytes(self.incoming)
        self.incoming.clear()
        return data
    def write(self, data):
        self.sent.append(bytes(data))


def words(values):
    return b''.join(int(v).to_bytes(2, 'little') for v in values)


class PresenceTests(unittest.TestCase):
    def test_absence_then_unknown_wakes(self):
        p = Presence(0)
        for now in range(1000, 60000, 1000):
            p.update([], now)
            self.assertTrue(p.awake)
        p.update([], 60000)
        self.assertFalse(p.awake)
        p.update([UNKNOWN], 61000)
        self.assertTrue(p.awake)
        self.assertEqual(p.profile_id, 0)

    def test_identity_confirmation_and_interruption(self):
        p = Presence(0)
        p.update([FACE1], 0)
        p.update([FACE1], 600)
        self.assertEqual(p.profile_id, 0)
        p.update([FACE1], 1200)
        self.assertEqual(p.profile_id, 1)
        p.update([FACE2], 1500)
        p.update([], 1800)
        p.update([FACE2], 2100)
        self.assertEqual(p.profile_id, 1)
        p.update([FACE2], 3200)
        self.assertEqual(p.profile_id, 2)

    def test_unknown_and_multiple_faces(self):
        p = Presence(0)
        p.update([FACE1], 0)
        p.update([FACE1], 1000)
        for now in range(2000, 70000, 1000):
            p.update([UNKNOWN], now)
        self.assertTrue(p.awake)
        self.assertEqual(p.profile_id, 1)
        p.update([FACE1, FACE2], 71000)
        p.update([FACE1, FACE2], 72000)
        self.assertEqual(p.profile_id, 1)

    def test_faults_do_not_count_as_absence(self):
        p = Presence(0)
        for now in range(1000, 90000, 1000):
            p.update(None, now)
        self.assertTrue(p.awake)
        p.update([], 90000)
        self.assertTrue(p.awake)
        # Wraparound behaves like MicroPython ticks.
        p = Presence((1 << 30) - 1000)
        p.update([FACE1], 100)
        self.assertTrue(p.awake)


class ProtocolTests(unittest.TestCase):
    def driver(self):
        u = FakeUART()
        d = HuskyLens(u)
        d.configured = True
        return u, d

    def test_fragmented_frames_and_unknown(self):
        u, d = self.driver()
        self.assertEqual(d.poll(300), (False, None))
        packet = frame(0x29, words([1, 1, 5, 0, 0]))
        u.incoming.extend(packet[:7])
        self.assertEqual(d.poll(350), (False, None))
        u.incoming.extend(packet[7:] + frame(0x2a, words(UNKNOWN)))
        self.assertEqual(d.poll(400), (True, [UNKNOWN]))

    def test_empty_distinct_from_timeout(self):
        u, d = self.driver()
        d.poll(300)
        u.incoming.extend(frame(0x29, words([0, 2, 0, 0, 0])))
        self.assertEqual(d.poll(400), (True, []))
        d.poll(600)
        self.assertEqual(d.poll(1600), (True, None))
        self.assertFalse(d.configured)

    def test_corrupt_frame_and_partial_transaction_timeout(self):
        u, d = self.driver()
        d.poll(300)
        broken = frame(0x29, words([0, 0, 0, 0, 0]))
        broken[-1] ^= 1
        u.incoming.extend(b'noise' + broken)
        self.assertEqual(d.poll(500), (False, None))
        u.incoming.extend(frame(0x29, words([2, 2, 0, 0, 0])) + frame(0x2a, words(FACE1)))
        self.assertEqual(d.poll(700), (False, None))
        self.assertEqual(d.poll(1300), (True, None))

    def test_nonblocking_reconnect_sets_face_algorithm(self):
        u = FakeUART()
        d = HuskyLens(u)
        d.poll(300)
        self.assertEqual(u.sent[-1], frame(0x2c))
        u.incoming.extend(frame(0x2e))
        d.poll(400)
        d.poll(600)
        self.assertEqual(u.sent[-1], frame(0x2d, b'\x00\x00'))
        u.incoming.extend(frame(0x2e))
        d.poll(700)
        self.assertTrue(d.configured)
        d.poll(900)
        self.assertEqual(u.sent[-1], frame(0x21))


if __name__ == '__main__':
    unittest.main()
