# Release: v1.3
# 3구역 독립 제어 자동 흰색 독서등
# 부드러운 밝기 변화 + 임계값 흔들림 방지

from machine import ADC, Pin
from time import sleep
import neopixel

# 조도 센서 3개
sensor1 = ADC(26)  # A0
sensor2 = ADC(27)  # A1
sensor3 = ADC(28)  # A2

# RGB LED Stick
NUM_LEDS = 10
led = neopixel.NeoPixel(Pin(18), NUM_LEDS)

# 설정값
TARGET = 25000
HYSTERESIS = 1000

MAX_BRIGHTNESS = 15

# 밝기 변화 속도
FADE_STEP = 0.15
INTERVAL = 0.05

# 현재 밝기
brightness1 = 0.0
brightness2 = 0.0
brightness3 = 0.0

# 목표 밝기
target1 = 0
target2 = 0
target3 = 0


def update_target(value, target_level):
    # 어두우면 최대 밝기를 목표로 설정
    if value < TARGET - HYSTERESIS:
        target_level = MAX_BRIGHTNESS

    # 밝으면 LED를 끄는 것을 목표로 설정
    elif value > TARGET + HYSTERESIS:
        target_level = 0

    # 기준값 주변에서는 기존 목표 유지
    return target_level


def fade(current, target):
    # 목표 밝기에 천천히 접근
    if current < target:
        current = min(
            target,
            current + FADE_STEP
        )

    elif current > target:
        current = max(
            target,
            current - FADE_STEP
        )

    return current


def set_white(start, end, level):
    # 밝기 범위 제한
    level = max(0, min(MAX_BRIGHTNESS, level))

    # RGB 흰색 밝기 계산
    value = int(level * 255 / 100)

    # 지정된 LED 구역만 설정
    for i in range(start, end):
        led[i] = (value, value, value)


print("자동 독서등 v1.3 시작")

try:
    while True:

        # 센서별 측정값
        value1 = sensor1.read_u16()
        value2 = sensor2.read_u16()
        value3 = sensor3.read_u16()

        # 센서별 목표 밝기 결정
        target1 = update_target(value1, target1)
        target2 = update_target(value2, target2)
        target3 = update_target(value3, target3)

        # 센서별 밝기를 부드럽게 변경
        brightness1 = fade(brightness1, target1)
        brightness2 = fade(brightness2, target2)
        brightness3 = fade(brightness3, target3)

        # LED 구역별 출력
        set_white(0, 3, brightness1)
        set_white(3, 6, brightness2)
        set_white(6, 10, brightness3)

        # LED 업데이트
        led.write()

        # 현재 상태 출력
        print(
            "A0:", value1,
            "| 밝기:", round(brightness1, 2),
            "|| A1:", value2,
            "| 밝기:", round(brightness2, 2),
            "|| A2:", value3,
            "| 밝기:", round(brightness3, 2)
        )

        sleep(INTERVAL)

except KeyboardInterrupt:

    # 종료 시 LED 끄기
    for i in range(NUM_LEDS):
        led[i] = (0, 0, 0)

    led.write()

    print("독서등 종료")
