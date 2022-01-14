#!/usr/bin/env python3
import math
import pathlib
import time

import yaml

import RPi.GPIO as GPIO
import ST7789
from fonts.ttf import ManropeBold as UserFont
from PIL import Image, ImageDraw, ImageFont

import weatherhat
from weatherhat import history


FPS = 10

BUTTONS = [5, 6, 16, 24]
LABELS = ["A", "B", "X", "Y"]

DISPLAY_WIDTH = 240
DISPLAY_HEIGHT = 240
SPI_SPEED_MHZ = 80

COLOR_WHITE = (255, 255, 255)
COLOR_BLUE = (31, 137, 251)
COLOR_GREEN = (99, 255, 124)
COLOR_YELLOW = (254, 219, 82)
COLOR_RED = (247, 0, 63)
COLOR_BLACK = (0, 0, 0)
COLOR_GREY = (100, 100, 100)


class View:
    def __init__(self, image):
        self._image = image
        self._draw = ImageDraw.Draw(image)

        self.font_large = ImageFont.truetype(UserFont, 80)
        self.font = ImageFont.truetype(UserFont, 50)
        self.font_medium = ImageFont.truetype(UserFont, 44)
        self.font_small = ImageFont.truetype(UserFont, 28)

    @property
    def canvas_width(self):
        return self._image.size[0]

    @property
    def canvas_height(self):
        return self._image.size[1]

    def button_a(self):
        return False

    def button_b(self):
        return False

    def button_x(self):
        return False

    def button_y(self):
        return False

    def update(self):
        pass

    def render(self):
        self.clear()

    def clear(self):
        self._draw.rectangle((0, 0, self.canvas_width, self.canvas_height), (0, 0, 0))


class SensorView(View):
    title = ""
    GRAPH_BAR_WIDTH = 20

    def __init__(self, image, sensordata, settings=None):
        View.__init__(self, image)
        self._data = sensordata
        self._settings = settings

    def blend(self, a, b, factor):
        blend_b = factor
        blend_a = 1.0 - factor
        return tuple([int((a[i] * blend_a) + (b[i] * blend_b)) for i in range(3)])

    def heading(self, data, units):
        if data < 100:
            data = "{:0.1f}".format(data)
        else:
            data = "{:0.0f}".format(data)

        tw, th = self._draw.textsize(data, self.font_large)

        self._draw.text(
            (0, 32),
            data,
            font=self.font_large,
            fill=COLOR_WHITE,
            anchor="lm"
        )

        self._draw.text(
            (tw, 64),
            units,
            font=self.font_medium,
            fill=COLOR_WHITE,
            anchor="lb"
        )

    def footer(self, label):
        self._draw.text((int(self.canvas_width / 2), self.canvas_height - 30), label, font=self.font_medium, fill=COLOR_GREY, anchor="mm")

    def graph(self, values, graph_x=0, graph_y=0, width=None, height=None, vmin=0, vmax=1.0, bar_width=2, colors=None):
        if not len(values):
            return

        if width is None:
            width = self.canvas_width

        if height is None:
            height = self.canvas_height

        if colors is None:
            #         Blue          Teal           Green        Yellow         Red
            colors = [(0, 0, 255), (0, 255, 255), (0, 255, 0), (255, 255, 0), (255, 0, 0)]

        vrange = vmax - vmin
        vstep = float(height) / vrange

        if vmin >= 0:
            midpoint_y = height
        else:
            midpoint_y = vmax * vstep
            self._draw.line((graph_x, graph_y + midpoint_y, graph_x + width, graph_y + midpoint_y), fill=COLOR_GREY)

        max_values = int(width / bar_width)

        values = [entry.value for entry in values[-max_values:]]

        for i, v in enumerate(values):
            v = min(vmax, max(vmin, v))

            offset_y = graph_y

            if vmin < 0:
                bar_height = midpoint_y * float(v) / float(vmax)
            else:
                bar_height = midpoint_y * float(v - vmin) / float(vmax - vmin)

            if v < 0:
                offset_y += midpoint_y
                bar_height = (height - midpoint_y) * float(abs(v)) / abs(vmin)

            color = float(v - vmin) / float(vmax - vmin) * (len(colors) - 1)
            color_idx = int(color)      # The integer part of color becomes our index into the colors array
            blend = color - color_idx   # The fractional part forms the blend amount between the two colours
            bar_color = colors[color_idx]
            if color_idx < len(colors) - 1:
                bar_color = self.blend(colors[color_idx], colors[color_idx + 1], blend)
                bar_color = bar_color

            x = (i * bar_width)

            if v < 0:
                self._draw.rectangle((
                    graph_x + x, offset_y,
                    graph_x + x + int(bar_width / 2), offset_y + bar_height
                ), fill=bar_color)
            else:
                self._draw.rectangle((
                    graph_x + x, offset_y + midpoint_y - bar_height,
                    graph_x + x + int(bar_width / 2), offset_y + midpoint_y
                ), fill=bar_color)


