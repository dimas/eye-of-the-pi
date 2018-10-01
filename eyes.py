#!/usr/bin/python

# This is a hasty port of the Teensy eyes code to Python...all kludgey with
# an embarrassing number of globals in the frame() function and stuff.
# Needed to get SOMETHING working, can focus on improvements next.

import Adafruit_ADS1x15
import math
import pi3d
import random
#import thread
import time
import RPi.GPIO as GPIO
from gfxutil import *


import SSD1351
import eye

try:
    import thread
except ImportError:
    import _thread as thread #Py3K changed it.

# INPUT CONFIG for eye motion ----------------------------------------------
# ANALOG INPUTS REQUIRE SNAKE EYES BONNET

JOYSTICK_X_IN   = -1    # Analog input for eye horiz pos (-1 = auto)
JOYSTICK_Y_IN   = -1    # Analog input for eye vert position (")
PUPIL_IN        = -1    # Analog input for pupil control (-1 = auto)
JOYSTICK_X_FLIP = False # If True, reverse stick X axis
JOYSTICK_Y_FLIP = False # If True, reverse stick Y axis
PUPIL_IN_FLIP   = False # If True, reverse reading from PUPIL_IN
TRACKING        = True  # If True, eyelid tracks pupil
PUPIL_SMOOTH    = 16    # If > 0, filter input from PUPIL_IN
PUPIL_MIN       = 0.0   # Lower analog range from PUPIL_IN
PUPIL_MAX       = 1.0   # Upper "
#WINK_L_PIN      = 22    # GPIO pin for LEFT eye wink button
#BLINK_PIN       = 23    # GPIO pin for blink button (BOTH eyes)
#WINK_R_PIN      = 24    # GPIO pin for RIGHT eye wink button
WINK_L_PIN      = -1
BLINK_PIN       = -1
WINK_R_PIN      = -1
AUTOBLINK       = True  # If True, eyes blink autonomously

OLED_WIDTH      = 128
OLED_HEIGHT     = 128


leftOLED = SSD1351.SSD1351(spi_bus = 0, spi_device = 0, dc = 24, rst = 25)
rightOLED = SSD1351.SSD1351(spi_bus = 1, spi_device = 0, dc = 23, rst = 26)

image = None

# GPIO initialization ------------------------------------------------------

