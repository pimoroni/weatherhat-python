#!/usr/bin/env python3
import math
import pathlib
import time

import yaml

import RPi.GPIO as GPIO
import ST7789
from fonts.ttf import ManropeMedium as UserFont
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

# Only the ALPHA channel is used from these images
icon_drop = Image.open("icons/icon-drop.png").convert("RGBA")
icon_nodrop = Image.open("icons/icon-nodrop.png").convert("RGBA")
icon_rightarrow = Image.open("icons/icon-rightarrow.png").convert("RGBA")
icon_alarm = Image.open("icons/icon-alarm.png").convert("RGBA")
icon_snooze = Image.open("icons/icon-snooze.png").convert("RGBA")
icon_help = Image.open("icons/icon-help.png").convert("RGBA")
icon_settings = Image.open("icons/icon-settings.png").convert("RGBA")
icon_channel = Image.open("icons/icon-channel.png").convert("RGBA")
icon_backdrop = Image.open("icons/icon-backdrop.png").convert("RGBA")
icon_return = Image.open("icons/icon-return.png").convert("RGBA")


class View:
    def __init__(self, image):
        self._image = image
        self._draw = ImageDraw.Draw(image)

        self.font_large = ImageFont.truetype(UserFont, 40)
        self.font = ImageFont.truetype(UserFont, 25)
        self.font_medium = ImageFont.truetype(UserFont, 22)
        self.font_small = ImageFont.truetype(UserFont, 14)

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
        pass

    def clear(self):
        self._draw.rectangle((0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT), (0, 0, 0))

    def icon(self, icon, position, color):
        col = Image.new("RGBA", icon.size, color=color)
        self._image.paste(col, position, mask=icon)

    def label(
        self,
        position="X",
        text=None,
        bgcolor=(0, 0, 0),
        textcolor=(255, 255, 255),
        margin=4,
    ):
        if position not in ["A", "B", "X", "Y"]:
            raise ValueError(f"Invalid label position {position}")

        text_w, text_h = self._draw.textsize(text, font=self.font)
        text_h -= 1
        text_w += margin * 2
        text_h += margin * 2

        if position == "A":
            x, y = 0, 0
        if position == "B":
            x, y = 0, DISPLAY_HEIGHT - text_h
        if position == "X":
            x, y = DISPLAY_WIDTH - text_w, 0
        if position == "Y":
            x, y = DISPLAY_WIDTH - text_w, DISPLAY_HEIGHT - text_h

        x2, y2 = x + text_w, y + text_h

        self._draw.rectangle((x, y, x2, y2), bgcolor)
        self._draw.text(
            (x + margin, y + margin - 1), text, font=self.font, fill=textcolor
        )

    def overlay(self, text, top=0):
        """Draw an overlay with some auto-sized text."""
        self._draw.rectangle(
            (0, top, DISPLAY_WIDTH, DISPLAY_HEIGHT), fill=(192, 225, 254)
        )  # Overlay backdrop
        self._draw.rectangle((0, top, DISPLAY_WIDTH, top + 1), fill=COLOR_BLUE)  # Top border
        self.text_in_rect(
            text,
            self.font,
            (3, top, DISPLAY_WIDTH - 3, DISPLAY_HEIGHT - 2),
            line_spacing=1,
        )

    def text_in_rect(self, text, font, rect, line_spacing=1.1, textcolor=(0, 0, 0)):
        x1, y1, x2, y2 = rect
        width = x2 - x1
        height = y2 - y1

        # Given a rectangle, reflow and scale text to fit, centred
        while font.size > 0:
            # space_width = font.getsize(" ")[0]
            line_height = int(font.size * line_spacing)
            max_lines = math.floor(height / line_height)
            lines = []

            # Determine if text can fit at current scale.
            words = text.split(" ")

            while len(lines) < max_lines and len(words) > 0:
                line = []

                while (len(words) > 0 and font.getsize(" ".join(line + [words[0]]))[0] <= width):
                    line.append(words.pop(0))

                lines.append(" ".join(line))

            if len(lines) <= max_lines and len(words) == 0:
                # Solution is found, render the text.
                y = int(y1 + (height / 2) - (len(lines) * line_height / 2) - (line_height - font.size) / 2)

                bounds = [x2, y, x1, y + len(lines) * line_height]

                for line in lines:
                    line_width = font.getsize(line)[0]
                    x = int(x1 + (width / 2) - (line_width / 2))
                    bounds[0] = min(bounds[0], x)
                    bounds[2] = max(bounds[2], x + line_width)
                    self._draw.text((x, y), line, font=self.font, fill=textcolor)
                    y += line_height

                return tuple(bounds)

            font = ImageFont.truetype(font.path, font.size - 1)

    def banner(self, text, bgcolor=COLOR_BLUE, textcolor=COLOR_WHITE):
        rect = (0, 0, DISPLAY_WIDTH, 30)
        self._draw.rectangle(rect, bgcolor)
        self.text_in_rect(
            text,
            self.font,
            rect,
            line_spacing=1,
            textcolor=textcolor
        )


