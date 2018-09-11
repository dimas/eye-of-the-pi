import spidev
import RPi.GPIO as GPIO
import time
import numpy as np

# https://cdn-shop.adafruit.com/datasheets/SSD1351-Revision+1.3.pdf

# Commands
CMD_SET_COL_ADDRESS             = 0x15 # Set Column Address
CMD_SET_ROW_ADDRESS             = 0x75 # Set Row Address
CMD_WRITE_RAM                   = 0x5C # Write RAM Command
CMD_READ_RAM                    = 0x5D # Read RAM Command
CMD_SET_REMAP                   = 0xA0 # Set Re-map / Color Depth (Display RAM to Panel)
CMD_SET_DISPLAY_START_LINE      = 0xA1 # Set Display Start Line
CMD_SET_DISPLAY_OFFSET          = 0xA2 # Set Display Offset
CMD_SET_DISPLAY_MODE_ALL_OFF    = 0xA4 # Set Display Mode - All OFF
CMD_SET_DISPLAY_MODE_ALL_ON     = 0xA5 # Set Display Mode - All ON (All pixels have GS63)
CMD_SET_DISPLAY_MODE_NORMAL     = 0xA6 # Set Display Mode - Reset to normal display
CMD_SET_DISPLAY_MODE_INVERSE    = 0xA7 # Set Display Mode - Inverse Display (GS0 -> GS63, GS1 -> GS62, ....)
CMD_FUNC_SELECT                 = 0xAB # Function Selection
CMD_SET_SLEEP_MODE_ON           = 0xAE # Set Sleep mode ON/OFF - Sleep mode On (Display OFF)
CMD_SET_SLEEP_MODE_OFF          = 0xAF # Set Sleep mode ON/OFF - Sleep mode OFF (Display ON)
CMD_SET_PHASE_LENGTH            = 0xB1 # Set Reset (Phase 1) / Pre-charge (Phase 2) period
CMD_DISPLAY_ENHANCEMENT         = 0xB2 # Display Enhancement
CMD_SET_CLOCK_DIVIDER           = 0xB3 # Front Clock Divider (DivSet) / Oscillator Frequency 
CMD_SET_SEGMENT_LOW_VOLTAGE     = 0xB4 # Set Segment Low Voltage (VSL)
CMD_SET_GPIO                    = 0xB5 # Set GPIO
CMD_SET_PRECHARGE2              = 0xB6 # Set Second Pre-charge Period
CMD_SET_GRAYSCALE_TABLE         = 0xB8 # Look Up Table for Gray Scale Pulse width
CMD_RESET_GRAYSCALE_TABLE       = 0xB9 # Use Built-in Linear LUT 
CMD_SET_PRECHARGE_VOLTAGE       = 0xBB # Set Pre-charge voltage
CMD_SET_VCOMH                   = 0xBE # Set Vcomh Voltage 
CMD_SET_CONTRAST_ABC            = 0xC1 # Set Contrast Current for Color A,B,C
CMD_SET_CONTRAST_MASTER         = 0xC7 # Master Contrast Current Control
CMD_SET_MULTIPLEX_RATIO         = 0xCA # Set MUX Ratio
CMD_SET_COMMAND_LOCK            = 0xFD # Set Command Lock
CMD_SET_SCROLL                  = 0x96 # Horizontal Scroll
CMD_STOP_SCROLL                 = 0x9E # Stop Moving
CMD_START_SCROLL                = 0x9F # Start Moving

# CMD_SET_REMAP

ADDR_INCREMENT_HORIZONTAL = 0x00
ADDR_INCREMENT_VERTICAL   = 0x01

MAP_SEG0_COL0   = 0x00
MAP_SEG0_COL127 = 0x02

COLOR_SEQ_ABC = 0x00
COLOR_SEQ_CBA = 0x04

SCAN_COM_INCR = 0x00
SCAN_COM_DECR = 0x10

ODD_EVEN_COM_SPLIT_DISABLED = 0x00
ODD_EVEN_COM_SPLIT_ENABLED  = 0x20

COLOR_DEPTH_65K          = 0x00
COLOR_DEPTH_65K_2        = 0x40
COLOR_DEPTH_262K         = 0x80
COLOR_DEPTH_262K_FORMAT2 = 0xC0

# CMD_FUNC_SELECT
EXTERNAL_VDD = 0x00
INTERNAL_VDD = 0x01

INTERFACE_8BIT_PARALLEL  = 0x00
INTERFACE_16BIT_PARALLEL = 0x40
INTERFACE_18BIT_PARALLEL = 0xC0