class MainView(SensorView):
    """Main Overview.

    Displays weather summary and navigation hints.

    """

    title = "Overview"

    def draw_info(self, x, y, color, label, data, desc, right=False, vmin=0, vmax=20, graph_mode=False):
        w = 200
        o_x = 0 if right else 40

        if graph_mode:
            vmax = max(vmax, max([h.value for h in data]))  # auto ranging?
            self.graph(data, x + o_x + 30, y + 20, 180, 64, vmin=vmin, vmax=vmax, bar_width=20, colors=[color])
        else:
            if type(data) is list:
                if len(data) > 0:
                    data = data[-1].value
                else:
                    data = 0

            if data < 100:
                data = "{:0.1f}".format(data)
            else:
                data = "{:0.0f}".format(data)

            self._draw.text(
                (x + w + o_x, y + 20 + 32),  # Position is the right, center of the text
                data,
                font=self.font_large,
                fill=color,
                anchor="rm"  # Using "rm" stops text jumping vertically
            )

        self._draw.text(
            (x + w + o_x, y + 90 + 40),
            desc,
            font=self.font,
            fill=COLOR_WHITE,
            anchor="rb"
        )
        label_img = Image.new("RGB", (130, 40))
        label_draw = ImageDraw.Draw(label_img)
        label_draw.text((0, 40) if right else (0, 0), label, font=self.font_medium, fill=COLOR_GREY, anchor="lb" if right else "lt")
        label_img = label_img.rotate(90, expand=True)
        if right:
            self._image.paste(label_img, (x + w, y))
        else:
            self._image.paste(label_img, (x, y))

    def render(self):
        SensorView.render(self)
        self.render_graphs()

    def render_graphs(self, graph_mode=False):
        self.draw_info(0, 0, (20, 20, 220), "RAIN", self._data.rain_mm_sec.history(), "mm/s", vmax=self._settings.maximum_rain_mm, graph_mode=graph_mode)
        self.draw_info(0, 150, (20, 20, 220), "PRES", self._data.pressure.history(), "mbar", graph_mode=graph_mode)
        self.draw_info(0, 300, (20, 100, 220), "TEMP", self._data.temperature.history(), "°C", graph_mode=graph_mode, vmin=self._settings.minimum_temperature, vmax=self._settings.maximum_temperature)

        x = int(self.canvas_width / 2)
        self.draw_info(x, 0, (220, 20, 220), "WIND", self._data.wind_speed.history(), "m/s", right=True, graph_mode=graph_mode)
        self.draw_info(x, 150, (220, 100, 20), "LIGHT", self._data.lux.history(), "lux", right=True, graph_mode=graph_mode)
        self.draw_info(x, 300, (10, 10, 220), "HUM", self._data.relative_humidity.history(), "%rh", right=True, graph_mode=graph_mode)


class MainViewGraph(MainView):
    title = "Overview: Graphs"

    def render(self):
        SensorView.render(self)
        self.render_graphs(graph_mode=True)


