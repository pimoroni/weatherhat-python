import select
from datetime import timedelta

import gpiod
import gpiodevice
from gpiod.line import Bias, Edge

print("""buttons.py - Detect which button has been pressed
This example should demonstrate how to:
1. set up gpiod to read buttons,
2. determine which button has been pressed
Press Ctrl+C to exit!
""")

IP_PU_FE = gpiod.LineSettings(edge_detection=Edge.FALLING, bias=Bias.PULL_UP, debounce_period=timedelta(milliseconds=20))

# The buttons on Weather HAT are connected to pins 5, 6, 16 and 24
# They short to ground, so we must Bias them with the PULL_UP resistor
# and watch for a falling-edge.
BUTTONS = {5: IP_PU_FE, 6: IP_PU_FE, 16: IP_PU_FE, 24: IP_PU_FE}

# These correspond to buttons A, B, X and Y respectively
LABELS = {5: 'A', 6: 'B', 16: 'X', 24: 'Y'}

# Request the button pins from the gpiochip
chip = gpiodevice.find_chip_by_platform()
lines = chip.request_lines(
            consumer="buttons.py",
            config=BUTTONS
        )

# "handle_button" will be called every time a button is pressed
# It receives one argument: the associated input pin.
def handle_button(pin):
    label = LABELS[pin]
    print("Button press detected on pin: {} label: {}".format(pin, label))

# read_edge_events does not allow us to specify a timeout
# so we'll use poll to check if any events are waiting for us...
poll = select.poll()
poll.register(lines.fd, select.POLLIN)

# Poll for button events
while True:
    if poll.poll(10):
        for event in lines.read_edge_events():
            handle_button(event.line_offset)