import network
import urequests
import dht
from machine import Pin
from time import sleep

# =========================
# WIFI
# =========================
SSID = "WIFI"
PASSWORD = ""

wifi = network.WLAN(network.STA_IF)
wifi.active(True)

wifi_led = Pin(2, Pin.OUT)
relay = Pin(5, Pin.OUT)
buzzer = Pin(19, Pin.OUT)

dht_sensor = dht.DHT11(Pin(4))

GET_SERVER = "http://YOUR-IP:PORT/esp32"
POST_SERVER = "http://YOUR-IP:PORT/update"

relay_status = 0


# =========================
# BUZZER
# =========================
def beep():
    for i in range(2):
        buzzer.value(1)
        sleep(0.1)
        buzzer.value(0)
        sleep(0.1)


# =========================
# WIFI CONNECT
# =========================
def wifi_connect():
    if not wifi.isconnected():
        wifi_led.value(0)
        wifi.connect(SSID, PASSWORD)

        t = 0
        while not wifi.isconnected():
            sleep(1)
            t += 1
            if t > 15:
                return False

    wifi_led.value(1)
    return True


# =========================
# SENSOR
# =========================
def read_sensor():
    try:
        dht_sensor.measure()
        t = dht_sensor.temperature()
        h = dht_sensor.humidity()

        if t < 0 or t > 80:
            return None, None

        if h < 0 or h > 100:
            return None, None

        return t, h

    except:
        return None, None


wifi_connect()

# =========================
# LOOP
# =========================
while True:

    try:
        wifi_connect()

        suhu, hum = None, None

        for i in range(3):
            suhu, hum = read_sensor()
            if suhu is not None:
                break
            sleep(1)

        if suhu is None:

            relay.value(0)
            relay_status = 0

            urequests.post(POST_SERVER, json={
                "temperature": -1,
                "humidity": -1,
                "relay": 0,
                "sensor_status": "ERROR"
            }).close()

            sleep(5)
            continue

        # =========================
        # GET CONFIG SERVER
        # =========================
        try:
            res = urequests.get(GET_SERVER)
            cfg = res.json()
            res.close()

            mode = cfg.get("mode", "AUTO")
            low = float(cfg.get("low_temp", 30))
            high = float(cfg.get("high_temp", 32))
            manual = cfg.get("relay", 0)

            if mode == "AUTO":

                if suhu >= high:
                    relay.value(0)
                    relay_status = 0

                elif suhu <= low:
                    relay.value(1)
                    relay_status = 1

            else:

                relay.value(manual)
                relay_status = manual

        except Exception as e:
            print("CFG ERROR:", e)

        # =========================
        # SEND DATA
        # =========================
        try:
            urequests.post(POST_SERVER, json={
                "temperature": suhu,
                "humidity": hum,
                "relay": relay_status,
                "sensor_status": "OK"
            }).close()

            beep()

        except:
            pass

    except Exception as e:
        print("MAIN ERROR:", e)

    sleep(2)