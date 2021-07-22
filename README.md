# Weather HAT Python Library & Examples

[![Build Status](https://travis-ci.com/pimoroni/weatherhat-python.svg?branch=master)](https://travis-ci.com/pimoroni/weatherhat-python)
[![Coverage Status](https://coveralls.io/repos/github/pimoroni/weatherhat-python/badge.svg?branch=master)](https://coveralls.io/github/pimoroni/weatherhat-python?branch=master)
[![PyPi Package](https://img.shields.io/pypi/v/weatherhat.svg)](https://pypi.python.org/pypi/weatherhat)
[![Python Versions](https://img.shields.io/pypi/pyversions/weatherhat.svg)](https://pypi.python.org/pypi/weatherhat)

# Pre-requisites

You must enable (delete where appropriate):

* i2c: `sudo raspi-config nonint do_i2c 0`
* spi: `sudo raspi-config nonint do_spi 0`

You can optionally run `sudo raspi-config` or the graphical Raspberry Pi Configuration UI to enable interfaces.

# Installing

Stable library from PyPi:

* Just run `pip3 install weatherhat`

In some cases you may need to use `sudo` or install pip with: `sudo apt install python3-pip`

Latest/development library from GitHub:

* `git clone https://github.com/pimoroni/weatherhat-python`
* `cd weatherhat-python`
* `sudo ./install.sh`

