# Eye of the Pi

This project started because I wanted to make [https://learn.adafruit.com/animated-snake-eyes-bonnet-for-raspberry-pi](this thing) I saw on Adafruit.

The project described there works the following way - a Python application draws these eyes using OpenGL (pi3d) on your normal screen and then there is a C program (`fbx2`)
that continuously copies image from the screen framebuffer to the displays connected over SPI.

I did not have Adafruit's board, my cheap displays from Aliexpress were slightly different and I could not make the whole thing work despite the effort.
So I decided to do it in an alternative way and use the opportunity to do it in Python only, no `fbx2`.

It was most interesting to me to play with the low-level display stuff (reading datasheet and playing with commands) so I guess I missed lots of ready-to-use libraries
like [Luma.OLED](https://luma-oled.readthedocs.io/en/latest/hardware.html)

The Python code in [Original Adafruit Pi_Eyes sources](https://github.com/adafruit/Pi_Eyes/) I found difficult to follow and modify because
it was a bit monolithic - everything was done in one huge `frame` method and there were lots of globals.

So I refactored it to be a bit more OOP-ish and introduced a clear separation between rendering code (the `Eye` class that draws the eye in a certain state using pi3d)
and animation code (that controls eye state based on time or GPIO input).
The hope is that two-eye version (when I start working on it) will also benefit a lot from that `Eye` class it as lots of copy&paste can be removed from `eyes.py`.

## How to use
It is still work in progress really...

So what there is currently:
* `SSD1351.py` - the "driver" for the SSD1351 display that initialises it (when connected the right way because all pins are hard-coded)
and allows flushing the internal framebuffer to the OLED. It also has couple of methods - one to fill the entire framebuffer with a single colour
and another - to copy an image into the framebuffer.
* `test.py` is just a very simple test to check the display and its driver work - it contiuously fills the display with red, then gren, then blue in a loop and prints
how many times per second it can flush the framebuffer (the fps).
* `eye.py` - the Eye class with eye-rendering logic extracted from `cyclop.py`
* Then there are files from the [Original Adafruit Pi_Eyes sources](https://github.com/adafruit/Pi_Eyes/):
** `cyclop.py` - that has been refactored. The animation logic still remains the this file (although moved to `Animator` class) while eye-rendering logic was moved to
a new `eye.py` file (`Eye` class). The refactoring is still work in progress.
** `eyes.py` - has not been touched yet but the idea is to eventually convert it the same way as `cyclop.py` - to use `Eye` class.
** `gfxutil.py` - no changes too
** `graphics/` directory - the original graphics, no changes

If you want to run it - just run `cyclop.py` - it should render an eye into a small 128x128 window and at the same time copy the content to the OLED screen connected.

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
* [Original Adafruit Pi_Eyes sources](https://github.com/adafruit/Pi_Eyes/)
* [Adafruit SSD1351 Python library](https://github.com/twchad/Adafruit_Python_SSD1351)
* [Adafruit's board](https://www.adafruit.com/product/3356). I did not have it but it shows nice video how these eyes should operate
* [SSD1351 datasheet](https://cdn-shop.adafruit.com/datasheets/SSD1351-Revision+1.3.pdf)
* [Luma.OLED](https://luma-oled.readthedocs.io/en/latest/hardware.html) - I haven't used it though
* [OLED Display Library Setup for the Raspberry Pi featuring SSD1331](https://www.bluetin.io/displays/oled-display-raspberry-pi-ssd1331/)


