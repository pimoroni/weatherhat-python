import tkinter
from PIL import ImageTk

import pathlib
import sys
modpath = pathlib.Path("../").resolve()
sys.path.insert(0, str(modpath))
import RPi.GPIO as GPIO  # noqa: E402


class ST7789:
    def __init__(
        self,
        rotation=90,
        port=0,
        cs=1,
        dc=9,
        backlight=12,
        spi_speed_hz=0
    ):

        self._tk_done = False
        self.tk_root = tkinter.Tk()
        self.tk_root.title('Weather HAT')
        self.tk_root.geometry('240x240')
        self.tk_root.aspect(240, 240, 240, 240)
        self.tk_root.protocol('WM_DELETE_WINDOW', self._close_window)
        self.cv = None
        self.cvh = 240
        self.cvw = 240
        self.last_key = None

    def wait_for_window_close(self):
        while not self._tk_done:
            self.update()

    def resize(self, event):
        """Resize background image to window size."""
        # adapted from:
        # https://stackoverflow.com/questions/24061099/tkinter-resize-background-image-to-window-size
        # https://stackoverflow.com/questions/19838972/how-to-update-an-image-on-a-canvas
        self.cvw = event.width
        self.cvh = event.height
        self.cv.config(width=self.cvw, height=self.cvh)
        image = self.disp_img_copy.resize([self.cvw, self.cvh])
        self.photo = ImageTk.PhotoImage(image)
        self.cv.itemconfig(self.cvhandle, image=self.photo, anchor='nw')
        self.tk_root.update()

    def tk_update(self):
        self.tk_root.update_idletasks()
        self.tk_root.update()

    def _close_window(self):
        self._tk_done = True
        self.tk_root.destroy()

    def _key(self, event):
        buttons = [5, 6, 16, 24]
        labels = ["A", "B", "X", "Y"]
        key = event.keysym.upper()
        if key in labels:
            index = labels.index(key)
            pin = buttons[index]
            GPIO.handlers[pin][0](pin)

    def display(self, image):
        self.disp_img_copy = image.copy()
        self.photo = ImageTk.PhotoImage(self.disp_img_copy.resize((self.cvw, self.cvh)))

        if self.cv is None:
            self.cv = tkinter.Canvas(self.tk_root, width=240, height=240)
            self.cv.bind('<Configure>', self.resize)
            self.cv.bind('<Key>', self._key)
            self.cv.focus_set()

        self.cv.pack(side='top', fill='both', expand='yes')
        self.cvhandle = self.cv.create_image(0, 0, image=self.photo, anchor='nw')

        self.tk_root.update()
