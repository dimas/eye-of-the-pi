import random

# Represents the instant state of an eye - pupil size, position
# as well as weight for both upper and lower eyelids
class EyeState:
    pupilSize = 0
    posX = 0
    posY = 0
    upperLidWeight = 0
    lowerLidWeight = 0

# Model representing a blink state of an eye.
# It performs smooth transition between open an closed state being driven by methods
#   start_blink / complete_blink
#   start_open / start_close
# In the end it just calculates current eyelid "weight" where 0.0 means fully open
# and 1.0 means fully closed. 
class BlinkStateModel:
    # 0 = open, 1 = blinking/closing/closed, 2 = opening
    state = 0
    # When the closing move started and how much time should it take (0 = instantly)
    closeStart = 0
    closeDuration = 0
    # When the opening move started and how much time should it take (0 = instantly)
    openStart = 0
    openDuration = 0
    # Should the eye stay closed when closing move finishes. If not, it will transition to opening move
    keepClosed = False

    # Begins blinking movement (close and open the eye once).
    # Note, that after closing the the eye it will stay closed until complete_blink() is called.
    # There is no need to wait until the eye closes fully before calling complete_blink() - it can be called
    # immediately after start_blink() and the eye will still perform the full close/open motion.
    # Also note that start_blink() only does anything if the eye is currently fully open and is ignored otherwise.
    def start_blink(self, now, closeDuration, openDuration):
        if self.state != 0:
            return
        self.state = 1 # ENBLINK
        self.closeStart = now
        self.closeDuration = closeDuration
        # Followed by open no delay
        self.openStart = now + closeDuration
        self.openDuration = openDuration
        # ... but only if complete_blink() is called in time
        self.keepClosed = True
        self.advance(now)

    # Finish blinking movement and open the eye.
    # This method does not actually start the movement but just "allows" it instead.
    # If the eye is in the middle of the closing movement because of start_blink(),
    # then calling this method does not immediately open the eye but will let it finish
    # the closing movement first.
    def complete_blink(self, now):
        if self.openStart < now:
            self.openStart = now
        self.keepClosed = False
        self.advance(now)
   
    # Begins opening movement.
    # Note that the movement overrides any other movement (opening or closing) if it is in progress.
    # The duration passed treated as desired duration of the full swing. So if the eye
    # is partially closed already (state != 0), duration and start time will be adjusted accordingly
    # to maintain the speed that full swing would require for target duration.
    def open(self, now, duration):
        n = self.get_eyelid_weight(now)
        self.state = 2
        self.openStart = now - duration * (1.0 - n)
        self.openDuration = duration
        self.keepClosed = False
        self.advance(now)

#        print("self.state=%d, self.startTime=%f, self.openDuration=%f, SUM=%f" % (self.state, self.startTime, self.openDuration, self.startTime+self.openDuration))

    # Begins closing movement.
    # Note that the movement overrides any other movement (opening or closing) if it is in progress.
    # The duration passed treated as desired duration of the full swing. So if the eye
    # is partially closed already (state != 0), duration and start time will be adjusted accordingly
    # to maintain the speed that full swing would require for target duration.
    # The eye will remain closed until a call to start_open()
    def close(self, now, duration):
        n = self.get_eyelid_weight(now)
        self.state = 1
        self.closeStart = now - duration * (1.0 - n)
        self.closeDuration = duration
        self.keepClosed = True
        self.advance(now)

    # Do state transitions if necessary
    def advance(self, now):
        if self.state == 1: # Eye currently winking/blinking?
            if self.closeStart + self.closeDuration <= now and not self.keepClosed:
                self.state  = 2

        if self.state == 2: # Eye currently opening
            if self.openStart + self.openDuration <= now:
                self.state  = 0

    # Return eyelid weight for the current blink state ranging from 0.0 (fully open) to 1.0 (fully closed).
    def get_eyelid_weight(self, now):

        # Do state transitions if necessary

        self.advance(now)

        # Now figure out progress in the current state

        if self.state == 1:
            passed = now - self.closeStart
            if self.closeDuration == 0 or passed >= self.closeDuration:
                return 1.0
            else:
                return passed / self.closeDuration

        elif self.state == 2:
            passed = now - self.openStart
            if self.openDuration == 0 or passed >= self.openDuration:
                return 0.0
            else:
                return 1.0 - passed / self.openDuration

        else:
            return 0.0

# All-eye selector for EyesModel's close_eye / open_eye operations.
# To act on all eyes we need to pass None there but it is not very readable,
# so just create an alias for that
ALL = None

