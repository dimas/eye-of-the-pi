# Eye of the Pi

This project started because I wanted to make [https://learn.adafruit.com/animated-snake-eyes-bonnet-for-raspberry-pi](this thing) I saw on Adafruit.

The project described there works the following way - a Python application draws these eyes using OpenGL (pi3d) on your normal screen and then there is a C program (`fbx2`)
that continuously copies image from the screen framebuffer to the displays connected over SPI.

I did not have Adafruit's board, my cheap displays from Aliexpress were slightly different and I could not make the whole thing work despite the effort.
So I decided to do it in an alternative way and use the opportunity to do it in Python only, no `fbx2`.

It was most interesting to me to make low-level display stuff to work so I guess I missed lots of ready-to-use libraries like [Luma.OLED](https://luma-oled.readthedocs.io/en/latest/hardware.html)

## How to use

Well, you probably cannot.

The current state of things is that I have `SSD1351.py` - the "driver" for the SSD1351 display that initialises it (when connected the right way because all pins are hard-coded)
and allows flushing the internal framebuffer to the OLED. It also has couple of methods - one to fill the entire framebuffer with a single colour
and another - to copy a different image into the framebuffer.

`test.py` is just a very simple test to check the display and its driver work - it contiuously fills the display with red, then gren, then blue and prints
how many times per second it can flush the framebuffer (the fps).

I am not uploading the patched `cyclop.py` yet - the code from the original project that was modified to copy image it draws to the OLED. I have a proof of concept version that
works but it is too messy. The idea, however is quite simple there - you let it draw on its configured display, then use `pi3d.util.Screenshot.screenshot()` to grab a screenshot
and send returned data `SSD1351.copy_image()` method. Then following `SSD1351.flush()` will put it into the display.

## How to connect
At the moment, I am playing with just a single display which is connected the following way

| Display        | Pi 3 pin       |
| -------------- |:--------------:|
| GND            | any GND        |
| VCC            | any +3V        |
| SCL            | 23 SCLK (SPI)  |
| SDA            | 19 MOSI (SPI)  |
| RES            | 22 GPIO 25     |
| DC             | 18 GPIO 24     |
| CS             | 24 CE0 (SPI)   |

The image below is from [OLED Display Library Setup for the Raspberry Pi featuring SSD1331](https://www.bluetin.io/displays/oled-display-raspberry-pi-ssd1331/).
It shows Pi Zero but I used exactly the same pins for my regular Pi 3.
![OLED Display Library Setup for the Raspberry Pi featuring SSD1331](docs/images/ssd1331-oled-display-raspberry-pi-connection.jpg)

## Notes

The choice of the format for the framebuffer was driven by two things:
* when you are using `pi3d` to take the screenshot of what you rendered with OpenGL, you are getting back a 3-dimensional `numpy.ndarray` - width x height x 3 (for RGB).
* `spidev.xfer` method can only understand normal python lists (`[0, 1, 2...]`) and does not understand neither `array.array` nor `numpy.ndarray`

Obviously conversion was unavoidable and as I discovered that in Python operations like `dst[b:b+n] = src[a:a+n]` are INSANELY slow, I choosen to keep
data in really efficient `numpy.ndarray` instead (where the same operation is fast) and only convert it to the list the moment we are sending data to the screen.


## Links
* [The project on Adafruit](https://learn.adafruit.com/animated-snake-eyes-bonnet-for-raspberry-pi?view=all)
* [Adafruit SSD1351 Python library](https://github.com/twchad/Adafruit_Python_SSD1351)
* [Adafruit's board](https://www.adafruit.com/product/3356). I did not have it but it shows nice video how these eyes should operate
* [SSD1351 datasheet](https://cdn-shop.adafruit.com/datasheets/SSD1351-Revision+1.3.pdf)
* [Luma.OLED](https://luma-oled.readthedocs.io/en/latest/hardware.html) - I haven't used it though
* [OLED Display Library Setup for the Raspberry Pi featuring SSD1331](https://www.bluetin.io/displays/oled-display-raspberry-pi-ssd1331/)


