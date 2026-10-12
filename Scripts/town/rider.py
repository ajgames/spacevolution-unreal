"""The PWC-01 hover jet-ski: its hull and rider meshes, input, Blueprint and the game mode that spawns it.

Built to the spec sheet: 3.42 m long, 1.24 m wide, 1.15 m to the bars. A faceted carbon hull with gunmetal
armour panels, amber LED strips, four lift rings with turbine fans underneath, rear stabiliser fins, and a rider
in a black suit and helmet. Coordinates are metres in the body's frame: X forward, Y right, Z up, origin at the
middle of the physics box (AWaveRider::Body).
"""
import math

import unreal

from colony.geo import bake
from ship.geo import Part
from .geo import Builder, UVBuffers, capsule, limb, sphere, torus
from .util import EAL, ROOT, load_or_create, log

FOLDER = f"{ROOT}/Rider"
INPUT_FOLDER = f"{FOLDER}/Input"
VT = unreal.InputActionValueType

# Hull stations: (x, half width, keel z, deck z)
STATIONS = [(1.72, 0.03, -0.05, 0.03), (1.45, 0.30, -0.24, 0.13), (1.00, 0.52, -0.32, 0.24), (0.45, 0.60, -0.34, 0.28),
            (-0.20, 0.62, -0.34, 0.16), (-0.95, 0.60, -0.33, 0.16), (-1.50, 0.54, -0.30, 0.20), (-1.70, 0.48, -0.26, 0.22)]
THRUSTERS = [(0.95, -0.38), (0.95, 0.38), (-0.85, -0.38), (-0.85, 0.38)]   # AWaveRider::Thrusters, in metres
RING_Z = -0.34


def _at(x):
    """Hull half width, keel and deck height at x, interpolated between stations."""
    for (x0, *a), (x1, *b) in zip(STATIONS, STATIONS[1:]):
        if x1 <= x <= x0:
            t = (x0 - x) / (x0 - x1)
            return tuple(p + (q - p) * t for p, q in zip(a, b))
    return tuple(STATIONS[0][1:]) if x > STATIONS[0][0] else tuple(STATIONS[-1][1:])


def _section(x, hw, keel, deck):
    mid = (keel + deck) * 0.5
    right = [(0.45 * hw, keel + 0.04), (0.92 * hw, keel + 0.16), (hw, mid), (0.86 * hw, deck - 0.05), (0.55 * hw, deck)]
    left = [(-y, z) for y, z in reversed(right)]
    # Counter-clockwise seen from the bow: up the right side, over the deck, down the left.
    return [(x, y, z) for y, z in [(0.0, keel)] + right + [(0.0, deck + 0.04)] + left]


def _strip(b, slot, points, size=0.022):
    """Square-section strip along a polyline (an LED line)."""
    sections = []
    for i, p in enumerate(points):
        a, c = points[max(i - 1, 0)], points[min(i + 1, len(points) - 1)]
        d = tuple(q - r for q, r in zip(c, a))
        length = math.sqrt(sum(v * v for v in d))
        d = tuple(v / length for v in d)
        side = (-d[1], d[0], 0.0)
        sl = math.hypot(side[0], side[1]) or 1.0
        side = (side[0] / sl, side[1] / sl, 0.0)
        up = (d[1] * side[2] - d[2] * side[1], d[2] * side[0] - d[0] * side[2], d[0] * side[1] - d[1] * side[0])
        h = size * 0.5
        sections.append([tuple(p[k] + side[k] * su * h + up[k] * uu * h for k in range(3))
                         for su, uu in ((1, -1), (1, 1), (-1, 1), (-1, -1))])
    b.loft(slot, sections)