class WindDirectionView(SensorView):
    """Wind Direction."""

    title = "Wind"
    metric = "m/sec"

    def __init__(self, image, sensordata, settings=None):
        SensorView.__init__(self, image, sensordata, settings)

    def render(self):
        SensorView.render(self)
        ox = self.canvas_width / 2
        oy = 40 + ((self.canvas_height - 60) / 2)
        needle = self._data.needle
        speed_ms = self._data.wind_speed.average(60)
        # gust_ms = self._data.wind_speed.gust()
        compass_direction = self._data.wind_direction.average_compass()

        radius = 80
        speed_max = 4.4  # m/s
        speed = min(speed_ms, speed_max)
        speed /= float(speed_max)

        arrow_radius_min = 20
        arrow_radius_max = 60
        arrow_radius = (speed * (arrow_radius_max - arrow_radius_min)) + arrow_radius_min
        arrow_angle = math.radians(130)

        tx, ty = ox + math.sin(needle) * (radius - arrow_radius), oy - math.cos(needle) * (radius - arrow_radius)
        ax, ay = ox + math.sin(needle) * (radius - arrow_radius), oy - math.cos(needle) * (radius - arrow_radius)

        arrow_xy_a = ax + math.sin(needle - arrow_angle) * arrow_radius, ay - math.cos(needle - arrow_angle) * arrow_radius
        arrow_xy_b = ax + math.sin(needle) * arrow_radius, ay - math.cos(needle) * arrow_radius
        arrow_xy_c = ax + math.sin(needle + arrow_angle) * arrow_radius, ay - math.cos(needle + arrow_angle) * arrow_radius

        # Compass red end
        self._draw.line((
            ox,
            oy,
            tx,
            ty
        ), (255, 0, 0), 5)

        # Compass white end
        """
        self._draw.line((
            ox,
            oy,
            ox + math.sin(needle - math.pi) * radius,
            oy - math.cos(needle - math.pi) * radius
        ), (255, 255, 255), 5)
        """

        self._draw.polygon([arrow_xy_a, arrow_xy_b, arrow_xy_c], fill=(255, 0, 0))

        if self._settings.wind_trails:
            trails = 40
            trail_length = len(self._data.needle_trail)
            for i, p in enumerate(self._data.needle_trail):
                # r = radius
                r = radius + trails - (float(i) / trail_length * trails)
                x = ox + math.sin(p) * r
                y = oy - math.cos(p) * r

                self._draw.ellipse((x - 2, y - 2, x + 2, y + 2), (int(255 / trail_length * i), 0, 0))

        radius += 60
        for direction, name in weatherhat.wind_degrees_to_cardinal.items():
            p = math.radians(direction)
            x = ox + math.sin(p) * radius
            y = oy - math.cos(p) * radius

            name = "".join([word[0] for word in name.split(" ")])
            tw, th = self._draw.textsize(name, font=self.font_small)
            x -= tw / 2
            y -= th / 2
            self._draw.text((x, y), name, font=self.font_small, fill=COLOR_GREY)

        self.heading(speed_ms, self.metric)
        self.footer(self.title.upper())

        direction_text = "".join([word[0] for word in compass_direction.split(" ")])

        self._draw.text(
            (self.canvas_width, 32),
            direction_text,
            font=self.font_large,
            fill=COLOR_WHITE,
            anchor="rm"
        )


class WindSpeedView(SensorView):
    """Wind Speed."""

    title = "WIND"
    metric = "m/s"

    def render(self):
        SensorView.render(self)
        self.heading(
            self._data.wind_speed.latest(),
            self.metric
        )
        self.footer(self.title.upper())

        self.graph(
            self._data.wind_speed.history(),
            graph_x=4,
            graph_y=70,
            width=self.canvas_width,
            height=self.canvas_height - 130,
            vmin=self._settings.minimum_wind_ms,
            vmax=self._settings.maximum_wind_ms,
            bar_width=self.GRAPH_BAR_WIDTH
        )


class RainView(SensorView):
    """Rain."""

    title = "Rain"
    metric = "mm/s"

    def render(self):
        SensorView.render(self)
        self.heading(
            self._data.rain_mm_sec.latest().value,
            self.metric
        )
        self.footer(self.title.upper())

        self.graph(
            self._data.rain_mm_sec.history(),
            graph_x=4,
            graph_y=70,
            width=self.canvas_width,
            height=self.canvas_height - 130,
            vmin=self._settings.minimum_rain_mm,
            vmax=self._settings.maximum_rain_mm,
            bar_width=self.GRAPH_BAR_WIDTH
        )


