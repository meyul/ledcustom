# Release: v1.5 / MicroPython, Raspberry Pi Pico
# A0: GP26, A1: GP27, A2: GP28 / LED Stick DIN: GP18
# 센서를 각 구역의 책 읽는 면에 두세요. LED만 직접 바라보게 두지 마세요.
# 첫 실행은 Thonny에서: 안내에 따라 두 번 Enter를 누르면 보정값이 저장됩니다.
# 재보정: 아래 RECALIBRATE를 True로 바꾸고 실행 후 다시 False로 돌리세요.
from machine import ADC, Pin
from time import sleep, ticks_ms, ticks_diff
import neopixel
import ujson as json

NUM_LEDS = 10
ZONES = [(0, 3), (3, 6), (6, 10)]
MAX_BRIGHTNESS = 15.0  # 기존과 동일한 최대 출력(%)
TARGETS = [25000.0, 25000.0, 25000.0]  # lux가 아닌 보정된 ADC 목표값
DEADBAND = 1000.0
SHADOW_HOLD_MS = 800  # 이 시간보다 짧은 큰 변화는 제어에 반영하지 않음
STABLE_TOLERANCE = 1500.0
SENSOR_ALPHA = 0.25
FADE_STEP = 0.15
INTERVAL = 0.05
CONTROL_MS = 100
MAX_CONTROL_STEP = 0.08  # 제어 주기마다 목표 출력 변화 한도(%)
CAL_FILE = "reading_lamp_calibration.json"
RECALIBRATE = False

sensors = [ADC(26), ADC(27), ADC(28)]
led = neopixel.NeoPixel(Pin(18), NUM_LEDS)


def clamp(value, low, high):
    return max(low, min(high, value))


def show(levels):
    for zone in range(3):
        value = int(clamp(levels[zone], 0, MAX_BRIGHTNESS) * 255 / 100)
        start, end = ZONES[zone]
        for pixel in range(start, end):
            led[pixel] = (value, value, value)
    led.write()


def measure(samples=30):
    totals = [0.0, 0.0, 0.0]
    for _ in range(samples):
        for i in range(3):
            totals[i] += sensors[i].read_u16()
        sleep(0.02)
    return [value / samples for value in totals]


def calibrate():
    show([0, 0, 0])
    print("\n[1/2] 세 센서를 나란히 놓아 같은 빛을 받게 하세요.")
    print("손 그림자를 피하고, 완전히 어둡거나 센서값이 포화된 곳은 피하세요.")
    input("준비되면 이 입력창에서 Enter: ")
    base = measure(60)
    if min(base) < 2000 or max(base) > 62000:
        raise ValueError("보정하기에 너무 어둡거나 밝습니다. 조명을 바꿔 재실행하세요.")
    reference = sum(base) / 3
    scales = [reference / value for value in base]
    if min(scales) < 0.25 or max(scales) > 4:
        raise ValueError("센서 차이가 너무 큽니다. 연결과 같은 조명 여부를 확인하세요.")

    print("[2/2] 센서를 각 구역의 책 읽는 면에 다시 배치하세요.")
    print("센서가 책에 닿는 주변광과 독서등 빛을 함께 받게 하세요.")
    print("Enter 후 약 10초 동안 센서, 독서등, 주변 조명을 움직이지 마세요.")
    input("준비되면 Enter: ")
    responses = []
    for zone in range(3):
        show([0, 0, 0])
        sleep(0.4)
        before = measure()
        levels = [0, 0, 0]
        levels[zone] = MAX_BRIGHTNESS
        show(levels)
        sleep(0.6)
        on = measure()
        show([0, 0, 0])
        sleep(0.4)
        after = measure()
        # 행: 센서, 열: 켠 LED 구역. 주변 조명 변동은 전후 평균으로 완화.
        responses.append([
            (on[i] - (before[i] + after[i]) / 2) * scales[i]
            for i in range(3)
        ])
    data = {"version": 1, "scales": scales, "responses": responses}
    # 임시 파일을 다 쓴 후 교체하여 쓰기 중단 위험을 줄임.
    import os
    with open(CAL_FILE + ".tmp", "w") as file:
        json.dump(data, file)
    os.rename(CAL_FILE + ".tmp", CAL_FILE)
    print("보정값 저장 완료. 다음 실행부터 자동으로 사용합니다.")
    return data


