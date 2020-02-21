# https://learn.adafruit.com/micropython-hardware-ssd1306-oled-display/software
import time
from machine import I2C, Pin
from ssd1306 import SSD1306_I2C
from ulock import rlock

class Display:

    def __init__(self,
                 width = 128, height = 64,
                 scl_pin_id = 15, sda_pin_id = 4,
                 freq = 400000):

        self._lock = rlock()
        self.width = width
        self.height = height
        self.poweron()
        self.i2c = I2C(scl = Pin(scl_pin_id, Pin.OUT, Pin.PULL_UP),
                               sda = Pin(sda_pin_id, Pin.OUT, Pin.PULL_UP),
                               freq = freq)
        self.display = SSD1306_I2C(width, height, self.i2c)
        self.show = self.display.show

    def poweron(self, pin=16):
        with self._lock:
            pin_reset = Pin(pin, mode=Pin.OUT)
            pin_reset.value(0)
            time.sleep_ms(50)
            pin_reset.value(1)

    def clear(self):
        # print("display clear called")
        with self._lock:
            self.display.fill(0)
            self.display.show()

    def show_text(self, text, x = 0, y = 0, clear_first = True, show_now = True, hold_seconds = 0):
        with self._lock:
            if clear_first:
                self.clear()
            self.display.text(text, x, y)
            if show_now:
                self.display.show()
                if hold_seconds > 0:
                    time.sleep(hold_seconds)

    def wrap(self, text, start_line = 0,
             height_per_line = 8, width_per_char = 8,
             start_pixel_each_line = 0):

        with self._lock:
            chars_per_line = self.width//width_per_char
            max_lines = self.height//height_per_line - start_line
            lines = [(text[chars_per_line*line: chars_per_line*(line+1)], start_pixel_each_line, height_per_line*(line+start_line)) for line in range(max_lines)]

        return lines


    def show_text_wrap(self, text,
                       start_line = 0, height_per_line = 8, width_per_char = 8, start_pixel_each_line = 0,
                       clear_first = True, show_now = True, hold_seconds = 0, clear_to_eol=True):

        with self._lock:
            if clear_first:
                # print("show_text_wrap: clear first")
                self.clear()

            for line, x, y in self.wrap(text, start_line, height_per_line, width_per_char, start_pixel_each_line):
                if clear_to_eol and len(line) != 0:
                    # print("clear_to_eol: x %d y %d w %d h %d" % (x, y, self.width-x, height_per_line))
                    self.display.fill_rect(x, y, self.width-x, height_per_line, 0)
                self.show_text(line, x, y, clear_first = False, show_now = False)

            if show_now:
                self.display.show()
                if hold_seconds > 0:
                    time.sleep(hold_seconds)


    def show_datetime(self, year, month, day, hour, minute, second):
        with self._lock:
            datetime = [year, month, day, hour, minute, second]
            datetime_str = ["{0:0>2}".format(d) for d in datetime]

            self.show_text(text = '-'.join(datetime_str[:3]), x = 0, y = 0, clear_first = True, show_now = False)
            self.show_text(text = ':'.join(datetime_str[3:6]), x = 0, y = 10, clear_first = False, show_now = True)


    def show_time(self, year, month, day, hour, minute, second):
        self.show_datetime(year, month, day, hour, minute, second)
