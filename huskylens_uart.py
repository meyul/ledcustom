"""Original HUSKYLENS UART protocol (not HUSKYLENS 2). MicroPython."""
from time import ticks_ms, ticks_diff, sleep


def frame(command, data=b''):
    packet = bytearray(b'\x55\xaa\x11')
    packet.extend((len(data), command))
    packet.extend(data)
    packet.append(sum(packet) & 255)
    return packet


class HuskyLens:
    def __init__(self, uart):
        self.uart = uart
        self.buffer = bytearray()
        self.pending = False
        self.expected = None
        self.blocks = []
        self.started = ticks_ms()
        self.last_request = ticks_ms()
        self.online = False
        self.configured = False
        self.phase = 0x2c
        self.request_kind = 0x21

    def packets(self):
        if self.uart.any():
            self.buffer.extend(self.uart.read() or b'')
        result = []
        while len(self.buffer) >= 6:
            if self.buffer[:3] != b'\x55\xaa\x11':
                del self.buffer[0]
                continue
            size = self.buffer[3] + 6
            if size > 64:  # Only short replies used by this driver
                del self.buffer[0]
                continue
            if len(self.buffer) < size:
                break
            packet = self.buffer[:size]
            if (sum(packet[:-1]) & 255) != packet[-1]:
                del self.buffer[0]
                continue
            del self.buffer[:size]
            result.append((packet[4], packet[5:-1]))
        return result

    def command(self, command, data=b''):
        self.uart.read()
        self.buffer = bytearray()
        self.uart.write(frame(command, data))
        start = ticks_ms()
        while ticks_diff(ticks_ms(), start) < 1500:
            for code, payload in self.packets():
                if code == 0x2e:
                    return True
            sleep(0.01)
        return False

    def begin(self):
        # Call once at startup. Runtime polling is nonblocking.
        self.configured = self.command(0x2c) and self.command(0x2d, b'\x00\x00')
        return self.configured

    def poll(self, now):
        """Return (complete_sample, blocks). None means communication failure.

        block = (x, y, width, height, face_id). [] is a valid empty frame.
        """
        for code, data in self.packets():
            if not self.pending:
                continue
            if self.request_kind != 0x21:
                if code == 0x2e:
                    self.pending = False
                    if self.request_kind == 0x2c:
                        self.phase = 0x2d
                    else:
                        self.configured = True
                        self.phase = 0x2c
                continue
            if code == 0x29 and len(data) == 10 and self.expected is None:
                self.expected = data[0] | (data[1] << 8)
                if self.expected > 32:
                    self.pending = False
                    self.online = False
                    return True, None
                self.blocks = []
            elif code == 0x2a and len(data) == 10 and self.expected is not None:
                self.blocks.append(tuple(data[i] | (data[i + 1] << 8)
                                         for i in range(0, 10, 2)))
            if self.expected is not None and len(self.blocks) == self.expected:
                self.pending = False
                self.online = True
                return True, self.blocks
        if self.pending and ticks_diff(now, self.started) >= 1000:
            self.pending = False
            self.online = False
            self.configured = False
            self.phase = 0x2c
            return True, None
        if not self.pending and ticks_diff(now, self.last_request) >= 300:
            # Discard late/incomplete data before a fresh transaction.
            self.uart.read()
            self.buffer = bytearray()
            self.expected = None
            self.blocks = []
            try:
                self.request_kind = 0x21 if self.configured else self.phase
                payload = b'\x00\x00' if self.request_kind == 0x2d else b''
                self.uart.write(frame(self.request_kind, payload))
            except OSError:
                self.last_request = now
                self.online = False
                return True, None
            self.started = now
            self.last_request = now
            self.pending = True
        return False, None