# CMD_SET_GPIO
GPIO0_INPUT_DISABLED = 0x00
GPIO0_INPUT_ENABLED  = 0x01
GPIO0_OUTPUT_LOW     = 0x02
GPIO0_OUTPUT_HIGH    = 0x03

GPIO1_INPUT_DISABLED = 0x00
GPIO1_INPUT_ENABLED  = 0x04
GPIO1_OUTPUT_LOW     = 0x08
GPIO1_OUTPUT_HIGH    = 0x0C

# CMD_SET_CONTRAST_ABC

DEFAULT_CONTRAST_A = 0x8A # 10001010b
DEFAULT_CONTRAST_B = 0x51 # 01010001b
DEFAULT_CONTRAST_C = 0x8A # 10001010b

# CMD_SET_CONTRAST_MASTER

DEFAULT_CONTRAST_MASTER = 0x0F # 1111b

# CMD_SET_COMMAND_LOCK
UNLOCK_MCU    = 0x12 # Unlock OLED driver IC MCU interface from entering command
LOCK_MCU      = 0x16 # Lock OLED driver IC MCU interface from entering command
LOCK_CONFIG   = 0xB0 # Command A2,B1,B3,BB,BE,C1 inaccessible in both lock and unlock state 
UNLOCK_CONFIG = 0xB1 # Command A2,B1,B3,BB,BE,C1 accessible if in unlock state  

class SSD1351:

    def __init__(self, spi_bus = 0, spi_device = 0, dc = 24, rst = 25):

        self.spi = spidev.SpiDev()
        self.spi.open(spi_bus, spi_device)
        self.spi.max_speed_hz = 10000000

        self.width = 128
        self.height = 128

        # RGB buffer ([x, y, component])
        self.frame = np.ndarray((self.width, self.height, 3), dtype=np.uint8)

        GPIO.setmode(GPIO.BCM)
        self.dc = dc
        self.rst = rst
