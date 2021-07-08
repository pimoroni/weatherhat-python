#!/usr/bin/env python3
import logging
import math
import pathlib
import random
import sys
import threading
import time

import ltr559
import RPi.GPIO as GPIO
import ST7789
from fonts.ttf import RobotoMedium as UserFont
from PIL import Image, ImageDraw, ImageFont

from weatherhat import WeatherHAT


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


RECT_BANNER = (0, 0, DISPLAY_WIDTH, 40)


class View:
    def __init__(self, image):
        self._image = image
        self._draw = ImageDraw.Draw(image)

        self.font = ImageFont.truetype(UserFont, 18)
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
        text_h = 11
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
            space_width = font.getsize(" ")[0]
            line_height = int(font.size * line_spacing)
            max_lines = math.floor(height / line_height)
            lines = []

            # Determine if text can fit at current scale.
            words = text.split(" ")

            while len(lines) < max_lines and len(words) > 0:
                line = []

                while (
                    len(words) > 0
                    and font.getsize(" ".join(line + [words[0]]))[0] <= width
                ):
                    line.append(words.pop(0))

                lines.append(" ".join(line))

            if len(lines) <= max_lines and len(words) == 0:
                # Solution is found, render the text.
                y = int(
                    y1
                    + (height / 2)
                    - (len(lines) * line_height / 2)
                    - (line_height - font.size) / 2
                )

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
        self._draw.rectangle(RECT_BANNER, COLOR_BLUE)
        self.text_in_rect(
            text,
            self.font,
            RECT_BANNER,
            line_spacing=1,
            textcolor=COLOR_WHITE
        )


class SensorView(View):
    title = ""

    def __init__(self, image, sensordata):
        View.__init__(self, image)
        self._data = sensordata

    def render(self):
        self.clear()
        self.banner(self.title)
        self.render_view()

    def render_view(self):
        pass


class MainView(SensorView):
    """Main overview.

    Displays weather summary and navigation hints.

    """

    title = "Overview"

    def render_view(self):
        self._draw.text(
            (0, 40),
            "Temperature: {:0.2f}C".format(self._data.temperature),
            font=self.font_small,
            fill=COLOR_WHITE
        )
        self._draw.text(
            (0, 60),
            "Pressure: {:0.4f}hPA".format(self._data.pressure),
            font=self.font_small,
            fill=COLOR_WHITE
        )
        self._draw.text(
            (0, 80),
            "Humidity: {:0.2f}%".format(self._data.humidity),
            font=self.font_small,
            fill=COLOR_WHITE
        )
        self._draw.text(
            (0, 100),
            "Wind Direction: {:0.0f} ({})".format(
                self._data.wind_degrees_avg,
                self._data.degrees_to_cardinal(self._data.wind_degrees_avg)),
            font=self.font_small,
            fill=COLOR_WHITE
        )
        self._draw.text(
            (0, 120),
            "Wind Speed: {:0.2f}mph".format(self._data.wind_mph),
            font=self.font_small,
            fill=COLOR_WHITE
        )


class SettingsView(View):
    pass


class MainSettingsView(SettingsView):
    pass


class WindView(SensorView):
    """Wind Overview."""

    title = "Wind"


class WindSettingsView(SettingsView):
    pass


class RainView(SensorView):
    """Rain Overview."""

    title = "Rain"


class RainSettingsView(SettingsView):
    pass


class TPHView(SensorView):
    """Temperature, Pressure & Humidity."""

    title = "BME280: Environment"


class TPHSettingsView(SettingsView):
    pass


class LightView(SensorView):
    """Light."""

    title = "LTR559: LIght"


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

    sensordata = WeatherHAT()

    viewcontroller = ViewController(
        [
            (
                MainView(image, sensordata),
                MainSettingsView(image)
            ),
            (
                WindView(image, sensordata),
                WindSettingsView(image)
            ),
            (
                RainView(image, sensordata),
                RainSettingsView(image),
            ),
            (
                TPHView(image, sensordata),
                TPHSettingsView(image),
            ),
            (
                LightView(image, sensordata),
                LightSettingsView(image),
            ),
        ]        
    )

    while True:
        sensordata.update()
        viewcontroller.update()
        viewcontroller.render()
        display.display(image.convert("RGB"))
        time.sleep(1.0 / FPS)


if __name__ == "__main__":
    main()
