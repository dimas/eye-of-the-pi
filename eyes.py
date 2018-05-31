#!/usr/bin/python

# This is a hasty port of the Teensy eyes code to Python...all kludgey with
# an embarrassing number of globals in the frame() function and stuff.
# Needed to get SOMETHING working, can focus on improvements next.

import Adafruit_ADS1x15
import argparse
import math
import pi3d
import random
import thread
import time
import RPi.GPIO as GPIO
from svg.path import Path, parse_path
from xml.dom.minidom import parse
from gfxutil import *

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
WINK_L_PIN      = 22    # GPIO pin for LEFT eye wink button
BLINK_PIN       = 23    # GPIO pin for blink button (BOTH eyes)
WINK_R_PIN      = 24    # GPIO pin for RIGHT eye wink button
AUTOBLINK       = True  # If True, eyes blink autonomously


# GPIO initialization ------------------------------------------------------

GPIO.setmode(GPIO.BCM)
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

DISPLAY = pi3d.Display.create(samples=4, w=128*5, h=128)
# make background green while debugging and refactoring so it is easier to see individual eye pieces
DISPLAY.set_background(0, 0.5, 0, 1) # r,g,b,alpha

# eyeRadius is the size, in pixels, at which the whole eye will be rendered
# onscreen.  eyePosition, also pixels, is the offset (left or right) from
# the center point of the screen to the center of each eye.  This geometry
# is explained more in-depth in fbx2.c.
eyePosition = DISPLAY.width / 4
eyeRadius   = 128  # Default; use 240 for IPS screens

parser = argparse.ArgumentParser()
parser.add_argument("--radius", type=int)
args = parser.parse_args()
if args.radius:
	eyeRadius = args.radius

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

frames        = 0
beginningTime = time.time()

currentPupilScale       =  0.5
prevPupilScale          = -1.0 # Force regen on first frame
prevLeftUpperLidWeight  = 0.5
prevLeftLowerLidWeight  = 0.5
prevRightUpperLidWeight = 0.5
prevRightLowerLidWeight = 0.5

timeOfLastBlink = 0.0
timeToNextBlink = 1.0
# These are per-eye (left, right) to allow winking:
blinkStateLeft      = 0 # NOBLINK
blinkStateRight     = 0
blinkDurationLeft   = 0.1
blinkDurationRight  = 0.1
blinkStartTimeLeft  = 0
blinkStartTimeRight = 0

trackingPos = 0.3

# Generate one frame of imagery
def frame(p):

	global startX, startY, destX, destY, curX, curY
	global moveDuration, holdDuration, startTime, isMoving
	global frames
	global leftEye, rightEye
	global prevPupilScale
	global timeOfLastBlink, timeToNextBlink
	global blinkStateLeft, blinkStateRight
	global blinkDurationLeft, blinkDurationRight
	global blinkStartTimeLeft, blinkStartTimeRight
	global trackingPos

	DISPLAY.loop_running()

	now = time.time()
	dt  = now - startTime

	frames += 1