class TemperatureView(SensorView):
    """Temperature."""

    title = "TEMP"
    metric = "°C"

    def render(self):
        SensorView.render(self)
        self.heading(
            self._data.temperature.latest().value,
            self.metric
        )
        self.footer(self.title.upper())

        self.graph(
            self._data.temperature.history(),
            graph_x=4,
            graph_y=70,
            width=self.canvas_width,
            height=self.canvas_height - 130,
            vmin=self._settings.minimum_temperature,
            vmax=self._settings.maximum_temperature,
            bar_width=self.GRAPH_BAR_WIDTH
        )


class LightView(SensorView):
    """Light."""

    title = "Light"
    metric = "lux"

    def render(self):
        SensorView.render(self)
        self.heading(
            self._data.lux.latest().value,
            self.metric
        )
        self.footer(self.title.upper())

        self.graph(
            self._data.lux.history(int(self.canvas_width / self.GRAPH_BAR_WIDTH)),
            graph_x=4,
            graph_y=70,
            width=self.canvas_width,
            height=self.canvas_height - 130,
            vmin=self._settings.minimum_lux,
            vmax=self._settings.maximum_lux,
            bar_width=self.GRAPH_BAR_WIDTH
        )


class PressureView(SensorView):
    """Pressure."""

    title = "PRESSURE"
    metric = "mbar"

    def render(self):
        SensorView.render(self)
        self.heading(
            self._data.pressure.latest().value,
            self.metric
        )
        self.footer(self.title.upper())

        self.graph(
            self._data.pressure.history(int(self.canvas_width / self.GRAPH_BAR_WIDTH)),
            graph_x=4,
            graph_y=70,
            width=self.canvas_width,
            height=self.canvas_height - 130,
            vmin=self._settings.minimum_pressure,
            vmax=self._settings.maximum_pressure,
            bar_width=self.GRAPH_BAR_WIDTH
        )


class HumidityView(SensorView):
    """Pressure."""

    title = "Humidity"
    metric = "%rh"

    def render(self):
        SensorView.render(self)
        self.heading(
            self._data.relative_humidity.latest().value,
            self.metric
        )
        self.footer(self.title.upper())

        self.graph(
            self._data.relative_humidity.history(int(self.canvas_width / self.GRAPH_BAR_WIDTH)),
            graph_x=4,
            graph_y=70,
            width=self.canvas_width,
            height=self.canvas_height - 130,
            vmin=0,
            vmax=100,
            bar_width=self.GRAPH_BAR_WIDTH
        )


