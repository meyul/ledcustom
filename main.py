
from machine import ADC, Pin, PWM
from time import sleep

# =====================================
# Grove Shield for Raspberry Pi Pico
# 독립 제어 독서등: 센서 3개 + LED 3개
# =====================================

# 조도 센서 입력
sensor_left = ADC(26)     # A0
sensor_center = ADC(27)   # A1
sensor_right = ADC(28)    # A2

sensors = [
    sensor_left,
    sensor_center,
    sensor_right
]

# LED PWM 출력 핀
# 실제 보드의 포트 매핑과 PWM 지원을 확인할 것!
led_left = PWM(Pin(16))
led_center = PWM(Pin(18))
led_right = PWM(Pin(20))

leds = [led_left, led_center, led_right]

for led in leds:
    led.freq(1000)
    led.duty_u16(0)

# =====================================
# 설정값
# =====================================

# 센서 ADC값 기준. 실제 측정 후 조정해야 함.
TARGET = 30000

# LED 밝기 조절 폭
MIN_BRIGHTNESS = 0
MAX_BRIGHTNESS = 50000

# 한 번에 밝기를 얼마나 변경할지 결정
STEP = 2500

# 센서값이 밝을수록 커지는 센서라는 가정
BRIGHTER_VALUE_IS_HIGHER = True

# =====================================
# 센서 읽기
# =====================================

def read_sensors():
    return [sensor.read_u16() for sensor in sensors]


# =====================================
# LED 밝기 제어
# =====================================

def adjust_led(value, current_brightness):
    if BRIGHTER_VALUE_IS_HIGHER:
        is_dark = value < TARGET
    else:
        is_dark = value > TARGET

    if is_dark:
        current_brightness += STEP
    else:
        current_brightness -= STEP

    current_brightness = max(
        MIN_BRIGHTNESS,
        min(MAX_BRIGHTNESS, current_brightness)
    )

    return current_brightness


# =====================================
# 메인 프로그램
# =====================================

brightness = [0, 0, 0]
names = ["왼쪽", "가운데", "오른쪽"]

print("자동 독서등 시작!")
print("Ctrl+C를 누르면 종료됩니다.")

try:
    while True:
        values = read_sensors()

        for i in range(3):
            brightness[i] = adjust_led(
                values[i],
                brightness[i]
            )

            leds[i].duty_u16(brightness[i])

        print(
            "센서:", values,
            "| LED 밝기:", brightness
        )

        sleep(0.2)

except KeyboardInterrupt:
    print("독서등 종료")

finally:
    for led in leds:
        led.duty_u16(0)
        led.deinit()
