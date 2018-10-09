import time

try:
    import thread
except ImportError:
    import _thread as thread #Py3K changed it.

# Copies frames from renderer into OLED screen
class FrameCopier:
    def __init__(self, renderer, oled, srcX, srcY):
        self.renderer = renderer
        self.oled = oled
        self.srcX = srcX
        self.srcY = srcY

    def start(self):
        thread.start_new_thread(self.run, ())

    def run(self):
        frame = None
        while True:
            frame = self.renderer.wait_frame(frame)
            self.oled.copy_image(frame, 0, 0, self.srcX, self.srcY)
            self.oled.flush()

