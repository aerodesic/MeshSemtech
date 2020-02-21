#!/bin/bash
if [ "$1" = "-c" ]; then
  ampy -p /dev/ttyUSB0 rmdir .
  shift
fi

FILES="config_lora.py controller_esp32.py controller.py main.py sx127x.py uPySensors/ssd1306_i2c.py uPySensors/ssd1306.py $1"

for f in $FILES; do
    echo "sending $f"
    ampy -p /dev/ttyUSB0 put $f $f
done