def load_calibration():
    if not RECALIBRATE:
        try:
            with open(CAL_FILE) as file:
                data = json.load(file)
            scales = data["scales"]
            responses = data["responses"]
            if (data["version"] == 1 and len(scales) == 3
                    and all(0.25 <= value <= 4 for value in scales)
                    and len(responses) == 3
                    and all(len(row) == 3 for row in responses)
                    and all(-262140 <= v <= 262140 for row in responses for v in row)):
                return data
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return calibrate()


class StableReading:
    """측정값이 충분히 오래 유지될 때만 제어용 값으로 채택."""
    def __init__(self, value, now):
        self.filtered = value
        self.accepted = value
        self.candidate = value
        self.since = now
        # 시작 직후에도 안정화 시간을 확보
        self.ready = False

    def update(self, value, now):
        self.filtered += SENSOR_ALPHA * (value - self.filtered)
        # 급변을 감지한 순간부터 출력 조절을 잠시 보류
        if abs(value - self.candidate) > STABLE_TOLERANCE:
            self.candidate = value
            self.since = now
            self.ready = False
        if ticks_diff(now, self.since) >= SHADOW_HOLD_MS:
            self.accepted = self.filtered
            self.ready = True
        return self.accepted


def next_output(current, measured, target, gain, ready):
    if not ready:
        return current
    error = target - measured
    if abs(error) <= DEADBAND:
        return current
    # 목표와 차이가 줄면 조절량도 줄임
    effective_error = error - DEADBAND if error > 0 else error + DEADBAND
    change = clamp(effective_error * gain, -MAX_CONTROL_STEP, MAX_CONTROL_STEP)
    # 목표 출력도 범위 안에 두어 최대/최소 출력에서 오차가 누적되지 않게 함
    return clamp(current + change, 0.0, MAX_BRIGHTNESS)


def fade(current, target):
    if current < target:
        return min(target, current + FADE_STEP)
    return max(target, current - FADE_STEP)


def main():
    show([0, 0, 0])
    data = load_calibration()
    scales = data["scales"]
    responses = data["responses"]
    gains = []
    for zone in range(3):
        # 인접 구역 LED의 영향도 고려하여 빛에 민감하면 제어 속도를 낮춤
        sensitivity = sum(max(0, responses[source][zone]) for source in range(3))
        gains.append(clamp(0.12 * MAX_BRIGHTNESS / max(1000, sensitivity),
                           0.000005, 0.00008))
        if responses[zone][zone] < 300:
            print("주의: A{} 센서에 담당 LED 빛이 잘 닿지 않을 수 있습니다. 위치를 확인하세요.".format(zone))

    now = ticks_ms()
    readings = [StableReading(sensors[i].read_u16() * scales[i], now)
                for i in range(3)]
    outputs = [0.0, 0.0, 0.0]
    brightness = [0.0, 0.0, 0.0]
    last_control = now
    last_print = now
    print("자동 독서등 v1.5 시작 / 목표:", TARGETS)
    while True:
        now = ticks_ms()
        for i in range(3):
            readings[i].update(sensors[i].read_u16() * scales[i], now)

        if ticks_diff(now, last_control) >= CONTROL_MS:
            last_control = now
            for i in range(3):
                outputs[i] = next_output(outputs[i], readings[i].accepted,
                                         TARGETS[i], gains[i], readings[i].ready)
        for i in range(3):
            brightness[i] = fade(brightness[i], outputs[i])
        show(brightness)

        if ticks_diff(now, last_print) >= 1000:
            last_print = now
            for i in range(3):
                measured = readings[i].accepted
                if not readings[i].ready:
                    state = "변화 확인 중"
                elif outputs[i] >= MAX_BRIGHTNESS - 0.05 and measured < TARGETS[i] - DEADBAND:
                    state = "최대 출력 / 목표 밝기 부족"
                elif outputs[i] <= 0.05 and measured > TARGETS[i] + DEADBAND:
                    state = "주변이 이미 밝음"
                else:
                    state = "자동 조절"
                print("A{}: {} / 목표: {} / 출력: {:.1f}% / {}".format(
                    i, int(measured), int(TARGETS[i]), brightness[i], state))
        sleep(INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("독서등 종료")
    finally:
        show([0, 0, 0])