def hull():
    part = Part("SM_WaveRider_Hull")
    for slot in ("Carbon", "Gunmetal", "Trim", "Seat", "Visor", "Turbine", "LED", "ThrusterGlow"):
        part.slot(slot)
    b = Builder()
    b.loft("Carbon", [_section(x, hw, keel, deck) for x, hw, keel, deck in STATIONS][::-1])

    # Gunmetal armour panels over the upper flanks, standing just proud of the hull.
    for s in (-1.0, 1.0):
        sections = []
        for x in [1.30 - 0.25 * i for i in range(11)]:
            hw, keel, deck = _at(x)
            mid = (keel + deck) * 0.5
            pts = [(x, s * (hw + 0.012), mid + 0.02), (x, s * (0.88 * hw + 0.012), deck - 0.04),
                   (x, s * (0.84 * hw), deck - 0.06), (x, s * (0.97 * hw), mid + 0.02)]
            sections.append(pts if s > 0 else pts[::-1])
        b.loft("Gunmetal", sections[::-1])

    # Cowl over the bow, the windscreen, the seat.
    cowl = []
    for x, w, top in ((1.38, 0.10, 0.20), (1.10, 0.26, 0.34), (0.75, 0.38, 0.48), (0.40, 0.42, 0.56), (0.18, 0.40, 0.56)):
        base = _at(x)[2] - 0.02
        cowl.append([(x, 0.0, base), (x, w, base), (x, 0.72 * w, top - 0.07), (x, 0.0, top), (x, -0.72 * w, top - 0.07),
                     (x, -w, base)])
    b.loft("Gunmetal", cowl[::-1])
    b.loft("Visor", [[(x, 0.0, z0), (x, 0.30, z0), (x, 0.22, z1), (x, -0.22, z1), (x, -0.30, z0)]
                     for x, z0, z1 in ((0.20, 0.55, 0.72), (0.36, 0.53, 0.60))])
    seat = []
    for x, w, top in ((-0.05, 0.17, 0.45), (-0.40, 0.21, 0.43), (-0.90, 0.22, 0.41), (-1.30, 0.19, 0.40)):
        base = _at(x)[2] - 0.02
        seat.append([(x, 0.0, base), (x, w, base), (x, w, top - 0.06), (x, 0.6 * w, top), (x, -0.6 * w, top),
                     (x, -w, top - 0.06), (x, -w, base)])
    b.loft("Seat", seat[::-1])

    # Stabiliser fins at the stern, raked back.
    for s in (-1.0, 1.0):
        b.ribbon("Gunmetal", [(-1.30, s * 0.42, 0.20), (-1.60, s * 0.47, 0.62)], [(-1.74, s * 0.47, 0.20), (-1.80, s * 0.50, 0.62)])

    # LED strips: along the upper chine, a chevron down each flank, and the cowl's eyes.
    for s in (-1.0, 1.0):
        chine = []
        for x in [1.40 - 0.2 * i for i in range(15)]:
            hw, keel, deck = _at(x)
            chine.append((x, s * (0.86 * hw + 0.02), deck - 0.05))
        _strip(b, "LED", chine)
        pts = []
        for x, k in ((-1.0, 0.5), (0.0, 0.62), (0.85, 0.45)):
            hw, keel, deck = _at(x)
            pts.append((x, s * (hw + 0.018), keel + (deck - keel) * k))
        _strip(b, "LED", pts)
        _strip(b, "LED", [(1.22, s * 0.10, 0.30), (1.05, s * 0.22, 0.39), (0.85, s * 0.30, 0.44)], 0.026)
    # Intake grille and thrust nozzle at the stern.
    b.box("Trim", -1.73, -1.70, -0.30, 0.30, -0.18, 0.06)
    b.into(part)
    limb(part, "Gunmetal", (-1.65, 0.0, -0.12), (-1.86, 0.0, -0.12), 0.13, 0.10, steps=16)
    limb(part, "ThrusterGlow", (-1.86, 0.0, -0.12), (-1.87, 0.0, -0.12), 0.09, 0.09, steps=16)

    # Handlebars.
    limb(part, "Gunmetal", (0.30, 0.0, 0.52), (0.27, 0.0, 0.80), 0.04, 0.035)
    limb(part, "Trim", (0.27, -0.45, 0.80), (0.27, 0.45, 0.80), 0.02)
    for s in (-1.0, 1.0):
        limb(part, "Seat", (0.27, s * 0.33, 0.80), (0.27, s * 0.47, 0.80), 0.032)

    # Lift rings: housing, fan and the glowing ring underneath.
    for x, y in THRUSTERS:
        torus(part, "Gunmetal", (x, y, RING_Z + 0.02), 0.27, 0.055, 40, 8)
        torus(part, "ThrusterGlow", (x, y, RING_Z - 0.035), 0.25, 0.022, 40, 6)
        limb(part, "Turbine", (x, y, RING_Z + 0.04), (x, y, RING_Z - 0.01), 0.23, 0.23, steps=32)
        fan = Builder()
        for k in range(9):
            a = math.tau * k / 9
            c, s = math.cos(a), math.sin(a)
            poly = [(x + c * 0.04 - s * 0.02, y + s * 0.04 + c * 0.02), (x + c * 0.04 + s * 0.02, y + s * 0.04 - c * 0.02),
                    (x + c * 0.22 + s * 0.05, y + s * 0.22 - c * 0.05), (x + c * 0.22 - s * 0.01, y + s * 0.22 + c * 0.01)]
            fan.prism("Turbine", poly, RING_Z - 0.03, RING_Z - 0.015)
        fan.into(part)
        limb(part, "Gunmetal", (x, y, RING_Z - 0.04), (x, y, RING_Z + 0.03), 0.05, 0.05, steps=12)
    return part