class SensorView(View):
    title = ""
    GRAPH_BAR_WIDTH = 10

    def __init__(self, image, sensordata, settings=None):
        View.__init__(self, image)
        self._data = sensordata
        self._settings = settings
        self.init_view()

    def init_view(self):
        pass

    def render(self):
        self.clear()
        # self.banner(self.title)
        self.render_view()

    def render_view(self):
        pass

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
            anchor="lb"
        )

        self._draw.text(
            (tw, 32),
            units,
            font=self.font_medium,
            fill=COLOR_WHITE,
            anchor="lb"
        )

    def graph(self, values, graph_x=0, graph_y=0, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, vmin=0, vmax=1.0, bar_width=2, colors=None):
        if not len(values):
            return
        if colors is None:
            #         Blue          Teal           Green        Yellow         Red
            colors = [(0, 0, 255), (0, 255, 255), (0, 255, 0), (255, 255, 0), (255, 0, 0)]

        max_values = int(width / bar_width)

        values = [entry.value for entry in values[-max_values:]]

        for i, v in enumerate(values):
            v = min(vmax, max(vmin, v))
            scale = float(v - vmin) / float(vmax - vmin)
            color = scale * (len(colors) - 1)
            color_idx = int(color)      # The integer part of color becomes our index into the colors array
            blend = color - color_idx   # The fractional part forms the blend amount between the two colours
            bar_color = colors[color_idx]
            if color_idx < len(colors) - 1:
                bar_color = self.blend(colors[color_idx], colors[color_idx + 1], blend)
                bar_color = bar_color

            x = (i * bar_width)
            h = scale * height
            self._draw.rectangle((
                graph_x + x, graph_y + height - h,
                graph_x + x + int(bar_width / 2), graph_y + height
            ), fill=bar_color)


class MainView(SensorView):
    """Main overview.

    Displays weather summary and navigation hints.

    """

    title = "Overview"

    def __init__(self, image, sensordata, settings=None):
        self._graph_mode = False
        SensorView.__init__(self, image, sensordata, settings)

    def draw_info(self, x, y, color, label, data, desc, right=False, vmin=0, vmax=20):
        w = 100
        o_x = 0 if right else 20

        if self._graph_mode:
            vmax = max(vmax, max([h.value for h in data]))  # auto ranging?
            self.graph(data, x + o_x + 15, y + 10, 90, 32, vmin=vmin, vmax=vmax, bar_width=10, colors=[color])
        else:
            if type(data) is list:
                data = data[-1].value

            if data < 100:
                data = "{:0.1f}".format(data)
            else:
                data = "{:0.0f}".format(data)

            self._draw.text(
                (x + w + o_x, y + 10 + 32),  # Text height is fixed at 32 here, since we're only using numbers
                data,
                font=self.font_large,
                fill=color,
                anchor="rb"  # Using "rb" stops text jumping vertically as often
            )

        self._draw.text(
            (x + w + o_x, y + 45 + 20),
            desc,
            font=self.font,
            fill=COLOR_WHITE,
            anchor="rb"
        )
        label_img = Image.new("RGB", (65, 20))
        label_draw = ImageDraw.Draw(label_img)
        label_draw.text((0, 20) if right else (0, 0), label, font=self.font_medium, fill=COLOR_GREY, anchor="lb" if right else "lt")
        label_img = label_img.rotate(90, expand=True)
        if right:
            self._image.paste(label_img, (x + w, y))
        else:
            self._image.paste(label_img, (x, y))

    def button_b(self):
        self._graph_mode = not self._graph_mode

    def render_view(self):
        self.draw_info(0, 0, (20, 20, 220), "RAIN", self._data.rain_mm_sec.history(), "mm/s", vmax=5)
        self.draw_info(0, 75, (20, 20, 220), "PRES", self._data.pressure.history(), "mbar")
        self.draw_info(0, 150, (20, 100, 220), "TEMP", self._data.temperature.history(), "°C")

        self.draw_info(120, 0, (220, 20, 220), "WIND", self._data.wind_speed.history_ms(), "m/s", right=True)
        self.draw_info(120, 75, (220, 100, 20), "LIGHT", self._data.lux.history(), "lux", right=True)
        self.draw_info(120, 150, (10, 10, 220), "HUM", self._data.relative_humidity.history(), "%rh", right=True)


