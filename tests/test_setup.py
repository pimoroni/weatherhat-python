def test_setup(gpio, ioe, bme280, ltr559, smbus2):
    import weatherhat
    library = weatherhat.WeatherHAT()

    bus = smbus2.SMBus(1)

    bme280.BME280.assert_called_once_with(i2c_dev=bus)
    ltr559.LTR559.assert_called_once_with(i2c_dev=bus)
    ioe.IOE.assert_called_once_with(i2c_addr=0x12, interrupt_pin=4)

    del library


def test_api(gpio, ioe, bme280, ltr559, smbus2):
    import weatherhat
    library = weatherhat.WeatherHAT()

    bus = smbus2.SMBus(1)

    bme280.BME280(i2c_dev=bus).get_temperature.return_value = 20.0
    bme280.BME280(i2c_dev=bus).get_pressure.return_value = 10600.0
    bme280.BME280(i2c_dev=bus).get_humidity.return_value = 60.0

    ltr559.LTR559(i2c_dev=bus).get_lux.return_value = 100.0

    ioe.IOE(i2c_addr=0x12, interrupt_pin=4).input.return_value = 2.3

    library.temperature_offset = 5.0

    library.update()

    assert library.wind_direction_raw == 2.3
    assert library.wind_direction == 180
    assert library.device_temperature == 20.0
    assert library.temperature == 25.0
    assert library.pressure == 10600.0
    assert library.relative_humidity == 15.0
    assert library.humidity == 60.0
    assert library.lux == 100.0
