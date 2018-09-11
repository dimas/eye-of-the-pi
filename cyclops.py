#!/usr/bin/python

# This is a PARED-DOWN version of eyes.py designed for the Gakken
# WorldEye display.  It renders a single eye (centered on screen) and
# does NOT require the OLED or TFT displays...doesn't even require the
# Snake Eyes Bonnet if you just have it running in autonomous mode.
# Code is just as in-progress as eyes.py and could use some work.

import math
import pi3d
import random
import thread
import time
import RPi.GPIO as GPIO

import SSD1351
import eye

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
BLINK_PIN       = 23    # GPIO pin for blink button
AUTOBLINK       = True  # If True, eye blinks autonomously

oled = SSD1351.SSD1351()

# GPIO initialization ------------------------------------------------------

GPIO.setmode(GPIO.BCM)
if BLINK_PIN >= 0: GPIO.setup(BLINK_PIN , GPIO.IN, pull_up_down=GPIO.PUD_UP)


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
# no slowdown).  Since there's a finite limit to the animation frame rate,
# we intentionally use a slower data rate (rather than sleep()) to lessen
# the impact of this thread.  data_rate of 250 w/4 ADC channels provides
# at most 75 Hz update from the ADC, which is plenty for this task.
def adcThread(adc, dest):
	while True:
		for i in range(len(dest)):
			# ADC input range is +- 4.096V
			# ADC output is -2048 to +2047
			# Analog inputs will be 0 to ~3.3V,
			# thus 0 to 1649-ish.  Read & clip:
			n = adc.read_adc(i, gain=1, data_rate=250)
			if   n <    0: n =    0
			elif n > 1649: n = 1649
			dest[i] = n / 1649.0 # Store as 0.0 to 1.0

# Start ADC sampling thread if needed:
if adc:
	thread.start_new_thread(adcThread, (adc, adcValue))


# Set up display and initialize pi3d ---------------------------------------

DISPLAY = pi3d.Display.create(samples=4, w=128, h=128)

DISPLAY.set_background(0, 0, 0, 1) # r,g,b,alpha

# eyeRadius is the size, in pixels, at which the whole eye will be rendered.
if DISPLAY.width <= (DISPLAY.height * 2):
	# For WorldEye, eye size is -almost- full screen height
	eyeRadius   = DISPLAY.height / 2.1
else:
	eyeRadius   = DISPLAY.height * 2 / 5

eye = eye.Eye(eyeRadius);

# A 2D camera is used, mostly to allow for pixel-accurate eye placement,
# but also because perspective isn't really helpful or needed here, and
# also this allows eyelids to be handled somewhat easily as 2D planes.
# Line of sight is down Z axis, allowing conventional X/Y cartesion
# coords for 2D positions.
cam    = pi3d.Camera(is_3d=False, at=(0,0,0), eye=(0,0,-1000))
light  = pi3d.Light(lightpos=(0, -500, -500), lightamb=(0.2, 0.2, 0.2))


# Init global stuff --------------------------------------------------------

mykeys = pi3d.Keyboard() # For capturing key presses

startX       = random.uniform(-30.0, 30.0)
n            = math.sqrt(900.0 - startX * startX)
startY       = random.uniform(-n, n)
destX        = startX
destY        = startY
curX         = startX
curY         = startY
moveDuration = random.uniform(0.075, 0.175)
holdDuration = random.uniform(0.1, 1.1)
startTime    = 0.0
isMoving     = False

beginningTime = time.time()

currentPupilScale  =  0.5
prevUpperLidWeight = 0.5
prevLowerLidWeight = 0.5

timeOfLastBlink = 0.0
timeToNextBlink = 1.0
blinkState      = 0
blinkDuration   = 0.1
blinkStartTime  = 0

trackingPos = 0.3

