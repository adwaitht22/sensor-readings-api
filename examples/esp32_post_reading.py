"""MicroPython example: send a reading from an ESP32 to the Sensor Readings API.

NOT TESTED ON HARDWARE. This is a starting point written to match the API's
request format. Before relying on it, run it on your own ESP32, fix anything
that differs on your board, and replace the read_temperature() stub with your
real sensor code.

Setup: copy to the board as main.py, edit the three constants below, and make
sure the API is reachable from the board's network (use the computer's LAN IP,
not localhost).
"""

import time

import network
import urequests

WIFI_SSID = "your-wifi-name"
WIFI_PASSWORD = "your-wifi-password"
API_URL = "http://192.168.1.50:8000/readings"  # your computer's LAN IP
DEVICE_ID = "esp32-01"


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        while not wlan.isconnected():
            time.sleep(0.5)
    return wlan


def read_temperature():
    """Replace with your real sensor code (e.g. a DS18B20 or DHT22)."""
    return 24.5


def send_reading(value):
    payload = {
        "device_id": DEVICE_ID,
        "sensor": "temperature",
        "value": value,
        "unit": "C",
    }
    response = urequests.post(API_URL, json=payload)
    print("status:", response.status_code)
    response.close()


connect_wifi()
while True:
    send_reading(read_temperature())
    time.sleep(30)