# Eyes model - provides instant state of the eyes to the rendering engine
# as well as methods that allow manipulating that state to the animation/control code.
# For example control code can request a certain eye to open, close or blink and the model will
# perform a smooth transition from open to closed state etc.
# Model also implements automatic blinking (when enabled)
class EyesModel:

    def __init__(self, num):
        self.autoblink = False
        self.timeOfNextBlink = 0
        self.blinkState = [BlinkStateModel()] * num
        self.trackingPos = 0.3
        self.posX = 0
        self.posY = 0
        self.pupilSize = 0

    def random_blink_duration(self):
        return random.uniform(0.035, 0.06)

    def enable_autoblink(self, now):
        self.autoblink = True
        self.timeOfNextBlink = now + random.uniform(0.0, 4.0)

    def disable_autoblink(self):
        self.autoblink = False

    # Begin blinking movement (close and open an eye once).
    # 'index' selects an eye to perform action on, ALL can be passed to perform it on all the eyes at the same time
    # For details see matching method in BlinkStateModel
    def start_blink(self, index, now, closeDuration = None, openDuration = None):
        if closeDuration is None:
            closeDuration = self.random_blink_duration()
        if openDuration is None:
            openDuration = 2 * closeDuration

        if index is ALL:
            for i in range(len(self.blinkState)):
                self.start_blink(i, now, closeDuration, openDuration)
        else:
            self.blinkState[index].start_blink(now, closeDuration, openDuration)


    # Finish blinking movement and open an eye.
    # 'index' selects an eye to perform action on, ALL can be passed to perform it on all the eyes at the same time.
    # For details see matching method in BlinkStateModel.
    def complete_blink(self, index, now):
        if index is ALL:
            for i in range(len(self.blinkState)):
                self.complete_blink(i, now)
        else:
            self.blinkState[index].complete_blink(now)


    # Close an eye.
    # 'index' selects an eye to perform action on, ALL can be passed to perform it on all the eyes at the same time.
    # For details see matching method in BlinkStateModel.
    def close_eye(self, index, now, duration = None):
        if duration is None:
            duration = self.random_blink_duration()

        if index is ALL:
            for i in range(len(self.blinkState)):
                self.close_eye(i, now, duration)
        else:
            self.blinkState[index].close(now, duration)

    # Open an eye.
    # For details see matching method in BlinkStateModel.
    # 'index' selects an eye to perform action on, ALL can be passed to perform it on all the eyes at the same time.
    def open_eye(self, index, now, duration = None):
        if duration is None:
            duration = self.random_blink_duration()

        if index is ALL:
            for i in range(len(self.blinkState)):
                self.open_eye(i, now, duration)
        else:
             self.blinkState[index].open(now, duration)

    def auto_blink(self, now):
        if self.autoblink and now >= self.timeOfNextBlink:
            closeDuration  = self.random_blink_duration()
            openDuration   = closeDuration * 2.0
            for blinkState in self.blinkState:
                blinkState.start_blink(now, closeDuration, openDuration)
                blinkState.complete_blink(now)
            self.timeOfNextBlink = now + closeDuration + openDuration + random.uniform(0.0, 4.0)

    def set_pupil_size(self, size):
        self.pupilSize = size

    def set_position(self, x, y):
        self.posX = x
        self.posY = y

    # Return state for each of the eyes in a list
    def get_state(self, now):

        self.auto_blink(now)

        num = len(self.blinkState)

        result = []

#        self.trackingPos = 1 if TRACKING:
#            n = 0.4 - self.posY / 60.0
#            if   n < 0.0: n = 0.0
#            elif n > 1.0: n = 1.0
#            self.trackingPos = (self.trackingPos * 3.0 + n) * 0.25

        for i in range(num):
            n = self.blinkState[i].get_eyelid_weight(now)
            state = EyeState()
            state.posX = self.posX
            state.posY = self.posY
            state.pupilSize = self.pupilSize
            state.upperLidWeight = self.trackingPos + (n * (1.0 - self.trackingPos))
            state.lowerLidWeight = (1.0 - self.trackingPos) + (n * self.trackingPos)
            result.append(state)

        return result


# Specific implementation of EyesModel for two eyes - it just introduces convergence
# assuming eyes will be drawn horisontally, one next to another.
# Left eye has index 0 while right eye has index 1.
class TwoEyesModel(EyesModel):

    def __init__(self):
        EyesModel.__init__(self, 2)

    def get_state(self, now):
        states = EyesModel.get_state(self, now)

        convergence = 2.0

        # Left eye
        states[0].posX += convergence
        # Right eye
        states[1].posX -= convergence

        return states