#        GPIO.setmode(GPIO.BOARD)
#        self.dc = 16

        GPIO.setup(self.dc, GPIO.OUT)
        GPIO.setup(self.rst, GPIO.OUT)

        self.reset()
        self.configure()

    def set_dc(self, state):
        GPIO.output(self.dc, 1 if state else 0)

    def set_rst(self, state):
        GPIO.output(self.rst, 1 if state else 0)

    def command(self, c):
        self.set_dc(False)
        self.spi.xfer([c])

    def data(self, c):
        self.set_dc(True)
        self.spi.xfer([c])

    def get_spi_bufsize(self):
        # There is /sys/module/spidev/parameters/bufsiz which you can increase to allow bigger chunks
        # so I wanter to read it here and use buffer of that size.
        # But spidev library does not support anything but 4K really
        # See https://github.com/doceme/py-spidev/issues/62
        return 4096

    # data must be a list
    def bulkdata(self, data):
        self.set_dc(True)
        chunk_size = self.get_spi_bufsize()
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            self.spi.xfer(chunk)

    # data must be a numpy.ndarray (we call tolist() for each chunk)
    def data_ndarray(self, data):
        self.set_dc(True)
        chunk_size = self.get_spi_bufsize()
        # It is slightly more efficient to slice numpy array into chunks and then call tolist() on each
        # instead of converting the entire array tolist() and then cutting the list into chunks.
        # Either way, the tolist() thing is very expensive really. Would be better if numpy.array
        # implemented sequence protocol which spidev.xfer expects
        # But alas, https://github.com/numpy/numpy/issues/7315
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size].tolist()
            self.spi.xfer(chunk)

    def reset(self):
        # Pull RST# low for 1 millisecond.
        # Datasheet only really asks for 2 nanos (see 8.9 - Power ON and OFF sequence)
        self.set_rst(False)
        time.sleep(0.001)

        # Set RST# back high
        self.set_rst(True)

    def configure(self):

        self.command(CMD_SET_COMMAND_LOCK)
        self.data(UNLOCK_MCU)
        self.command(CMD_SET_COMMAND_LOCK)
        self.data(UNLOCK_CONFIG)

        # Lets keep the display off while it is being initialised
        self.command(CMD_SET_SLEEP_MODE_ON)

        self.command(CMD_SET_CLOCK_DIVIDER)
        # As of frequency divider (low nibble) at 2-3 the flicker becomes apparent and anything above I cannot even call flicker - you actually see display scan!
        # 1 is usable and 0 is the best but as brightness goes down as you are lowering the divider, 0 is a bit dark-ish if a low contrast is used too.
        self.data(0xF1)

        self.command(CMD_RESET_GRAYSCALE_TABLE)

        self.command(CMD_SET_MULTIPLEX_RATIO)
        self.data(127)

        self.command(CMD_SET_DISPLAY_START_LINE)
        self.data(0)

        self.command(CMD_SET_DISPLAY_OFFSET)
        self.data(0)

        self.command(CMD_SET_ROW_ADDRESS)
        self.bulkdata([0, 127]) # start, end

        self.command(CMD_SET_COL_ADDRESS)
        self.bulkdata([0, 127]) # start, end

        self.command(CMD_SET_GPIO)
        self.data(GPIO0_INPUT_DISABLED | GPIO1_INPUT_DISABLED)

        self.command(CMD_FUNC_SELECT)
        self.data(INTERNAL_VDD | INTERFACE_8BIT_PARALLEL)

        self.command(CMD_SET_PHASE_LENGTH)
        self.command(0x82) # default

        self.command(CMD_SET_VCOMH)
        self.command(0x05) # default

        self.command(CMD_SET_SEGMENT_LOW_VOLTAGE)
        self.data(0xA0) # According to datasheet, table 9-1, these are the only possible values
        self.data(0xB5)
        self.data(0x55)

        self.command(CMD_SET_PRECHARGE2)
        self.data(0x08) # default

        self.command(CMD_SET_CONTRAST_MASTER)
        self.data(DEFAULT_CONTRAST_MASTER // 4) # temp, to keep it low

        self.command(CMD_SET_CONTRAST_ABC)
        self.bulkdata([DEFAULT_CONTRAST_A, DEFAULT_CONTRAST_B, DEFAULT_CONTRAST_C])

        self.command(CMD_SET_REMAP)
        self.data(COLOR_DEPTH_262K | ODD_EVEN_COM_SPLIT_ENABLED | SCAN_COM_INCR | COLOR_SEQ_CBA | MAP_SEG0_COL127 | ADDR_INCREMENT_HORIZONTAL)

        self.command(CMD_SET_DISPLAY_MODE_NORMAL)

        # Given the display was configured, tell it to ignore further commands changing setup
        self.command(CMD_SET_COMMAND_LOCK)
        self.data(LOCK_CONFIG)

        self.command(CMD_SET_SLEEP_MODE_OFF)


    # Fill the entire framebuffer with the same color.
    # Only usefull for testing really.
    def fill(self, r, g, b):
      self.frame[:,:] = [r, g, b]

    # Flush framebuffer to the device
    def flush(self):
        raw = self.frame.flatten() >> 2
        self.command(CMD_WRITE_RAM)
        self.data_ndarray(raw)

    # Copy rectangle from the passed image into the screen frame buffer
    # The image is represented with RGB array - numpy.ndarray((width, height, 3))
    #   dstx, dsty - location in the destination (OLED frame buffer) where to copy
    #   srcx, srcy - location in the source image (img) where to copy from
    #   w, h       - width and height of the rectangle to copy
    # This method crops image being copied to a rectange that is valid for both source and destination.
    def copy_image(self, img, dstx = 0, dsty = 0, srcx = 0, srcy = 0, w = None, h = None):

        # 90% of this method is just validation of input and cropping the area to copy
        # Actual copying happens at the very end

        dstw = self.width
        dsth = self.height

        srcw = img.shape[1]
        srch = img.shape[0]

        # If no width/height were given, assume we want to copy the entire image
        # Use source size for now, it will be later limited to destination if needed
        if h == None:
            h = srch
        if w == None:
            w = srcw

        # Make sure destination coordinates are not negative
        if dstx < 0:
            w += dstx
            srcx -= dstx
            dstx = 0
        if dsty < 0:
            h += dsty
            srcy -= dsty
            dsty = 0

        # Make sure source coordinates are not negative
        if srcx < 0:
            w += srcx
            dstx -= srcx
            srcx = 0;
        if srcy < 0:
            h += srcy
            dsty -= srcy
            srcy = 0;

        # Make sure we are not copying more than available in the source
        if srcx + w > srcw:
            w = srcw - srcx
        if srcy + h > srch:
            h = srch - srcy

        # Make sure we are not copying more than the destination can fit
        if dstx + w > dstw:
            w = dstw - dstx
        if dsty + h > dsth:
            h = dsth - dsty

        # Finally, check if we ended up with nothing to copy
        if w <= 0 or h <= 0:
            return

        # print("(%d, %d) x (%d %d) => (%d, %d); src(%d, %d), dst(%d, %d)" % (srcx, srcy, w, h, dstx, dsty, srcw, srch, dstw, dsth))

        self.frame[dsty:dsty+h, dstx:dstx+w] = img[srcy:srcy+h, srcx:srcx+w]