class ViewController:
    def __init__(self, views):
        self.views = views
        self._current_view = 0
        self._current_subview = 0

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(BUTTONS, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        for pin in BUTTONS:
            GPIO.add_event_detect(pin, GPIO.FALLING, self.handle_button, bouncetime=200)

    def handle_button(self, pin):
        index = BUTTONS.index(pin)
        label = LABELS[index]

        if label == "A":  # Select View
            self.button_a()

        if label == "B":
            self.button_b()

        if label == "X":
            self.button_x()

        if label == "Y":
            self.button_y()

    @property
    def home(self):
        return self._current_view == 0 and self._current_subview == 0

    def next_subview(self):
        view = self.views[self._current_view]
        if isinstance(view, tuple):
            self._current_subview += 1
            self._current_subview %= len(view)

    def next_view(self):
        self._current_subview = 0
        self._current_view += 1
        self._current_view %= len(self.views)

    def prev_view(self):
        self._current_subview = 0
        self._current_view -= 1
        self._current_view %= len(self.views)

    def get_current_view(self):
        view = self.views[self._current_view]
        if isinstance(view, tuple):
            view = view[self._current_subview]

        return view

    @property
    def view(self):
        return self.get_current_view()

    def update(self):
        self.view.update()

    def render(self):
        self.view.render()

    def button_a(self):
        if not self.view.button_a():
            self.next_view()

    def button_b(self):
        self.view.button_b()

    def button_x(self):
        if not self.view.button_x():
            self.next_subview()
            return True
        return True

    def button_y(self):
        return self.view.button_y()


class Config:
    """Class to hold weather UI settings."""
    def __init__(self, settings_file="settings.yml"):
        self._file = pathlib.Path(settings_file)

        self._last_save = None

        # Wind Settings
        self.wind_trails = True

        # BME280 Settings
        self.minimum_temperature = -10
        self.maximum_temperature = 40

        self.minimum_pressure = 1000
        self.maximum_pressure = 1100

        self.minimum_lux = 100
        self.maximum_lux = 1000

        self.minimum_rain_mm = 0
        self.maximum_rain_mm = 10

        self.minimum_wind_ms = 0
        self.maximum_wind_ms = 40

        self.load()

    def load(self):
        if not self._file.is_file():
            return False

        try:
            self._config = yaml.safe_load(open(self._file))
        except yaml.parser.ParserError as e:
            raise yaml.parser.ParserError(
                "Error parsing settings file: {} ({})".format(self._file, e)
            )

    @property
    def _config(self):
        options = {}
        for k, v in self.__dict__.items():
            if not k.startswith("_"):
                options[k] = v
        return options

    @_config.setter
    def _config(self, config):
        for k, v in self.__dict__.items():
            if k in config:
                setattr(self, k, config[k])


class SensorData:
    AVERAGE_SAMPLES = 120
    WIND_DIRECTION_AVERAGE_SAMPLES = 60
    COMPASS_TRAIL_SIZE = 120

    def __init__(self):
        self.sensor = weatherhat.WeatherHAT()

        self.temperature = history.History()

        self.pressure = history.History()

        self.humidity = history.History()
        self.relative_humidity = history.History()
        self.dewpoint = history.History()

        self.lux = history.History()

        self.wind_speed = history.WindSpeedHistory()
        self.wind_direction = history.WindDirectionHistory()

        self.rain_mm_sec = history.History()
        self.rain_total = 0

        # Track previous average values to give the compass a trail
        self.needle_trail = []

    def update(self, interval=5.0):
        self.sensor.update(interval)

        self.temperature.append(self.sensor.temperature)

        self.pressure.append(self.sensor.pressure)

        self.humidity.append(self.sensor.humidity)
        self.relative_humidity.append(self.sensor.relative_humidity)
        self.dewpoint.append(self.sensor.dewpoint)

        self.lux.append(self.sensor.lux)

        if self.sensor.updated_wind_rain:
            self.rain_total = self.sensor.rain_total
        else:
            self.rain_total = 0

        self.wind_speed.append(self.sensor.wind_speed)
        self.wind_direction.append(self.sensor.wind_direction)

        self.rain_mm_sec.append(self.sensor.rain)

        self.needle = math.radians(self.wind_direction.average(self.WIND_DIRECTION_AVERAGE_SAMPLES))
        self.needle_trail.append(self.needle)
        self.needle_trail = self.needle_trail[-self.COMPASS_TRAIL_SIZE:]


def main():
    display = ST7789.ST7789(
        rotation=90,
        port=0,
        cs=1,
        dc=9,
        backlight=13,
        spi_speed_hz=SPI_SPEED_MHZ * 1000 * 1000
    )
    image = Image.new("RGBA", (DISPLAY_WIDTH * 2, DISPLAY_HEIGHT * 2), color=(255, 255, 255))
    sensordata = SensorData()
    settings = Config()
    viewcontroller = ViewController(
        (
            (
                MainView(image, sensordata, settings),
                MainViewGraph(image, sensordata, settings)
            ),
            (
                WindDirectionView(image, sensordata, settings),
                WindSpeedView(image, sensordata, settings)
            ),
            RainView(image, sensordata, settings),
            LightView(image, sensordata, settings),
            (
                TemperatureView(image, sensordata, settings),
                PressureView(image, sensordata, settings),
                HumidityView(image, sensordata, settings)
            ),
        )
    )

    while True:
        sensordata.update(interval=5.0)
        viewcontroller.update()
        viewcontroller.render()
        display.display(image.resize((DISPLAY_WIDTH, DISPLAY_HEIGHT)).convert("RGB"))
        time.sleep(1.0 / FPS)


if __name__ == "__main__":
    main()