#GPIO.setmode(GPIO.BCM)
if WINK_L_PIN >= 0: GPIO.setup(WINK_L_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
if BLINK_PIN  >= 0: GPIO.setup(BLINK_PIN , GPIO.IN, pull_up_down=GPIO.PUD_UP)
if WINK_R_PIN >= 0: GPIO.setup(WINK_R_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)


# ADC stuff ----------------------------------------------------------------

if JOYSTICK_X_IN >= 0 or JOYSTICK_Y_IN >= 0 or PUPIL_IN >= 0:
	adc      = Adafruit_ADS1x15.ADS1015()
	adcValue = [0] * 4
else:
	adc = None

# Because ADC reads are blocking operations, they normally would slow down
# the animation loop noticably, especially when reading multiple channels
# (even when using high data rate settings).  To avoid this, ADC channels
# are read in a separate thread and stored in the global list adcValue[],
# which the animation loop can read at its leisure (with immediate results,
# no slowdown).
def adcThread(adc, dest):
	while True:
		for i in range(len(dest)):
			# ADC input range is +- 4.096V
			# ADC output is -2048 to +2047
			# Analog inputs will be 0 to ~3.3V,
			# thus 0 to 1649-ish.  Read & clip:
			n = adc.read_adc(i, gain=1)
			if   n <    0: n =    0
			elif n > 1649: n = 1649
			dest[i] = n / 1649.0 # Store as 0.0 to 1.0
		time.sleep(0.01) # 100-ish Hz

# Start ADC sampling thread if needed:
if adc:
	thread.start_new_thread(adcThread, (adc, adcValue))


# Set up display and initialize pi3d ---------------------------------------

GAP = OLED_WIDTH // 2
DISPLAY = pi3d.Display.create(samples = 4, w = 2*OLED_WIDTH + GAP, h = OLED_HEIGHT)
# make background green while debugging and refactoring so it is easier to see individual eye pieces
DISPLAY.set_background(0, 0.5, 0, 1) # r,g,b,alpha

# eyeRadius is the size, in pixels, at which the whole eye will be rendered
# onscreen.  eyePosition, also pixels, is the offset (left or right) from
# the center point of the screen to the center of each eye.
eyePosition = OLED_WIDTH // 2 + GAP // 2
eyeRadius   = OLED_WIDTH / 2.1

rightEye = eye.Eye(eyeRadius, -eyePosition, 0, True);
leftEye = eye.Eye(eyeRadius, eyePosition, 0, False);

# A 2D camera is used, mostly to allow for pixel-accurate eye placement,
# but also because perspective isn't really helpful or needed here, and
# also this allows eyelids to be handled somewhat easily as 2D planes.
# Line of sight is down Z axis, allowing conventional X/Y cartesion
# coords for 2D positions.
cam    = pi3d.Camera(is_3d=False, at=(0,0,0), eye=(0,0,-1000))
light  = pi3d.Light(lightpos=(0, -500, -500), lightamb=(0.2, 0.2, 0.2))

# Initialize static geometry -----------------------------------------------

# Init global stuff --------------------------------------------------------


#mykeys = pi3d.Keyboard() # For capturing key presses

#startX       = random.uniform(-30.0, 30.0)
#n            = math.sqrt(900.0 - startX * startX)
#startY       = random.uniform(-n, n)
#destX        = startX
#destY        = startY
#curX         = startX
#curY         = startY
#moveDuration = random.uniform(0.075, 0.175)
#holdDuration = random.uniform(0.1, 1.1)
#startTime    = 0.0
#isMoving     = False

#frames        = 0
#beginningTime = time.time()

#currentPupilScale       =  0.5
#prevPupilScale          = -1.0 # Force regen on first frame
#prevLeftUpperLidWeight  = 0.5
#prevLeftLowerLidWeight  = 0.5
#prevRightUpperLidWeight = 0.5
#prevRightLowerLidWeight = 0.5

#timeOfLastBlink = 0.0
#timeToNextBlink = 1.0
# These are per-eye (left, right) to allow winking:
#blinkStateLeft      = 0 # NOBLINK
#blinkStateRight     = 0
#blinkDurationLeft   = 0.1
#blinkDurationRight  = 0.1
#blinkStartTimeLeft  = 0
#blinkStartTimeRight = 0

#trackingPos = 0.3

import threading
#condition = threading.Condition()

class EyePositionInput:
    def get_position(self, now):
        return 0, 0

# Eye position from analog inputs
class JoystickEyePositionInput(EyePositionInput):
    def __init__(self, adcValue, joystickXIndex, joystickYIndex):
        self.adcValue = adcValue
        self.joystickXIndex = joystickXIndex
        self.joystickYIndex = joystickYIndex

    def get_position(self, now):
        curX = self.adcValue[self.joystickXIndex]
        curY = self.adcValue[self.joystickYIndex]
        if JOYSTICK_X_FLIP: curX = 1.0 - curX
        if JOYSTICK_Y_FLIP: curY = 1.0 - curY
        curX = -30.0 + curX * 60.0
        curY = -30.0 + curY * 60.0

        return curX, curY

# Autonomous eye position
# The logic here is taken from the original code and just encapsulated in a class
class AutonomousEyePositionInput(EyePositionInput):
    def __init__(self):
        self.set_position(0, 0)

    # Set initial position, the next call to get_position will return this position
    # but will immediately initiate eye movement to a random one
    def set_position(self, x, y):
        self.startX = self.destX = x
        self.startY = self.destY = y

        self.startTime = 0
        self.moveDuration = 0
        self.holdDuration = 0
        self.isMoving = False

    def get_position(self, now):
        dt = now - self.startTime

        if self.isMoving:
            if dt <= self.moveDuration:
                # Keep moving
                scale        = (now - self.startTime) / self.moveDuration
                # Ease in/out curve: 3*t^2-2*t^3
                scale        = 3.0 * scale * scale - 2.0 * scale * scale * scale
                curX         = self.startX + (self.destX - self.startX) * scale
                curY         = self.startY + (self.destY - self.startY) * scale
                return curX, curY
            else:
                # Swith to hold
                self.startX       = self.destX
                self.startY       = self.destY
                self.holdDuration = random.uniform(0.1, 1.1)
                self.startTime    = now
                self.isMoving     = False
                return self.destX, self.destY
        else:
            if dt >= self.holdDuration:
                # Start a new move
                self.destX        = random.uniform(-30.0, 30.0)
                n                 = math.sqrt(900.0 - self.destX * self.destX)
                self.destY        = random.uniform(-n, n)
                self.moveDuration = random.uniform(0.075, 0.175)
                self.startTime    = now
                self.isMoving     = True

            return self.startX, self.startY


class PupilSizeInput:
    def get_size(self, now):
        return 0

class ADCPupilSizeInput(PupilSizeInput):
    def __init__(self, adcValue, pupilSizeIndex):
        self.adcValue = adcValue
        self.pupilSizeIndex = pupilSizeIndex
        self.currentPupilScale = 0.5

    def get_size(self, now):
        v = self.adcValue[self.pupilSizeIndex]
        if PUPIL_IN_FLIP: v = 1.0 - v
        # If you need to calibrate PUPIL_MIN and MAX,
        # add a 'print v' here for testing.
        if   v < PUPIL_MIN: v = PUPIL_MIN
        elif v > PUPIL_MAX: v = PUPIL_MAX
        # Scale to 0.0 to 1.0:
        v = (v - PUPIL_MIN) / (PUPIL_MAX - PUPIL_MIN)
        if PUPIL_SMOOTH > 0:
                v = ((self.currentPupilScale * (PUPIL_SMOOTH - 1) + v) /
                     PUPIL_SMOOTH)

        self.currentPupilScale = v

        return v


class AutonomousPupilSizeInput(PupilSizeInput):
    def __init__(self):
        self.plan = []

    def get_size(self, now):
        last_size = 0.5
        current_interval = None
        while True:
            # Try finding the current interval in the existing plan if any
            # Linear search, shame on me
            for interval in self.plan:
                last_size = interval[3] # endValue
                if (interval[0] <= now and interval[0] + interval[1] >= now):
                    current_interval = interval
                    break

            if current_interval:
                break

            # There is no matching interval, generate next fragment of the plan
            self.plan = []
            self.generate_plan(now, last_size, random.random(), 4.0, 1.0)

        # We are in the middle of current_interval
        dt = (now - current_interval[0]) / current_interval[1]

        # v = startValue + (endValue - startValue) * dt
        v = current_interval[2] + (current_interval[3] - current_interval[2]) * dt

        return v
  
    # Recursive simulated pupil response when no analog sensor
    # Build plan for the next 'duration' seconds - append it to the 'plan' array
    # Each item of the plan list is an array of [startTime, duration, startValue, endValue]
    def generate_plan(
      self,
      startTime,
      startValue, # Pupil scale starting value (0.0 to 1.0)
      endValue,   # Pupil scale ending value
      duration,   # Start-to-end time, floating-point seconds
      range):     # +/- random pupil scale at midpoint

        if range >= 0.125: # Limit subdvision count, because recursion
            duration *= 0.5 # Split time & range in half for subdivision,
            range    *= 0.5 # then pick random center point within range:
            midValue  = ((startValue + endValue - range) * 0.5 +
                         random.uniform(0.0, range))
            self.generate_plan(startTime,            startValue, midValue, duration, range)
            self.generate_plan(startTime + duration, midValue  , endValue, duration, range)
        else: # No more subdivisons, add linear iris motion...
            self.plan.append([startTime, duration, startValue, endValue])

class EyelidModel:
    def __init__(self):
        pass

    def get_weight(self):
        return 0

class BlinkState:
    state = 0 # 0 - open, 1 - blinking/closed, 2 - opening
    startTime = 0
    duration = 0
    keepClosed = False

    def start_blink(self, now, duration):
        self.state     = 1 # ENBLINK
        self.startTime = now
        self.duration  = duration

# Represents the instant state of a single eye - pupil size, position
# as well as weight for both upper and lower eyelids
class EyeState:
    pupilSize = 0
    posX = 0
    posY = 0
#    eyelidWeight = []
    upperEyelidWeight = 0
    lowerEyelidWeight = 0

#    def __init__(self):
#        self.eyelidWeight = [0] * num

# Eyes model - provides instant state of the eyes to the rendering engine
# as well as methods that allow manipulating that state to the animation/control code.
# For example control code can request a certain eye to be closed and model will
# perform a smooth transition from open to closed state etc.
class EyesModel:

    def __init__(self, num = 2):
        self.autoblink = True
        self.timeOfLastBlink = 0
        self.timeToNextBlink = 0
        self.blinkState = [BlinkState()] * num
        self.trackingPos = 0.3

    def random_blink_duration(self):
        return random.uniform(0.035, 0.06)

    def close_eyes(self, now, flag, duration):
        if duration is None:
            duration = self.random_blink_duration() 
        pass

    # When flag=True, closes and eye and keeps it closed until
    # another call is made with flag=False
    # Notes:
    #   1. Calling with flag=True begins closing movement that will take some time
    #      so the eye slowly transitions from open to closed state
    #   2. Even if call with flag=True is immediately followed with another flag=False call,
    #      the closing movement will still complete before opening movement starts.
    #      This can be used to do a blink/wink
    #   2. After the eye is closed, it stays closed until until method is called with flag=False
    #      to "reenable" automatic blinking
    def close_eye(self, now, index, flag, duration):
        if duration is None:
            duration = self.random_blink_duration()
        if flag and blinkState.state != 1:
            self.start_blink(now, duration)
        blinkState.keepClosed = flag

    def auto_blink(self, now):
        if self.autoblink and (now - self.timeOfLastBlink) >= self.timeToNextBlink:
            self.timeOfLastBlink = now
            duration  = self.random_blink_duration()
            self.timeToNextBlink = duration * 3 + random.uniform(0.0, 4.0)
            for blinkState in self.blinkState:
                if blinkState.state != 1:
                    blinkState.start_blink(now, duration)

    # Calculate eyelid position (weight) for an eye
    def get_eyelid_weight(self, now, index):

        blinkState = self.blinkState[index]

        if blinkState.state: # Eye currently winking/blinking?
            # Check if blink time has elapsed...
            if (now - blinkState.startTime) >= blinkState.duration:
                if not blinkState.keepClosed:
                    blinkState.state += 1
                    if blinkState.state > 2:
                        blinkState.state = 0 # NOBLINK
                    else: # state == 2 (opening the eye)
                        blinkState.duration *= 2.0
                        blinkState.startTime = now
        if blinkState.state:
            n = (now - blinkState.startTime) / blinkState.duration
            if n > 1.0: n = 1.0
            if blinkState.state == 2: n = 1.0 - n
        else:
            n = 0.0

        return n

    def get_pupil_size(self, now):
        global pupilSizeInput
        return pupilSizeInput.get_size(now)

    def get_position(self, now):
        global eyePosInput
        return eyePosInput.get_position(now)

    # Return state for each of the eyes in a list
    def get_state(self, now):

        self.auto_blink(now)

        num = len(self.blinkState)

        result = []

        posX, posY = self.get_position(now)
        pupilSize = self.get_pupil_size(now)

        if TRACKING:
            n = 0.4 - posY / 60.0
            if   n < 0.0: n = 0.0
            elif n > 1.0: n = 1.0
            self.trackingPos = (self.trackingPos * 3.0 + n) * 0.25

        for i in range(num):
            n = self.get_eyelid_weight(now, i)
            state = EyeState()
            state.posX = posX
            state.posY = posY
            state.pupilSize = pupilSize
            state.upperEyelidWeight = self.trackingPos + (n * (1.0 - self.trackingPos))
            state.lowerEyelidWeight = (1.0 - self.trackingPos) + (n * self.trackingPos)
            result.append(state)

        return result


# Specific implementation of TwoEyesModel - it just introduces convergence
# assuming eyes will be drawn horisontally next one to another.
# Left eye has index 0 while right eye has index 1.
class TwoEyesModel(EyesModel):

    def __init__(self):
        super(TwoEyesModel, self).__init__(2)

    def get_state(self, now):
        states = super(TwoEyesModel, self).get_state(now)

        convergence = 2.0

        # Left eye
        states[0].posX += convergence
        # Right eye
        states[1].posX -= convergence

        return states

eyePosInput = AutonomousEyePositionInput()
pupilSizeInput = AutonomousPupilSizeInput()
#eyesModel = EyesModel()
eyesModel = TwoEyesModel()
#eyePosInput = JoystickEyePositionInput(adcValue, JOYSTICK_X_IN, JOYSTICK_Y_IN)

# Generate one frame of imagery

class Renderer:

    def __init__(self, model):
        self.model = model
        self.image = None
        self.condition = threading.Condition()
        self.trackingPos = 0.3

    def run(self):
        while True:
            self.frame()

    def frame(self):
        global leftEye, rightEye

        DISPLAY.loop_running()

        now = time.time()

        states = self.model.get_state(now)
        eyes = [leftEye, rightEye]

        for i in range(2):
          eye = eyes[i]
          state = states[i]
          eye.set_upper_lid_weight(state.upperEyelidWeight)
          eye.set_lower_lid_weight(state.lowerEyelidWeight)
          eye.set_pupil(state.posY, state.posX, state.pupilSize)
          eye.draw()

        img = pi3d.util.Screenshot.screenshot()

        # Make new image available to waiting threads
        with self.condition:
            self.image = img
            self.condition.notifyAll()

    # Wait until next image is rendered and return it
    def wait_image(self, last_image):
        with self.condition:
            while self.image is last_image:
                self.condition.wait()
            return self.image


def oledThread(renderer, oled, srcx):

    image = None
    while True:
        t0 = time.time()
        image = renderer.wait_image(image)
        t1 = time.time()
        oled.copy_image(image, 0, 0, srcx, 0)
        t2 = time.time()
        oled.flush()
        t3 = time.time()
#        print("%s : copy_image=%d, flush=%d" % (threading.current_thread(), (t2-t1)*1000, (t3-t2)*1000))
        print("%s : wait_image=%d, copy_image=%d, flush=%d" % ("x", (t1-t0)*1000, (t2-t1)*1000, (t3-t2)*1000))

# MAIN LOOP -- runs continuously -------------------------------------------

renderer = Renderer(eyesModel)

thread.start_new_thread(oledThread, (renderer, leftOLED, DISPLAY.width // 2 - eyePosition - OLED_WIDTH // 2))
thread.start_new_thread(oledThread, (renderer, rightOLED, DISPLAY.width // 2 + eyePosition - OLED_WIDTH // 2))

renderer.run()