class SettingsView(View):
    """Baseclass for a settings edit view."""

    def __init__(self, image, options=[]):
        self._options = options
        self._current_option = 0
        self._change_mode = False
        self._help_mode = False
        self.channel = None

        View.__init__(self, image)

    def render(self):
        self.clear()
        self.icon(icon_backdrop.rotate(180), (DISPLAY_WIDTH - 26, 0), COLOR_WHITE)
        self.icon(icon_return, (DISPLAY_WIDTH - 19 - 3, 3), (55, 55, 55))

        if len(self._options) == 0:
            return

        option = self._options[self._current_option]
        title = option["title"]
        prop = option["prop"]
        object = option.get("object", self.channel)
        value = getattr(object, prop)
        fmt = option.get("format", "{value}")
        if type(fmt) is str:
            text = fmt.format(value=value)
        else:
            text = option["format"](value)
        mode = option.get("mode", "int")
        help = option["help"]

        if self._change_mode:
            self.label(
                "Y",
                "Yes" if mode == "bool" else "++",
                textcolor=COLOR_BLACK,
                bgcolor=COLOR_WHITE,
            )
            self.label(
                "B",
                "No" if mode == "bool" else "--",
                textcolor=COLOR_BLACK,
                bgcolor=COLOR_WHITE,
            )
        else:
            self.label("B", "Next", textcolor=COLOR_BLACK, bgcolor=COLOR_WHITE)
            self.label("Y", "Change", textcolor=COLOR_BLACK, bgcolor=COLOR_WHITE)

        self._draw.text((3, 36), f"{title} : {text}", font=self.font, fill=COLOR_WHITE)

        if self._help_mode:
            self.icon(icon_backdrop.rotate(90), (0, 0), COLOR_BLUE)
            self._draw.rectangle((7, 3, 23, 19), COLOR_BLACK)
            self.overlay(help, top=26)

        self.icon(icon_help, (0, 0), COLOR_BLUE)

    def button_a(self):
        self._help_mode = not self._help_mode
        return True

    def button_b(self):
        if self._help_mode:
            return True

        if self._change_mode:
            option = self._options[self._current_option]
            prop = option["prop"]
            mode = option.get("mode", "int")
            object = option.get("object", self.channel)

            value = getattr(object, prop)
            if mode == "bool":
                value = False
            else:
                inc = option["inc"]
                limit = option["min"]
                value -= inc
                if mode == "float":
                    value = round(value, option.get("round", 1))
                if value < limit:
                    value = limit
            setattr(object, prop, value)
        else:
            self._current_option += 1
            self._current_option %= len(self._options)

        return True

    def button_x(self):
        if self._change_mode:
            self._change_mode = False
            return True
        return False

    def button_y(self):
        if self._help_mode:
            return True
        if self._change_mode:
            option = self._options[self._current_option]
            prop = option["prop"]
            mode = option.get("mode", "int")
            object = option.get("object", self.channel)

            value = getattr(object, prop)
            if mode == "bool":
                value = True
            else:
                inc = option["inc"]
                limit = option["max"]
                value += inc
                if mode == "float":
                    value = round(value, option.get("round", 1))
                if value > limit:
                    value = limit
            setattr(object, prop, value)
        else:
            self._change_mode = True

        return True


