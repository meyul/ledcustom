# v1.6 / Raspberry Pi Pico / MicroPython / original HUSKYLENS
# Keep reading_lamp_v1_5.py beside this file: it provides sensor calibration/control.
from machine import UART, Pin
from time import ticks_ms, ticks_diff, sleep
import ujson as json
import reading_lamp_v1_5 as lamp
from huskylens_uart import HuskyLens
from lamp_presence import Presence

PROFILE_FILE = 'lamp_profiles.json'


def load_profiles():
    with open(PROFILE_FILE) as file:
        profiles = json.load(file)
    if '0' not in profiles:
        raise ValueError('lamp_profiles.json needs default profile 0')
    for key in profiles:
        profile = profiles[key]
        targets = profile['targets']
        cap = profile['max_brightness']
        if (len(targets) != 3 or not all(0 < t <= 65535 for t in targets)
                or not 0 < cap <= lamp.MAX_BRIGHTNESS):
            raise ValueError('Invalid profile: ' + key)
    return profiles


def main():
    lamp.show([0, 0, 0])
    profiles = load_profiles()
    data = lamp.load_calibration()
    scales, responses = data['scales'], data['responses']
    gains = []
    for zone in range(3):
        sensitivity = sum(max(0, responses[source][zone]) for source in range(3))
        gains.append(lamp.clamp(0.12 * lamp.MAX_BRIGHTNESS / max(1000, sensitivity),
                                0.000005, 0.00008))
        if responses[zone][zone] < 300:
            print('A{}: 담당 LED 빛이 센서에 닿는지 확인하세요.'.format(zone))
    uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1), timeout=0, rxbuf=512)
    camera = HuskyLens(uart)
    if not camera.begin():
        print('카메라 연결 실패: 기본 자동 조명 유지. UART/얼굴 인식 모드를 확인하세요.')
    now = ticks_ms()
    presence = Presence(now)
    readings = [lamp.StableReading(lamp.sensors[i].read_u16() * scales[i], now)
                for i in range(3)]
    outputs = [0.0, 0.0, 0.0]
    brightness = [0.0, 0.0, 0.0]
    last_control = last_print = now
    print('독서등 v1.6 시작 / 얼굴 미감지 60초 후 소등')
    while True:
        now = ticks_ms()
        try:
            fresh, blocks = camera.poll(now)
        except OSError:
            camera.pending = False
            camera.online = False
            fresh, blocks = True, None
        if fresh:
            presence.update(blocks, now)
        profile = profiles.get(str(presence.profile_id), profiles['0'])
        targets = profile['targets']
        cap = profile['max_brightness']
        for i in range(3):
            readings[i].update(lamp.sensors[i].read_u16() * scales[i], now)
        if ticks_diff(now, last_control) >= lamp.CONTROL_MS:
            last_control = now
            for i in range(3):
                if presence.awake:
                    outputs[i] = min(cap, lamp.next_output(
                        min(outputs[i], cap), readings[i].accepted,
                        targets[i], gains[i], readings[i].ready))
                else:
                    outputs[i] = 0.0
        for i in range(3):
            brightness[i] = lamp.fade(brightness[i], outputs[i])
        lamp.show(brightness)
        if ticks_diff(now, last_print) >= 1000:
            last_print = now
            state = '자동 조절' if presence.awake else '자리 비움: 소등'
            if not camera.online:
                state += ' / 카메라 통신 확인 필요'
            print('ID:{} / {} / {} / 출력: {}'.format(
                presence.profile_id, profile['name'], state,
                [round(v, 1) for v in brightness]))
        sleep(lamp.INTERVAL)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('독서등 종료')
    finally:
        lamp.show([0, 0, 0])
