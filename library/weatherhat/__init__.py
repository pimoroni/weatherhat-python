import time
import threading
import math

import RPi.GPIO as GPIO
import ioexpander as io
from bme280 import BME280
from ltr559 import LTR559
from smbus2 import SMBus


__version__ = '0.0.1'


# Anemometer pins
ANI1 = 5       # P0.0
ANI2 = 6       # P0.1

# Wind vane (ADC)
WV = 8         # P0.3 ANI6
WV_RADIUS = 7  # Radius from center to the center of a cup, in CM
WV_CIRCUMFERENCE = WV_RADIUS * 2 * math.pi

# Rain gauge
R2 = 3         # P1.2
R3 = 7         # P1.1
R4 = 2         # P1.0
R5 = 1         # P1.5
RAIN_MM_PER_TICK = 0.2794

wind_degrees_to_cardinal = {
    0: "North",
    45: "North East",
    90: "East",
    135: "South East",
    180: "South",
    225: "South West",
    270: "West",
    315: "North West"
}

wind_direction_to_degrees = {
    0.9: 0,
    2.0: 45,
    3.0: 90,
    2.8: 135,
    2.5: 180,
    1.5: 225,
    0.3: 270,
    0.6: 315
}


class WeatherHAT:
    def __init__(self):
        self._lock = threading.Lock()
        self._i2c_dev = SMBus(1)

        self._bme280 = BME280(i2c_dev=self._i2c_dev)
        self._ltr559 = LTR559(i2c_dev=self._i2c_dev)

        self._ioe = io.IOE(i2c_addr=0x18, interrupt_pin=4)

        # Fudge to enable pull-up on interrupt pin
        self._ioe._gpio.setup(self._ioe._interrupt_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # Input voltage of IO Expander, this is 3.3 on Breakout Garden
        self._ioe.set_adc_vref(3.3)

        # Wind Vane
        self._ioe.set_mode(WV, io.ADC)

        # Anemometer
        self._ioe.set_mode(ANI1, io.OUT)
        self._ioe.output(ANI1, 0)
        self._ioe.set_pin_interrupt(ANI2, True)
        self._ioe.setup_switch_counter(ANI2)

        # Rain Sensor
        self._ioe.set_mode(R2, io.IN_PU)
        self._ioe.set_mode(R3, io.OUT)
        self._ioe.set_mode(R4, io.IN_PU)
        self._ioe.setup_switch_counter(R4)
        self._ioe.set_mode(R5, io.IN_PU)
        self._ioe.output(R3, 0)
        self._ioe.set_pin_interrupt(R4, True)
        self._ioe.on_interrupt(self.handle_ioe_interrupt)
        self._ioe.clear_interrupt()

        self._avg_wind_speed = []
        self._avg_wind_direction = []

        # Data API... kinda
        self.temperature_offset = -7.5
        self.device_temperature = 0
        self.temperature = 0
        self.temperature_history = []

        self.pressure = 0
        self.pressure_history = []

        self.humidity = 0
        self.absolute_humidity = 0
        self.humidity_history = []
        self.dewpoint = 0

        self.lux = 0
        self.lux_history = []

        self.wind_mph = 0
        self.wind_mph_avg = 0
        self.wind_kmph = 0
        self.wind_speed_history = []

        self.wind_degrees = 0
        self.wind_degrees_avg = 0
        self.wind_direction_history = []

        self.rain_mm_sec = 0
        self.rain_mm_total = 0
        self.rain_history = []

        self.reset_counts()

    def reset_counts(self):
        self._lock.acquire(blocking=True)
        self._ioe.clear_switch_counter(ANI2)
        self._ioe.clear_switch_counter(R4)
        self._lock.release()

        self._wind_counts = 0
        self._rain_counts = 0
        self._last_wind_counts = 0
        self._last_rain_counts = 0
        self._t_start = time.time()

    def compensate_humidity(self, humidity, temperature, corrected_temperature):
        """Compensate humidity.

        Convert humidity to relative humidity.

        """
        dewpoint = self.get_dewpoint(humidity, temperature)
        corrected_humidity = 100 - (5 * (corrected_temperature - dewpoint)) - 20
        return min(100, max(0, corrected_humidity))

    def get_dewpoint(self, humidity, temperature):
        """Calculate Dewpoint."""
        return temperature - ((100 - humidity) / 5)

    def hpa_to_inches(self, hpa):
        """Convert hextopascals to inches of mercury."""
        return hpa * 0.02953

    def degrees_to_cardinal(self, degrees):
        value, cardinal = min(wind_degrees_to_cardinal.items(), key=lambda item: abs(item[0] - degrees))
        return cardinal

    def update(self, interval=60.0, history_depth=120, wind_direction_samples=60):
        # Time elapsed since last update
        delta = time.time() - self._t_start

        # Always update TPHL & Wind Direction
        self._lock.acquire(blocking=True)

        # TODO make history depth configurable
        # TODO make update interval for sensors fixed so history always represents a known period

        self.device_temperature = self._bme280.get_temperature()
        self.temperature = self.device_temperature + self.temperature_offset
        self.temperature_history.append(self.temperature)
        self.temperature_history = self.temperature_history[-history_depth:]

        self.pressure = self._bme280.get_pressure()
        self.pressure_history.append(self.pressure)
        self.pressure_history = self.pressure_history[-history_depth:]

        self.absolute_humidity = self._bme280.get_humidity()
        self.humidity = self.compensate_humidity(self.absolute_humidity, self.device_temperature, self.temperature)
        self.humidity_history.append(self.humidity)
        self.humidity_history = self.humidity_history[-history_depth:]
        self.dewpoint = self.get_dewpoint(self.humidity, self.device_temperature)

        self.lux = self._ltr559.get_lux()
        self.lux_history.append(self.lux)
        self.lux_history = self.lux_history[-history_depth:]

        wind_direction = self._ioe.input(WV)

        self._lock.release()

        value, self.wind_degrees = min(wind_direction_to_degrees.items(), key=lambda item: abs(item[0] - wind_direction))
        self._avg_wind_direction.append(self.wind_degrees)
        # Discard old wind directon samples
        self._avg_wind_direction = self._avg_wind_direction[-wind_direction_samples:]
        self.wind_degrees_avg = sum(self._avg_wind_direction) / len(self._avg_wind_direction)

        self.wind_direction_history.append(self.wind_degrees_avg)
        self.wind_direction_history = self.wind_direction_history[-history_depth:]

        # Don't update rain/wind data until we've sampled for long enough
        if delta < interval:
            return

        rain_hz = self._rain_counts / delta
        wind_hz = self._wind_counts / delta
        self.reset_counts()

        # print(delta, rain_hz, wind_hz)

        wind_hz /= 2.0  # Two pulses per rotation
        wind_cms = wind_hz * WV_CIRCUMFERENCE * 1.18
        self.wind_kmph = (wind_cms * 60 * 60) / 100.0 / 1000.0
        self.wind_mph = max(0, self.wind_kmph * 0.621371)
        self._avg_wind_speed.append(self.wind_mph)

        self.wind_mph_avg = sum(self._avg_wind_speed) / len(self._avg_wind_speed)

        self.wind_speed_history.append(self.wind_mph_avg)

        self.rain_mm_sec = rain_hz * RAIN_MM_PER_TICK
        self.rain_mm_total = self._rain_counts * RAIN_MM_PER_TICK
        self.rain_history.append(self.rain_mm_sec)
        self.rain_history = self.rain_history[-history_depth:]

    def handle_ioe_interrupt(self, pin):
        self._lock.acquire(blocking=True)
        self._ioe.clear_interrupt()

        wind_counts, _ = self._ioe.read_switch_counter(ANI2)
        rain_counts, _ = self._ioe.read_switch_counter(R4)

        # If the counter value is *less* than the previous value
        # then we know the 7-bit switch counter overflowed
        # We bump the count value by the lost counts between last_wind and 128
        # since at 127 counts, one more count will overflow us back to 0
        if wind_counts < self._last_wind_counts:
            self._wind_counts += 128 - self._last_wind_counts
            self._wind_counts += wind_counts
        else:
            self._wind_counts += wind_counts - self._last_wind_counts

        self._last_wind_counts = wind_counts

        if rain_counts < self._last_rain_counts:
            self._rain_counts += 128 - self._last_rain_counts
            self._rain_counts += rain_counts
        else:
            self._rain_counts += rain_counts - self._last_rain_counts

        self._last_rain_counts = rain_counts

        # print(wind_counts, rain_counts, self._wind_counts, self._rain_counts)

        self._lock.release()