def figure():
    """The rider: crouched over the bars, feet in the footwells, in a black suit and helmet."""
    part = Part("SM_WaveRider_Rider")
    part.slot("Suit")
    part.slot("Visor")
    capsule(part, "Suit", (-0.62, -0.13, 0.55), (-0.62, 0.13, 0.55), 0.13)
    capsule(part, "Suit", (-0.58, 0.0, 0.62), (-0.28, 0.0, 1.03), 0.17)
    capsule(part, "Suit", (-0.30, -0.19, 1.00), (-0.30, 0.19, 1.00), 0.09)
    limb(part, "Suit", (-0.24, 0.0, 1.08), (-0.18, 0.0, 1.17), 0.06)
    sphere(part, "Suit", (-0.13, 0.0, 1.27), 0.16, steps=16)
    sphere(part, "Visor", (-0.07, 0.0, 1.26), 0.15, steps=16, scale=(0.75, 0.95, 0.62))
    for s in (-1.0, 1.0):
        shoulder, elbow, hand = (-0.30, s * 0.22, 1.00), (0.0, s * 0.31, 0.86), (0.27, s * 0.40, 0.80)
        capsule(part, "Suit", shoulder, elbow, 0.068)
        capsule(part, "Suit", elbow, hand, 0.058)
        sphere(part, "Suit", hand, 0.06, steps=10)
        hip, knee, foot = (-0.62, s * 0.13, 0.55), (-0.22, s * 0.25, 0.63), (-0.45, s * 0.37, 0.24)
        capsule(part, "Suit", hip, knee, 0.095)
        capsule(part, "Suit", knee, foot, 0.075)
        capsule(part, "Suit", (-0.47, s * 0.37, 0.21), (-0.28, s * 0.37, 0.21), 0.06)
    return part


def spray_sheet():
    """Sheet of spray thrown off the left of the bow: back and out in an arc, widening and lifting as it goes.
    UV x runs across the sheet, UV y along it from the hull."""
    part = Part("SM_WaveRider_Spray")
    b = UVBuffers()
    rows, cols = 12, 5
    for i in range(rows + 1):
        v = i / rows
        x, y, z = -2.6 * v, -1.7 * v ** 0.8, 1.15 * math.sin(math.pi * v * 0.85)
        width = 0.12 + 0.9 * v
        for j in range(cols + 1):
            u = j / cols
            b.vert(((x - 0.3 * width * u) * 100.0, (y - 0.25 * width * u) * 100.0, (z + width * (u - 0.35)) * 100.0))
            b.uv0.append((u, v))
    for i in range(rows):
        for j in range(cols):
            a, c = i * (cols + 1) + j, (i + 1) * (cols + 1) + j
            b.quad(a, c, c + 1, a + 1)
    b.add_to(part, "Spray")
    return part


def wake_plume():
    """Rooster tail behind the hull: a short tube that kicks up and spreads, kept short and low so the chase
    camera never ends up inside it. UV x wraps round it, UV y runs along it."""
    part = Part("SM_WaveRider_Wake")
    b = UVBuffers()
    rows, sides = 12, 10
    for i in range(rows + 1):
        v = i / rows
        cx, cz = -2.6 * v, 1.1 * math.sin(math.pi * v * 0.9) ** 0.8 - 0.1
        radius = 0.07 + 0.34 * v
        for j in range(sides + 1):
            a = math.tau * j / sides
            b.vert((cx * 100.0, radius * math.cos(a) * 100.0, (cz + 0.6 * radius * math.sin(a)) * 100.0))
            b.uv0.append((j / sides, v))
    for i in range(rows):
        for j in range(sides):
            a, c = i * (sides + 1) + j, (i + 1) * (sides + 1) + j
            b.quad(a, c, c + 1, a + 1)
    b.add_to(part, "Wake")
    return part


# --- Input -------------------------------------------------------------------------------------------------------

def _action(name, value_type, description):
    ia = load_or_create(f"{INPUT_FOLDER}/{name}", unreal.InputAction, unreal.InputAction_Factory())
    ia.set_editor_property("value_type", value_type)
    ia.set_editor_property("action_description", description)
    if value_type != VT.BOOLEAN:
        ia.set_editor_property("accumulation_behavior", unreal.InputActionAccumulationBehavior.CUMULATIVE)
    EAL.save_loaded_asset(ia)
    return ia


def _key(name):
    k = unreal.Key()
    k.set_editor_property("key_name", name)
    return k


def _negate(imc):
    m = unreal.new_object(unreal.InputModifierNegate, outer=imc)
    for axis in ("x", "y", "z"):
        m.set_editor_property(axis, True)
    return m


def _scale(imc, x, y=None):
    m = unreal.new_object(unreal.InputModifierScalar, outer=imc)
    m.set_editor_property("scalar", unreal.Vector(x, x if y is None else y, 1.0))
    return m


def _dead_zone(imc):
    m = unreal.new_object(unreal.InputModifierDeadZone, outer=imc)
    m.set_editor_property("lower_threshold", 0.15)
    return m


