import time

import weatherhat

print(f"""
BME280.py - Print raw readings from the BME280 weather sensor.
Press Ctrl+C to exit!
""")

sensor = weatherhat.WeatherHAT()

while True:
    sensor.update(interval=1.0)

    print(f"""
Device temperature: {sensor.device_temperature:0.2f} *C
Humidity:           {sensor.humidity:0.2f} %
Pressure:           {sensor.pressure:0.2f} hPa
""")

    time.sleep(1.0)