class MainSettingsView(SettingsView):
    pass


class WindDirectionView(SensorView):
    """Wind Direction."""

    title = "Wind Direction"

    def __init__(self, image, sensordata, settings=None):
        SensorView.__init__(self, image, sensordata, settings)

    def render_view(self):
        ox = DISPLAY_WIDTH / 2
        oy = 20 + ((DISPLAY_HEIGHT - 20) / 2)
        needle = self._data.needle
        speed_ms = self._data.wind_speed.average_ms(60)
        # gust_ms = self._data.wind_speed.gust_ms()
        compass_direction = self._data.wind_direction.average_compass()

        radius = 50
        speed_max = 4.4  # m/s
        speed = min(speed_ms, speed_max)
        speed /= float(speed_max)

        arrow_radius_min = 10
        arrow_radius_max = 30
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

                self._draw.ellipse((x - 1, y - 1, x + 1, y + 1), (int(255 / trail_length * i), 0, 0))

        radius += 30
        for direction, name in weatherhat.wind_degrees_to_cardinal.items():
            p = math.radians(direction)
            x = ox + math.sin(p) * radius
            y = oy - math.cos(p) * radius

            name = "".join([word[0] for word in name.split(" ")])
            tw, th = self._draw.textsize(name, font=self.font_small)
            x -= tw / 2
            y -= th / 2
            self._draw.text((x, y), name, font=self.font_small, fill=COLOR_WHITE)

        self.heading(speed_ms, "m/s")

        direction_text = "".join([word[0] for word in compass_direction.split(" ")])

        self._draw.text(
            (DISPLAY_WIDTH, 0),
            direction_text,
            font=self.font_large,
            fill=COLOR_WHITE,
            anchor="rt"
        )


class WindSpeedView(SensorView):
    """Wind Speed."""

    title = "Wind Speed"

    def render_view(self):
        self.heading(
            self._data.wind_speed.latest_ms(),
            "m/s"
        )

        self.graph(
            self._data.wind_speed.history(),
            graph_x=0,
            graph_y=35,
            width=DISPLAY_WIDTH,
            height=DISPLAY_HEIGHT - 35,
            vmin=0,
            vmax=20,
            bar_width=self.GRAPH_BAR_WIDTH
        )


class WindSettingsView(SettingsView):
    pass


class RainView(SensorView):
    """Rain Overview."""

    title = "Rain"

    def render_view(self):
        self.heading(
            self._data.rain_mm_sec.latest().value,
            "mm/s"
        )

        self.graph(
            self._data.rain_mm_sec.history(),
            graph_x=0,
            graph_y=35,
            width=DISPLAY_WIDTH,
            height=DISPLAY_HEIGHT - 35,
            vmin=0,
            vmax=1.0,
            bar_width=self.GRAPH_BAR_WIDTH
        )


class RainSettingsView(SettingsView):
    pass


class TPHView(SensorView):
    """Temperature, Pressure & Humidity."""

    title = "BME280: Environment"

    def render_view(self):
        self.heading(
            self._data.temperature.latest().value,
            "°C"
        )

        self.graph(
            self._data.temperature.history(),
            graph_x=0,
            graph_y=35,
            width=DISPLAY_WIDTH,
            height=DISPLAY_HEIGHT - 35,
            vmin=self._settings.minimum_temperature,
            vmax=self._settings.maximum_temperature,
            bar_width=self.GRAPH_BAR_WIDTH
        )


class TPHSettingsView(SettingsView):
    pass


class LightView(SensorView):
    """Light."""

    title = "LTR559: Light"

    def render_view(self):
        self.heading(
            self._data.lux.latest().value,
            "lux"
        )

        self.graph(
            self._data.lux.history(int(DISPLAY_WIDTH / self.GRAPH_BAR_WIDTH)),
            graph_x=0,
            graph_y=35,
            width=DISPLAY_WIDTH,
            height=DISPLAY_HEIGHT - 35,
            vmin=0,
            vmax=1000,
            bar_width=self.GRAPH_BAR_WIDTH
        )


