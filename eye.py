from xml.dom.minidom import parse
from gfxutil import *

# Represents the instant state of a single eye - pupil size, position
# as well as weight for both upper and lower eyelids
class EyeState:
    pupilSize = 0
    posX = 0
    posY = 0
    upperLidWeight = 0
    lowerLidWeight = 0

class Eyelid:
    def __init__(self, eyeRadius, lidMap, shader, lidOpenPts, lidClosedPts, lidEdgePts, posX = 0, posY = 0, flip = False):
        self.prevWeight = 0
        self.lidOpenPts = lidOpenPts
        self.lidClosedPts = lidClosedPts
        self.lidEdgePts = lidEdgePts
        self.flip = flip
        self.prevPts = pointsInterp(lidOpenPts, lidClosedPts, 0.5)
        self.regen = True

        # Eyelid meshes are likewise temporary; texture coordinates are
        # assigned here but geometry is dynamically regenerated in main loop.
        self.eyelid = meshInit(33, 5, False, 0, 0.5/lidMap.iy, True)
        self.eyelid.set_textures([lidMap])
        self.eyelid.set_shader(shader)

        self.eyelid.positionX(posX)
        self.eyelid.positionY(posY)
        self.eyelid.positionZ(-eyeRadius - 42)

        # Determine change in eyelid values needed to trigger geometry regen.
        # This is done a little differently than the pupils...instead of bounds,
        # the distance between the middle points of the open and closed eyelid
        # paths is evaluated, then similar 1/4 pixel threshold is determined.
        self.lidRegenThreshold = 0.0

        p1 = lidOpenPts[len(lidOpenPts) // 2]
        p2 = lidClosedPts[len(lidClosedPts) // 2]
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        d  = dx * dx + dy * dy
        if d > 0: self.lidRegenThreshold = 0.25 / math.sqrt(d)

    def set_weight(self, weight):
        if (self.regen or (abs(weight - self.prevWeight) >= self.lidRegenThreshold)):
            newLidPts = pointsInterp(self.lidOpenPts, self.lidClosedPts, weight)
            if weight > self.prevWeight:
                mesh = pointsMesh(self.lidEdgePts, self.prevPts, newLidPts, 5, 0, False, self.flip)
            else:
                mesh = pointsMesh(self.lidEdgePts, newLidPts, self.prevPts, 5, 0, False, self.flip)

            self.eyelid.re_init(pts = mesh)

            self.prevWeight = weight
            self.prevPts    = newLidPts
            self.regen = True
        else:
            self.regen = False

    def draw(self):
        self.eyelid.draw()

class Eye:
    def __init__(self, eyeRadius, posX = 0, posY = 0, flip = False):

        # offset/rotation of iris and sclera. 180 degree difference for left and right eye just so they don't look identical
        offset = 0 if flip else 0.5

        # Load SVG file, extract paths & convert to point lists --------------------

        # Thanks Glen Akins for the symmetrical-lidded cyclops eye SVG!
        # Iris & pupil have been scaled down slightly in this version to compensate
        # for how the WorldEye distorts things...looks OK on WorldEye now but might
        # seem small and silly if used with the regular OLED/TFT code.
        dom = parse("graphics/cyclops-eye.svg")
#        dom = parse("graphics/eye.svg")

        self.pupilMinPts       = getPoints(dom, "pupilMin"      , 32, True , True )
        self.pupilMaxPts       = getPoints(dom, "pupilMax"      , 32, True , True )
        self.irisPts           = getPoints(dom, "iris"          , 32, True , True )
        self.scleraFrontPts    = getPoints(dom, "scleraFront"   ,  0, False, False)
        self.scleraBackPts     = getPoints(dom, "scleraBack"    ,  0, False, False)
        self.upperLidClosedPts = getPoints(dom, "upperLidClosed", 33, False, True )
        self.upperLidOpenPts   = getPoints(dom, "upperLidOpen"  , 33, False, True )
        self.upperLidEdgePts   = getPoints(dom, "upperLidEdge"  , 33, False, False)
        self.lowerLidClosedPts = getPoints(dom, "lowerLidClosed", 33, False, False)
        self.lowerLidOpenPts   = getPoints(dom, "lowerLidOpen"  , 33, False, False)
        self.lowerLidEdgePts   = getPoints(dom, "lowerLidEdge"  , 33, False, False)

        # Transform point lists to eye dimensions
        vb = getViewBox(dom)
        scalePoints(self.pupilMinPts,       vb, eyeRadius)
        scalePoints(self.pupilMaxPts,       vb, eyeRadius)
        scalePoints(self.irisPts,           vb, eyeRadius)
        scalePoints(self.scleraFrontPts,    vb, eyeRadius)
        scalePoints(self.scleraBackPts,     vb, eyeRadius)
        scalePoints(self.upperLidClosedPts, vb, eyeRadius)
        scalePoints(self.upperLidOpenPts,   vb, eyeRadius)
        scalePoints(self.upperLidEdgePts,   vb, eyeRadius)
        scalePoints(self.lowerLidClosedPts, vb, eyeRadius)
        scalePoints(self.lowerLidOpenPts,   vb, eyeRadius)
        scalePoints(self.lowerLidEdgePts,   vb, eyeRadius)

        # Load texture maps --------------------------------------------------------
        irisMap   = pi3d.Texture("graphics/iris.jpg"  , mipmap=False, filter=pi3d.GL_LINEAR)
        scleraMap = pi3d.Texture("graphics/sclera.png", mipmap=False, filter=pi3d.GL_LINEAR, blend=True)
        lidMap    = pi3d.Texture("graphics/lid.png"   , mipmap=False, filter=pi3d.GL_LINEAR, blend=True)
        # U/V map may be useful for debugging texture placement; not normally used
        #uvMap     = pi3d.Texture("graphics/uv.png"    , mipmap=False, filter=pi3d.GL_LINEAR, blend=False, m_repeat=True)

        shader = pi3d.Shader("uv_light")

        # Regenerating flexible object geometry (such as eyelids during blinks, or
        # iris during pupil dilation) is CPU intensive, can noticably slow things
        # down, especially on single-core boards.  To reduce this load somewhat,
        # determine a size change threshold below which regeneration will not occur;
        # roughly equal to 1/2 pixel, since 2x2 area sampling is used.

        # Determine change in pupil size to trigger iris geometry regen
        self.irisRegenThreshold = 0.0
        a = pointsBounds(self.pupilMinPts) # Bounds of pupil at min size (in pixels)
        b = pointsBounds(self.pupilMaxPts) # " at max size
        maxDist = max(abs(a[0] - b[0]), abs(a[1] - b[1]), # Determine distance of max
                      abs(a[2] - b[2]), abs(a[3] - b[3])) # variance around each edge
        # maxDist is motion range in pixels as pupil scales between 0.0 and 1.0.
        # 1.0 / maxDist is one pixel's worth of scale range.  Need 1/4 that...
        if maxDist > 0: self.irisRegenThreshold = 0.25 / maxDist

        self.ulid = Eyelid(eyeRadius, lidMap, shader, self.upperLidOpenPts, self.upperLidClosedPts, self.upperLidEdgePts, posX, posY, flip)
        self.llid = Eyelid(eyeRadius, lidMap, shader, self.lowerLidOpenPts, self.lowerLidClosedPts, self.lowerLidEdgePts, posX, posY, flip)

        self.prevPupilScale  = -1.0 # Force regen on first frame

        # Generate initial iris mesh; vertex elements will get replaced on
        # a per-frame basis in the main loop, this just sets up textures, etc.
        self.iris = meshInit(32, 4, True, offset, 0.5/irisMap.iy, False)
        self.iris.set_textures([irisMap])
        self.iris.set_shader(shader)
        self.irisZ = zangle(self.irisPts, eyeRadius)[0] * 0.99 # Get iris Z depth, for later

        # Generate sclera for eye...start with a 2D shape for lathing...
        angle1 = zangle(self.scleraFrontPts, eyeRadius)[1] # Sclera front angle
        angle2 = zangle(self.scleraBackPts , eyeRadius)[1] # " back angle
        aRange = 180 - angle1 - angle2
        pts    = []
        for i in range(24):
            ca, sa = pi3d.Utility.from_polar((90 - angle1) - aRange * i / 23)
            pts.append((ca * eyeRadius, sa * eyeRadius))

        self.eyeball = pi3d.Lathe(path=pts, sides=64)
        self.eyeball.set_textures([scleraMap])
        self.eyeball.set_shader(shader)
        reAxis(self.eyeball, offset)

        self.eyeball.positionX(posX)
        self.eyeball.positionY(posY)
        self.iris.positionX(posX)
        self.iris.positionY(posY)


    def draw(self):
        self.iris.draw()
        self.eyeball.draw()
        self.ulid.draw()
        self.llid.draw()

    def set_pupil(self, x, y, scale):

        # Regenerate iris geometry only if size changed by >= 1/2 pixel
        if abs(scale - self.prevPupilScale) >= self.irisRegenThreshold:
            # Interpolate points between min and max pupil sizes
            interPupil = pointsInterp(self.pupilMinPts, self.pupilMaxPts, scale)
            # Generate mesh between interpolated pupil and iris bounds
            mesh = pointsMesh(None, interPupil, self.irisPts, 4, -self.irisZ, True)
            self.iris.re_init(pts=mesh)
            self.prevPupilScale = scale

        self.iris.rotateToX(x)
        self.iris.rotateToY(y)

        self.eyeball.rotateToX(x)
        self.eyeball.rotateToY(y)

    def set_upper_lid_weight(self, weight):
        self.ulid.set_weight(weight)

    def set_lower_lid_weight(self, weight):
        self.llid.set_weight(weight)

    # Set everything at once
    def set_state(self, state):
        self.ulid.set_weight(state.upperLidWeight)
        self.llid.set_weight(state.lowerLidWeight)
        self.set_pupil(state.posY, state.posX, state.pupilSize)