def _per_second(imc):
    return unreal.new_object(unreal.InputModifierScaleByDeltaTime, outer=imc)


def _map(action, key, modifiers=()):
    return unreal.EnhancedActionKeyMapping(action=action, key=_key(key), modifiers=list(modifiers))


def build_input():
    throttle = _action("IA_RiderThrottle", VT.AXIS1D, "Throttle (+) and brake/reverse (-)")
    steer = _action("IA_RiderSteer", VT.AXIS1D, "Steer right (+) and left (-)")
    pitch = _action("IA_RiderPitch", VT.AXIS1D, "In the air: nose down (+) and up (-)")
    look = _action("IA_RiderLook", VT.AXIS2D, "Orbit the camera, degrees")
    jump = _action("IA_RiderJump", VT.BOOLEAN, "Jump; hold in the air to burst")
    boost = _action("IA_RiderBoost", VT.BOOLEAN, "Boost")
    reset = _action("IA_RiderReset", VT.BOOLEAN, "Put the rider back upright")

    imc = load_or_create(f"{INPUT_FOLDER}/IMC_WaveRider", unreal.InputMappingContext,
                         unreal.InputMappingContext_Factory())
    mappings = [
        _map(throttle, "W"), _map(throttle, "S", [_negate(imc)]),
        _map(throttle, "Gamepad_RightTriggerAxis"), _map(throttle, "Gamepad_LeftTriggerAxis", [_negate(imc)]),
        _map(steer, "D"), _map(steer, "A", [_negate(imc)]), _map(steer, "Gamepad_LeftX", [_dead_zone(imc)]),
        _map(pitch, "W"), _map(pitch, "S", [_negate(imc)]), _map(pitch, "Gamepad_LeftY", [_dead_zone(imc)]),
        # Mouse counts become degrees; the stick becomes degrees per second.
        _map(look, "Mouse2D", [_scale(imc, 0.18)]),
        _map(look, "Gamepad_Right2D", [_dead_zone(imc), _per_second(imc), _scale(imc, 140.0, 90.0)]),
        _map(jump, "SpaceBar"), _map(jump, "Gamepad_FaceButton_Bottom"),
        _map(boost, "LeftShift"), _map(boost, "Gamepad_FaceButton_Left"), _map(boost, "Gamepad_RightShoulder"),
        _map(reset, "R"), _map(reset, "Gamepad_FaceButton_Top"),
    ]
    imc.set_editor_property("default_key_mappings", unreal.InputMappingContextMappingData(mappings=mappings))
    imc.set_editor_property("context_description", "Wave rider")
    EAL.save_loaded_asset(imc)
    return {"rider_mapping_context": imc, "throttle_action": throttle, "steer_action": steer, "pitch_action": pitch,
            "look_action": look, "jump_action": jump, "boost_action": boost, "reset_action": reset}


def _blueprint(path, parent, defaults):
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", parent)
    bp = load_or_create(path, unreal.Blueprint, factory)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    cdo = unreal.get_default_object(bp.generated_class())
    for key, value in defaults.items():
        cdo.set_editor_property(key, value)
    # Compile again: spawned instances only copy defaults the compiler saw differ from the parent class.
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    EAL.save_loaded_asset(bp)
    return bp


def build(materials):
    """Bakes the meshes, makes the input assets, BP_WaveRider and BP_WaveRiderGameMode; returns the game mode."""
    hull_mesh = bake(hull(), f"{FOLDER}/Meshes", materials, collision=False, nanite=False, smooth_angle=14.0)
    rider_mesh = bake(figure(), f"{FOLDER}/Meshes", materials, collision=False, nanite=False, smooth_angle=60.0)
    spray = bake(spray_sheet(), f"{FOLDER}/Meshes", materials, collision=False, nanite=False, smooth_angle=80.0,
                 box_uvs=False)
    wake = bake(wake_plume(), f"{FOLDER}/Meshes", materials, collision=False, nanite=False, smooth_angle=80.0,
                box_uvs=False)
    rider = _blueprint(f"{FOLDER}/BP_WaveRider", unreal.WaveRider, {
        "hull_mesh": hull_mesh, "rider_mesh": rider_mesh, "spray_mesh": spray, "wake_mesh": wake, **build_input()})
    controller = EAL.load_asset("/Game/Player/BP_CrewPlayerController")
    defaults = {"default_pawn_class": rider.generated_class(), "hud_class": unreal.WaveRiderHUD}
    if controller:
        defaults["player_controller_class"] = controller.generated_class()
    mode = _blueprint(f"{FOLDER}/BP_WaveRiderGameMode", unreal.SpacevolutionGameMode, defaults)
    log("wave rider, input and game mode ready")
    return {"rider": rider, "mode": mode, "hull": hull_mesh}
