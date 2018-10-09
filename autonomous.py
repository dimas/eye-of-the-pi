import random
import math

# Autonomous eye position
# The logic here is taken from the original code and just encapsulated in a class
class AutonomousEyePositionInput:
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


class AutonomousPupilSizeInput:
    def __init__(self):
        self.set_size(0.5)

    def set_size(self, size):
        self.last_size = size
        self.plan = []

    def get_size(self, now):
        last_size = self.last_size
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