class LightSettingsView(SettingsView):
    pass


class ViewController:
    def __init__(self, views):
        self.views = views
        self._current_view = 0
        self._current_subview = 0

    @property
    def home(self):
        return self._current_view == 0 and self._current_subview == 0

    def next_subview(self):
        view = self.views[self._current_view]
        if isinstance(view, tuple):
            self._current_subview += 1
            self._current_subview %= len(view)

    def next_view(self):
        if self._current_subview == 0:
            self._current_view += 1
            self._current_view %= len(self.views)
            self._current_subview = 0

    def prev_view(self):
        if self._current_subview == 0:
            self._current_view -= 1
            self._current_view %= len(self.views)
            self._current_subview = 0

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
        self.minimum_temperature = 4
        self.maximum_temperature = 40

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

    def save(self):
        dump = yaml.dump(self._config)

        if dump == self._last_save:
            return False

        with open(self._file, "w") as file:
            file.write(dump)

        self._last_save = dump

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

        self.rain_mm_total = history.History()
        self.rain_mm_sec = history.History()

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

        self.wind_speed.append(self.sensor.wind_speed)
        self.wind_direction.append(self.sensor.wind_direction)

        self.rain_mm_total.append(self.sensor.rain_mm_total)
        self.rain_mm_sec.append(self.sensor.rain_mm_sec)

        self.needle = math.radians(self.wind_direction.average(self.WIND_DIRECTION_AVERAGE_SAMPLES))
        self.needle_trail.append(self.needle)
        self.needle_trail = self.needle_trail[-self.COMPASS_TRAIL_SIZE:]


def main():
    def handle_button(pin):
        index = BUTTONS.index(pin)
        label = LABELS[index]

        if label == "A":  # Select View
            viewcontroller.button_a()

        if label == "B":
            viewcontroller.button_b()

        if label == "X":
            viewcontroller.button_x()

        if label == "Y":
            viewcontroller.button_y()

    display = ST7789.ST7789(
        rotation=90,
        port=0,
        cs=1,
        dc=9,
        backlight=13,
        spi_speed_hz=SPI_SPEED_MHZ * 1000 * 1000
    )

    image = Image.new("RGBA", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=(255, 255, 255))

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(BUTTONS, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    for pin in BUTTONS:
        GPIO.add_event_detect(pin, GPIO.FALLING, handle_button, bouncetime=200)

    sensordata = SensorData()

    settings = Config()

    main_options = []
    wind_direction_options = [
        {
            "title": "Wind Trails",
            "prop": "wind_trails",
            "mode": "bool",
            "format": lambda value: "Yes" if value else "No",
            "object": settings,
            "help": "Enable/disable wind directon trails."
        }
    ]
    temperature_options = [
        {
            "title": "Minimum Temperature",
            "prop": "minimum_temperature",
            "inc": 1,
            "min": -40,
            "max": 100,
            "format": "{value}C",
            "object": settings,
            "help": "Minimum temperature in the graph, in degrees C."
        },
        {
            "title": "Maximum Temperature",
            "prop": "maximum_temperature",
            "inc": 1,
            "min": -40,
            "max": 100,
            "format": "{value}C",
            "object": settings,
            "help": "Maximum temperature in the graph, in degrees C."
        }
    ]

    viewcontroller = ViewController(
        [
            (
                MainView(image, sensordata, settings),
                MainSettingsView(image, options=main_options)
            ),
            (
                WindDirectionView(image, sensordata, settings),
                WindSettingsView(image, options=wind_direction_options)
            ),
            (
                WindSpeedView(image, sensordata, settings),
                WindSettingsView(image)
            ),
            (
                RainView(image, sensordata, settings),
                RainSettingsView(image),
            ),
            (
                TPHView(image, sensordata, settings),
                TPHSettingsView(image, options=temperature_options),
            ),
            (
                LightView(image, sensordata, settings),
                LightSettingsView(image),
            ),
        ]
    )

    while True:
        sensordata.update(interval=5.0)
        viewcontroller.update()
        viewcontroller.render()
        display.display(image.convert("RGB"))
        settings.save()
        time.sleep(1.0 / FPS)


if __name__ == "__main__":
    main()
