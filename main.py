from machine import ADC, Pin
from time import sleep

import neopixel

# 조도 센서: A0 (GP26)
sensor = ADC(26)

# Grove RGB LED Stick: D18 (GP18)
led = neopixel.NeoPixel(Pin(18), 10)

# 설정값
NUM_LEDS = 10
TARGET = 25000
MAX_BRIGHTNESS = 15

brightness = 0


def set_white(level):
    # 밝기를 0~15% 범위로 제한
    level = max(0, min(MAX_BRIGHTNESS, level))

    # 밝기를 RGB 값으로 변환
    value = int(level * 255 / 100)

    # 10개 LED 모두 흰색으로 설정
    for i in range(NUM_LEDS):
        led[i] = (value, value, value)

    # LED에 데이터 전송
    led.write()


print("자동 흰색 독서등 시작")

try:
    while True:
        # 조도 센서 값 읽기
        value = sensor.read_u16()

        # 어두우면 밝기 증가
        if value < TARGET:
            brightness = min(
                MAX_BRIGHTNESS,
                brightness + 1
            )

        # 밝으면 밝기 감소
        else:
            brightness = max(
                0,
                brightness - 1
            )

        # 흰색 LED 출력
        set_white(brightness)

        # 현재 상태 출력
        print(
            "센서:", value,
            "| LED 밝기:", brightness, "%"
        )

        sleep(0.2)

except KeyboardInterrupt:
    # 종료할 때 LED 끄기
    set_white(0)

    print("자동 독서등 종료")
