BCM = 0

IN = 0
OUT = 1

PUD_UP = 1
PUD_DOWN = 0

RISING = 1
FALLING = 0

handlers = {}


def setmode(pin):
    pass


def setwarnings(mode):
    pass


def setup(pin, direction, pull_up_down=None):
    pass


def add_event_detect(pin, edge, handler, bouncetime=0):
    if pin not in handlers:
        handlers[pin] = {}
    handlers[pin][edge] = handler
