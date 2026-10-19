
from machine import ADC, Pin
from time import sleep_us, sleep

# 조도 센서: A0 (GP26)
sensor = ADC(26)

# Grove RGB LED Stick: D18 (GP18)
data = Pin(18, Pin.OUT)

NUM_LEDS = 10
TARGET = 25000
MAX_BRIGHTNESS = 15
brightness = 0

def set_white(level):
    value = int(level*255/100)
    show((value, value, value))

# WS2813/WS2812 계열에 데이터를 보내는 함수
# MicroPython RP2의 타이밍에 의존하므로,
# 실제 하드웨어에서 테스트가 필요함.
import rp2

@rp2.asm_pio(
    sideset_init=rp2.PIO.OUT_LOW,
    out_shiftdir=rp2.PIO.SHIFT_LEFT,
    autopull=True,
    pull_thresh=24
)
def ws281x():
    T1 = 2
    T2 = 5
    T3 = 3

    label("bitloop")
    out(x, 1).side(0)[T3 - 1]
    jmp(not_x, "do_zero").side(1)[T1 - 1]
    jmp("bitloop").side(1)[T2 - 1]
    label("do_zero")
    nop().side(0)[T2 - 1]

sm = rp2.StateMachine(
    0, ws281x, freq=8000000, sideset_base=data
)
sm.active(1)

def show(color):
    # 각 픽셀에 24비트 GRB 데이터 전송
    grb = ((color[1] & 255) << 16) | \
          ((color[0] & 255) << 8) | \
          (color[2] & 255)

    for _ in range(NUM_LEDS):
        sm.put(grb, 24)

    sleep_us(80)

def set_white(level):
    value = int(level * 255 / 100)
    show((value, value, value))

print("자동 독서등 시작")

try:
    while True:
        value = sensor.read_u16()

        # 어두울수록 LED 밝기를 높임
        if value < TARGET:
            brightness = min(MAX_BRIGHTNESS, brightness + 1)
        else:
            brightness = max(0, brightness - 1)

        set_white(brightness)

        print("센서:", value, "| LED 밝기:", brightness, "%")
        sleep(0.2)

except KeyboardInterrupt:
    set_white(0)
    sm.active(0)
    print("종료")
