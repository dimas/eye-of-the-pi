import SSD1351
import time

oled = SSD1351.SSD1351()

flushes = 0
lastt = int(time.time())
lastf = 0
while True:
    oled.fill(0xFF, 0x00, 0x00)
    oled.flush()
    flushes += 1
    oled.fill(0x00, 0xFF, 0x00)
    oled.flush()
    flushes += 1
    oled.fill(0x00, 0x00, 0xFF)
    oled.flush()
    flushes += 1

    tm = int(time.time())
    if lastt != tm:
        print("%d fps" % (flushes - lastf))
        lastt = tm
        lastf = flushes

