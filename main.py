
from machine import ADC
from ws2812 import WS2812
from time import sleep

# 조도 센서: A0
light_sensor = ADC(0)

# RGB LED 스틱: D18, LED 10개
led = WS2812(18, 10)

# 설정
TARGET = 25000
MAX_BRIGHTNESS = 100
MIN_BRIGHTNESS = 0

brightness = 0

def set_white(level):
    # level: 0~100
    value = int(level * 255 / 100)
    led.pixels_fill((value, value, value))
    led.pixels_show()

print("자동 독서등 시작!")

try:
    while True:
        light_value = light_sensor.read_u16()

        # 센서값을 확인하면서 기준값에 따라 LED 조절
        if light_value < TARGET:
            brightness = min(MAX_BRIGHTNESS, brightness + 5)
        else:
            brightness = max(MIN_BRIGHTNESS, brightness - 5)

        set_white(brightness)

        print(
            "조도 센서:", light_value,
            "| LED 밝기:", brightness, "%"
        )

        sleep(0.2)

except KeyboardInterrupt:
    set_white(0)
    print("독서등 종료")
