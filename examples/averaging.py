import time

import weatherhat
from weatherhat import history

sensor = weatherhat.WeatherHAT()

temperature = history.History()

pressure = history.History()

humidity = history.History()
relative_humidity = history.History()
dewpoint = history.History()

lux = history.History()

wind_speed = history.WindSpeedHistory()
wind_direction = history.WindDirectionHistory()

rain_mm_total = history.History()
rain_mm_sec = history.History()


while True:
    sensor.update(interval=5.0)

    # Append values to the histories
    temperature.append(sensor.temperature)
    pressure.append(sensor.pressure)
    humidity.append(sensor.humidity)
    relative_humidity.append(sensor.relative_humidity)
    dewpoint.append(sensor.dewpoint)
    lux.append(sensor.lux)
    wind_speed.append(sensor.wind_speed)
    wind_direction.append(sensor.wind_direction)
    rain_mm_total.append(sensor.rain_mm_total)
    rain_mm_sec.append(sensor.rain_mm_sec)

    wind_direction_cardinal = wind_direction.average_compass(60)

    print(f"""
System temp: Now: {sensor.device_temperature:0.2f} ℃
Temperature: Avg: {temperature.average()} ℃ - Now: {sensor.temperature:0.2f} ℃

Humidity:    Avg: {humidity.average():0.2f} % - Now: {sensor.humidity:0.2f} %
Dew point:   Avg: {dewpoint.average():0.2f} ℃ - Now: {sensor.dewpoint:0.2f} ℃

Light:       Avg: {lux.average():0.2f} Lux - Now: {sensor.lux:0.2f} Lux

Pressure:    Avg: {pressure.average():0.2f} hPa - Now: {sensor.pressure:0.2f} hPa

Wind (avg):  Avg: {wind_speed.average():0.2f} mph - Now: {sensor.wind_speed:0.2f} mph

Rain:        Avg: {rain_mm_sec.average():0.2f} mm/sec - Now: {sensor.rain_mm_sec:0.2f} mm/sec

Wind (avg):  Avg: Now: {wind_direction.average(60):0.2f} degrees ({wind_direction_cardinal})

""")

    time.sleep(5.0)
