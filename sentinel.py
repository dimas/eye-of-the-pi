#!/usr/bin/python

import pi3d
import time

import SSD1351
import eye
import model
import renderer
import copier
import autonomous

try:
    import thread
except ImportError:
    import _thread as thread #Py3K changed it.

# Fake proximity sensor, changes its output every 3 seconds
class ProximitySensor:
    status = True
    end = 0

    def object_in_range(self):
        if self.end <= time.time():
            self.end = time.time() + 3
            self.status = not self.status
        return self.status

# This is the main logic / behaviour of the application.
# Basically we keep the eyas shut until proximity sensor tells us there is an object in range,
# then we open the eyes and keep them open (blinking an moving around) until
# proximity sensor says there is not object in range.
# At this point we close the eyes and start from the beginning.
def controlThread(renderer, eyesModel):

  proximitySensor = ProximitySensor()

  eyePosInput = autonomous.AutonomousEyePositionInput()
  pupilSizeInput = autonomous.AutonomousPupilSizeInput()

  while True:

    while not proximitySensor.object_in_range():
        time.sleep(0.05)

    print("Object in range, waking up")

    # Start with the eyes closed
    eyesModel.close_eye(model.ALL, time.time(), 0)
    eyesModel.set_position(0, 0)
    eyesModel.set_pupil_size(0)

    renderer.start()

    # Wake up, open eyes slowly
    eyesModel.open_eye(model.ALL, time.time(), 0.7)
    eyesModel.enable_autoblink(time.time())

    # Put simulators to the same state as the model so there won't be a sudden jump
    # in eye position or pupil size
    eyePosInput.set_position(0, 0)
    pupilSizeInput.set_size(0)

    last_frame = None

    # While there is an object in range of the sensor, do autonomous eye movement
    while proximitySensor.object_in_range():
        now = time.time()

        # Get data from simulators
        x, y = eyePosInput.get_position(now)
        pupilSize = pupilSizeInput.get_size(now)

        eyesModel.set_position(x, y)
        eyesModel.set_pupil_size(pupilSize)

        # There is no point in moving the eye faster than renderer can draw it
        # otherwise it is going to be a very tight, CPU hogging loop.
        # So wait until Renderer produces another frame even though we do not need it here
        last_frame = renderer.wait_frame(last_frame)

    print("No object in range, going to sleep")

    # Going to sleep, close eyes slowly
    eyesModel.disable_autoblink()
    eyesModel.close_eye(model.ALL, time.time(), 0.7)
    # Give the model time to go through the transition
    time.sleep(1)
    # Stop rendering to not waste resources while we are sleeping
    renderer.stop()


# MAIN

OLED_WIDTH      = 128
OLED_HEIGHT     = 128
GAP             = OLED_WIDTH // 2

leftOLED = SSD1351.SSD1351(spi_bus = 0, spi_device = 0, dc = 24, rst = 25)
rightOLED = SSD1351.SSD1351(spi_bus = 1, spi_device = 0, dc = 23, rst = 26)

displayWidth = 2 * OLED_WIDTH + GAP
displayHeight = OLED_HEIGHT

# Display must be created before the eyes or their draw() method throws...
display = pi3d.Display.create(samples = 4, w = displayWidth, h = displayHeight)
# make background green while debugging and refactoring so it is easier to see individual eye pieces
display.set_background(0, 0.5, 0, 1) # r,g,b,alpha
# A 2D camera is used, mostly to allow for pixel-accurate eye placement,
# but also because perspective isn't really helpful or needed here, and
# also this allows eyelids to be handled somewhat easily as 2D planes.
# Line of sight is down Z axis, allowing conventional X/Y cartesion
# coords for 2D positions.
cam    = pi3d.Camera(is_3d=False, at=(0,0,0), eye=(0,0,-1000))
light  = pi3d.Light(lightpos=(0, -500, -500), lightamb=(0.2, 0.2, 0.2))

# eyeRadius is the size, in pixels, at which the whole eye will be rendered
# onscreen.  eyePosition, also pixels, is the offset (left or right) from
# the center point of the screen to the center of each eye.
eyePosition = OLED_WIDTH // 2 + GAP // 2
eyeRadius   = OLED_WIDTH / 2.1

rightEye = eye.Eye(eyeRadius, -eyePosition, 0, True);
leftEye = eye.Eye(eyeRadius, eyePosition, 0, False);

eyesModel = model.TwoEyesModel()

renderer = renderer.Renderer(display, [leftEye, rightEye], eyesModel)

leftOLEDCopier = copier.FrameCopier(renderer, leftOLED, displayWidth // 2 - eyePosition - OLED_WIDTH // 2, 0)
rightOLEDCopier = copier.FrameCopier(renderer, rightOLED, displayWidth // 2 + eyePosition - OLED_WIDTH // 2, 0)

leftOLEDCopier.start()
rightOLEDCopier.start()

thread.start_new_thread(controlThread, (renderer, eyesModel))

# Renderer's run() method never returns. And of course it needs to be invoked from the main thread.
# Because pi3d...
renderer.run()
