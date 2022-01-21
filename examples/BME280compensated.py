import time
import weatherhat

print(f"""
BME280Compensated.py - Print compensated readings from the BME280 weather sensor.
Press Ctrl+C to exit!
""")

# We can compensate for the heat of the Pi and other environmental conditions using a simple offset.
# Change this number to adjust temperature compensation!
OFFSET = -7.5

sensor = weatherhat.WeatherHAT()

while True:
    sensor.temperature_offset = OFFSET
    sensor.update(interval=1.0)
    
    print(f"""
Compensated air temperature: {sensor.temperature:0.2f} *C
    Raw temperature          {sensor.device_temperature:0.2f} *C    
    With offset              {OFFSET} *C

Relative humidity:           {sensor.relative_humidity:0.2f} %
    Raw humidity             {sensor.humidity:0.2f} %

Pressure:                    {sensor.pressure:0.2f} hPa
""")

    time.sleep(1.0)