class Animator:

    def __init__(self):
        self.frames = 0

    def frame(self, p):

	global startX, startY, destX, destY, curX, curY
	global moveDuration, holdDuration, startTime, isMoving
	global prevPupilScale
	global irisRegenThreshold, upperLidRegenThreshold, lowerLidRegenThreshold
	global luRegen, llRegen, ruRegen, rlRegen
	global timeOfLastBlink, timeToNextBlink
	global blinkState
	global blinkDuration
	global blinkStartTime
	global trackingPos

	DISPLAY.loop_running()

	now = time.time()
	dt  = now - startTime

	if(now > beginningTime):
		print(self.frames/(now-beginningTime))

	if JOYSTICK_X_IN >= 0 and JOYSTICK_Y_IN >= 0:
		# Eye position from analog inputs
		curX = adcValue[JOYSTICK_X_IN]
		curY = adcValue[JOYSTICK_Y_IN]
		if JOYSTICK_X_FLIP: curX = 1.0 - curX
		if JOYSTICK_Y_FLIP: curY = 1.0 - curY
		curX = -30.0 + curX * 60.0
		curY = -30.0 + curY * 60.0
	else :
		# Autonomous eye position
		if isMoving == True:
			if dt <= moveDuration:
				scale        = (now - startTime) / moveDuration
				# Ease in/out curve: 3*t^2-2*t^3
				scale = 3.0 * scale * scale - 2.0 * scale * scale * scale
				curX         = startX + (destX - startX) * scale
				curY         = startY + (destY - startY) * scale
			else:
				startX       = destX
				startY       = destY
				curX         = destX
				curY         = destY
				holdDuration = random.uniform(0.15, 1.7)
				startTime    = now
				isMoving     = False
		else:
			if dt >= holdDuration:
				destX        = random.uniform(-30.0, 30.0)
				n            = math.sqrt(900.0 - destX * destX)
				destY        = random.uniform(-n, n)
				# Movement is slower in this version because
				# the WorldEye display is big and the eye
				# should have some 'mass' to it.
				moveDuration = random.uniform(0.12, 0.35)
				startTime    = now
				isMoving     = True

        eye.set_pupil(curY, curX, p)

	# Eyelid WIP

	if AUTOBLINK and (now - timeOfLastBlink) >= timeToNextBlink:
		# Similar to movement, eye blinks are slower in this version
		timeOfLastBlink = now
		duration        = random.uniform(0.06, 0.12)
		if blinkState != 1:
			blinkState     = 1 # ENBLINK
			blinkStartTime = now
			blinkDuration  = duration
		timeToNextBlink = duration * 3 + random.uniform(0.0, 4.0)

	if blinkState: # Eye currently winking/blinking?
		# Check if blink time has elapsed...
		if (now - blinkStartTime) >= blinkDuration:
			# Yes...increment blink state, unless...
			if (blinkState == 1 and # Enblinking and...
			    (BLINK_PIN >= 0 and    # blink pin held
			     GPIO.input(BLINK_PIN) == GPIO.LOW)):
				# Don't advance yet; eye is held closed
				pass
			else:
				blinkState += 1
				if blinkState > 2:
					blinkState = 0 # NOBLINK
				else:
					blinkDuration *= 2.0
					blinkStartTime = now
	else:
		if BLINK_PIN >= 0 and GPIO.input(BLINK_PIN) == GPIO.LOW:
			blinkState     = 1 # ENBLINK
			blinkStartTime = now
			blinkDuration  = random.uniform(0.035, 0.06)

	if TRACKING:
		# 0 = fully up, 1 = fully down
		n = 0.5 - curY / 70.0
		if   n < 0.0: n = 0.0
		elif n > 1.0: n = 1.0
		trackingPos = (trackingPos * 3.0 + n) * 0.25



	if blinkState:
		n = (now - blinkStartTime) / blinkDuration
		if n > 1.0: n = 1.0
		if blinkState == 2: n = 1.0 - n
	else:
		n = 0.0

	newUpperLidWeight = trackingPos + (n * (1.0 - trackingPos))
	newLowerLidWeight = (1.0 - trackingPos) + (n * trackingPos)

        eye.set_upper_lid_weight(newUpperLidWeight)
        eye.set_lower_lid_weight(newLowerLidWeight)

        eye.draw()

        image = pi3d.util.Screenshot.screenshot()
        oled.copy_image(image)
        oled.flush()

	self.frames += 1

	k = mykeys.read()
	if k==27:
		mykeys.close()
		DISPLAY.stop()
		exit(0)

a = Animator()

def split( # Recursive simulated pupil response when no analog sensor
  startValue, # Pupil scale starting value (0.0 to 1.0)
  endValue,   # Pupil scale ending value (")
  duration,   # Start-to-end time, floating-point seconds
  range):     # +/- random pupil scale at midpoint
	startTime = time.time()
	if range >= 0.125: # Limit subdvision count, because recursion
		duration *= 0.5 # Split time & range in half for subdivision,
		range    *= 0.5 # then pick random center point within range:
		midValue  = ((startValue + endValue - range) * 0.5 +
		             random.uniform(0.0, range))
		split(startValue, midValue, duration, range)
		split(midValue  , endValue, duration, range)
	else: # No more subdivisons, do iris motion...
		dv = endValue - startValue
		while True:
			dt = time.time() - startTime
			if dt >= duration: break
			v = startValue + dv * dt / duration
			if   v < PUPIL_MIN: v = PUPIL_MIN
			elif v > PUPIL_MAX: v = PUPIL_MAX
			a.frame(v) # Draw frame w/interim pupil scale value


# MAIN LOOP -- runs continuously -------------------------------------------

while True:

	if PUPIL_IN >= 0: # Pupil scale from sensor
		v = adcValue[PUPIL_IN]
		if PUPIL_IN_FLIP: v = 1.0 - v
		# If you need to calibrate PUPIL_MIN and MAX,
		# add a 'print v' here for testing.
		if   v < PUPIL_MIN: v = PUPIL_MIN
		elif v > PUPIL_MAX: v = PUPIL_MAX
		# Scale to 0.0 to 1.0:
		v = (v - PUPIL_MIN) / (PUPIL_MAX - PUPIL_MIN)
		if PUPIL_SMOOTH > 0:
			v = ((currentPupilScale * (PUPIL_SMOOTH - 1) + v) /
			     PUPIL_SMOOTH)
		a.frame(v)
	else: # Fractal auto pupil scale
		v = random.random()
		split(currentPupilScale, v, 4.0, 1.0)
	currentPupilScale = v
