import pi3d
import threading
import time

# Renderer continuously draws eyes represented by the passed EyesModel.
# The assumption is model state is changing because something uses state-manipulation methods of the EyesModel
# (and also because of autoblink enabled) so sequence of frames we are rendering shows the animation.
# Code interested in new frames should repeatedly call wait_frame method which will return
# a new image as soon as it becomes available.
#
# Note that originally I plannned to implement rendering in a background thread so Renderer would have start/stop
# methods for Renderer that allows controlling but alas:
#   load_opengl must be called on main thread for <pi3d.Buffer.Buffer object at 0x74d72250>
#   ...
#   AttributeError: 'Buffer' object has no attribute 'vbuf'
# so I am going to just call run() from the main thread. Still start/stop methods are provided
# to allow control thread to pause and resume rendering when needed.
class Renderer:

    def __init__(self, display, eyes, model):
        self.eyes = eyes
        self.model = model
        self.frame = None
        self.condition = threading.Condition()
        self.started = False
        self.display = display

    # Has to be called from the main thread
    def run(self):
        while True:
            # Wait until something calls start()
            with self.condition:
                while not self.started:
                    self.condition.wait()

            self.render_frame()


    def render_frame(self):
        self.display.loop_running()

        now = time.time()

        states = self.model.get_state(now)

        for i in range(2):
          eye = self.eyes[i]
          eye.set_state(states[i])
          eye.draw()

        img = pi3d.util.Screenshot.screenshot()

        # Make new image available to waiting threads
        with self.condition:
            self.frame = img
            self.condition.notifyAll()

    # Wait until next frame is rendered and return it
    def wait_frame(self, last_frame):
        with self.condition:
            while self.frame is last_frame:
                self.condition.wait()
            return self.frame

    def start(self):
        with self.condition:
            self.started = True
            self.condition.notifyAll()
        print("Renderer started")

    def stop(self):
        with self.condition:
            self.started = False
        print("Renderer stopped")
