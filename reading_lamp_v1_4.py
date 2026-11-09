# Release: v1.4
# 3구역 독립 제어: 어두울수록 밝아지는 흰색 독서등
from machine import ADC, Pin
from time import sleep
import neopixel

sensors = [ADC(26), ADC(27), ADC(28)]
NUM_LEDS = 10
led = neopixel.NeoPixel(Pin(18), NUM_LEDS)
ZONES = [(0, 3), (3, 6), (6, 10)]

TARGET = 25000
HYSTERESIS = 1000
# 센서값이 이 값 이하이면 최대 밝기 (환경에 맞게 조절)
DARK_VALUE = 5000
MAX_BRIGHTNESS = 15  # 퍼센트, 기존 최대 밝기 유지
MIN_BRIGHTNESS = 1
FADE_STEP = 0.15
INTERVAL = 0.05
FILTER_ALPHA = 0.2  # 작을수록 센서 변화에 천천히 반응


def update_target(value, is_on):
    # 켜짐/꺼짐 경계를 다르게 두어 기준 근처에서 반복 점멸 방지
    if value < TARGET - HYSTERESIS:
        is_on = True
    elif value > TARGET + HYSTERESIS:
        is_on = False

    if not is_on:
        return 0.0, is_on

    # 센서값이 낮을수록 더 밝게: DARK_VALUE 이하에서 최대 밝기
    bright_value = TARGET + HYSTERESIS
    ratio = (bright_value - value) / (bright_value - DARK_VALUE)
    ratio = max(0.0, min(1.0, ratio))
    level = MIN_BRIGHTNESS + ratio * (MAX_BRIGHTNESS - MIN_BRIGHTNESS)
    return level, is_on


def fade(current, target):
    if current < target:
        return min(target, current + FADE_STEP)
    if current > target:
        return max(target, current - FADE_STEP)
    return current


def set_white(start, end, level):
    level = max(0, min(MAX_BRIGHTNESS, level))
    value = int(level * 255 / 100)
    for i in range(start, end):
        led[i] = (value, value, value)


brightness = [0.0, 0.0, 0.0]
is_on = [False, False, False]
filtered = [float(sensor.read_u16()) for sensor in sensors]
print_count = 0

print("자동 독서등 v1.4 시작")
try:
    while True:
        for i in range(3):
            raw = sensors[i].read_u16()
            filtered[i] += FILTER_ALPHA * (raw - filtered[i])
            target, is_on[i] = update_target(filtered[i], is_on[i])
            brightness[i] = fade(brightness[i], target)
            start, end = ZONES[i]
            set_white(start, end, brightness[i])

        led.write()
        print_count += 1
        if print_count >= 10:
            print_count = 0
            print(" | ".join(
                "A{}: {} / 밝기: {:.1f}%".format(
                    i, int(filtered[i]), brightness[i]
                ) for i in range(3)
            ))
        sleep(INTERVAL)

except KeyboardInterrupt:
    print("독서등 종료")
finally:
    for i in range(NUM_LEDS):
        led[i] = (0, 0, 0)
    led.write()