#	if(now > beginningTime):
#		print(frames/(now-beginningTime))

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
				holdDuration = random.uniform(0.1, 1.1)
				startTime    = now
				isMoving     = False
		else:
			if dt >= holdDuration:
				destX        = random.uniform(-30.0, 30.0)
				n            = math.sqrt(900.0 - destX * destX)
				destY        = random.uniform(-n, n)
				moveDuration = random.uniform(0.075, 0.175)
				startTime    = now
				isMoving     = True

	# Eyelid WIP

	if AUTOBLINK and (now - timeOfLastBlink) >= timeToNextBlink:
		timeOfLastBlink = now
		duration        = random.uniform(0.035, 0.06)
		if blinkStateLeft != 1:
			blinkStateLeft     = 1 # ENBLINK
			blinkStartTimeLeft = now
			blinkDurationLeft  = duration
		if blinkStateRight != 1:
			blinkStateRight     = 1 # ENBLINK
			blinkStartTimeRight = now
			blinkDurationRight  = duration
		timeToNextBlink = duration * 3 + random.uniform(0.0, 4.0)

	if blinkStateLeft: # Left eye currently winking/blinking?
		# Check if blink time has elapsed...
		if (now - blinkStartTimeLeft) >= blinkDurationLeft:
			# Yes...increment blink state, unless...
			if (blinkStateLeft == 1 and # Enblinking and...
			    ((BLINK_PIN >= 0 and    # blink pin held, or...
			      GPIO.input(BLINK_PIN) == GPIO.LOW) or
			    (WINK_L_PIN >= 0 and    # wink pin held
			      GPIO.input(WINK_L_PIN) == GPIO.LOW))):
				# Don't advance yet; eye is held closed
				pass
			else:
				blinkStateLeft += 1
				if blinkStateLeft > 2:
					blinkStateLeft = 0 # NOBLINK
				else:
					blinkDurationLeft *= 2.0
					blinkStartTimeLeft = now
	else:
		if WINK_L_PIN >= 0 and GPIO.input(WINK_L_PIN) == GPIO.LOW:
			blinkStateLeft     = 1 # ENBLINK
			blinkStartTimeLeft = now
			blinkDurationLeft  = random.uniform(0.035, 0.06)

	if blinkStateRight: # Right eye currently winking/blinking?
		# Check if blink time has elapsed...
		if (now - blinkStartTimeRight) >= blinkDurationRight:
			# Yes...increment blink state, unless...
			if (blinkStateRight == 1 and # Enblinking and...
			    ((BLINK_PIN >= 0 and    # blink pin held, or...
			      GPIO.input(BLINK_PIN) == GPIO.LOW) or
			    (WINK_R_PIN >= 0 and    # wink pin held
			      GPIO.input(WINK_R_PIN) == GPIO.LOW))):
				# Don't advance yet; eye is held closed
				pass
			else:
				blinkStateRight += 1
				if blinkStateRight > 2:
					blinkStateRight = 0 # NOBLINK
				else:
					blinkDurationRight *= 2.0
					blinkStartTimeRight = now
	else:
		if WINK_R_PIN >= 0 and GPIO.input(WINK_R_PIN) == GPIO.LOW:
			blinkStateRight     = 1 # ENBLINK
			blinkStartTimeRight = now
			blinkDurationRight  = random.uniform(0.035, 0.06)

	if BLINK_PIN >= 0 and GPIO.input(BLINK_PIN) == GPIO.LOW:
		duration = random.uniform(0.035, 0.06)
		if blinkStateLeft == 0:
			blinkStateLeft     = 1
			blinkStartTimeLeft = now
			blinkDurationLeft  = duration
		if blinkStateRight == 0:
			blinkStateRight     = 1
			blinkStartTimeRight = now
			blinkDurationRight  = duration

	if TRACKING:
		n = 0.4 - curY / 60.0
		if   n < 0.0: n = 0.0
		elif n > 1.0: n = 1.0
		trackingPos = (trackingPos * 3.0 + n) * 0.25

	if blinkStateLeft:
		n = (now - blinkStartTimeLeft) / blinkDurationLeft
		if n > 1.0: n = 1.0
		if blinkStateLeft == 2: n = 1.0 - n
	else:
		n = 0.0

        leftEye.set_upper_lid_weight(trackingPos + (n * (1.0 - trackingPos)))
        leftEye.set_lower_lid_weight((1.0 - trackingPos) + (n * trackingPos))

	if blinkStateRight:
		n = (now - blinkStartTimeRight) / blinkDurationRight
		if n > 1.0: n = 1.0
		if blinkStateRight == 2: n = 1.0 - n
	else:
		n = 0.0

        rightEye.set_upper_lid_weight(trackingPos + (n * (1.0 - trackingPos)))
        rightEye.set_lower_lid_weight((1.0 - trackingPos) + (n * trackingPos))

	convergence = 2.0

	# Right eye (on screen left)

        rightEye.set_pupil(curY, curX - convergence, p)

        rightEye.draw()

	# Left eye (on screen right)

        leftEye.set_pupil(curY, curX + convergence, p)
        leftEye.draw()

	k = mykeys.read()
	if k==27:
		mykeys.close()
		DISPLAY.stop()
		exit(0)


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
			frame(v) # Draw frame w/interim pupil scale value


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
		frame(v)
	else: # Fractal auto pupil scale
		v = random.random()
		split(currentPupilScale, v, 4.0, 1.0)
	currentPupilScale = v
