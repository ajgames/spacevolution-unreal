"""
Builds the "orbital porthole" scene: a bright white station module whose back
wall has a rounded-rect bay with a large circular window looking down on a
cloud-covered planet, with a moon hanging above the horizon.

Run inside Unreal Editor 5.8 (needs Python Editor Script Plugin + Geometry Script):
    Output Log -> switch the input to "Python" ->  py "<full path to this file>"
or  File -> Execute Python Script...

Safe to re-run: it reloads the level, deletes everything in the OrbitalWindow
outliner folder and rebuilds it. Tweak the constants below and run again.
"""
import math
import random
import traceback

import unreal

# --------------------------------------------------------------------------
# Tunables
# --------------------------------------------------------------------------
LEVEL_PATH = "/Game/OrbitalWindow/Maps/OrbitalWindow"
ASSET_DIR = "/Game/OrbitalWindow"
FOLDER = "OrbitalWindow"

# Room layout in cm. The camera looks down +X at the back wall.
ROOM_HALF_W = 720.0      # inner half width (Y)
ROOM_H = 800.0
ROOM_BACK_X = -700.0
WALL_FACE_X = 560.0      # back wall face toward the camera
RECESS_X = 660.0         # face of the recessed bay
WALL_BACK_X = 760.0      # outer skin of the hull
BAY_HALF_W = 600.0
BAY_Z0, BAY_Z1 = 30.0, 770.0
BAY_RADIUS = 160.0
WIN_Z = 400.0
WIN_R = 285.0

CAM_LOC = (-450.0, 0.0, 400.0)
CAM_FOCAL_MM = 25.0      # on a 36 x 20.25 mm filmback -> ~71 deg horizontal

# Orbit / sky
PLANET_RADIUS_KM = 6360.0
ALTITUDE_KM = 120.0                  # above the 60 km default atmosphere
PLANET_TILT_DEG = 15.6               # tilts the planet forward so the horizon sits ~2/3 up the porthole
SUN_YAW, SUN_ELEV = 40.0, 40.0       # where the sun is in the sky (camera frame)
SUN_LUX = 10.0
MOON_YAW, MOON_ELEV = 5.0, 8.1
MOON_DIST = 1.5e6                    # cm
MOON_ANGULAR_DEG = 3.2

# Exterior structure framing the top/bottom of the view (elevation angles, deg)
OVERHANG_EDGE_ELEV = 10.1
DECK_EDGE_ELEV = -11.0
OVERHANG_Z = 1100.0
DECK_Z = -250.0

# Dreamy look: push these up for more glow/haze, down for a cleaner image
POST_EXPOSURE_BIAS = 1.0
POST_BLOOM = 1.4
HAZE_DENSITY = 0.006
SUN_SHAFT_STRENGTH = 2.5

# --------------------------------------------------------------------------
# Editor handles
# --------------------------------------------------------------------------
EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
LES = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
UES = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
EAL = unreal.EditorAssetLibrary
MEL = unreal.MaterialEditingLibrary
AT = unreal.AssetToolsHelpers.get_asset_tools()

GSP = unreal.GeometryScript_Primitives
GSB = unreal.GeometryScript_MeshBooleans
GSN = unreal.GeometryScript_Normals
GSA = unreal.GeometryScript_NewAssetUtils
ORIGIN_CENTER = unreal.GeometryScriptPrimitiveOriginMode.CENTER
POPTS = unreal.GeometryScriptPrimitiveOptions()
BOOL_OPTS = unreal.GeometryScriptMeshBooleanOptions()
IDENTITY = unreal.Transform()
SUBTRACT = unreal.GeometryScriptBooleanOperation.SUBTRACT

MOVABLE = unreal.ComponentMobility.MOVABLE
FAILURES = []


def V(x, y, z):
    return unreal.Vector(x, y, z)


def R(pitch=0.0, yaw=0.0, roll=0.0):
    return unreal.Rotator(roll=roll, pitch=pitch, yaw=yaw)


def xf(loc=(0, 0, 0), rot=(0, 0, 0)):
    return unreal.Transform(location=V(*loc), rotation=R(*rot), scale=V(1, 1, 1))


def direction(yaw_deg, elev_deg):
    y, e = math.radians(yaw_deg), math.radians(elev_deg)
    return (math.cos(e) * math.cos(y), math.cos(e) * math.sin(y), math.sin(e))


def step(name, fn):
    unreal.log(f"[OrbitalWindow] {name}...")
    try:
        return fn()
    except Exception:
        FAILURES.append(name)
        unreal.log_error(f"[OrbitalWindow] {name} failed:\n{traceback.format_exc()}")


def try_set(obj, key, value):
    # Property names drift between engine versions; one bad name shouldn't sink a whole step.
    try:
        obj.set_editor_property(key, value)
    except Exception as e:
        unreal.log_warning(f"[OrbitalWindow] couldn't set {key}: {e}")


def tag(actor, label, sub=""):
    actor.set_actor_label(label)
    actor.set_folder_path(f"{FOLDER}/{sub}" if sub else FOLDER)
    return actor


def spawn(cls, label, sub, loc=(0, 0, 0), rot=(0, 0, 0)):
    return tag(EAS.spawn_actor_from_class(cls, V(*loc), R(*rot)), label, sub)


# --------------------------------------------------------------------------
# Level
# --------------------------------------------------------------------------
def open_level():
    if EAL.does_asset_exist(LEVEL_PATH):
        LES.load_level(LEVEL_PATH)
        old = [a for a in EAS.get_all_level_actors() if str(a.get_folder_path()).startswith(FOLDER)]
        if old:
            EAS.destroy_actors(old)
    else:
        LES.new_level(LEVEL_PATH)


# --------------------------------------------------------------------------
# Materials
# --------------------------------------------------------------------------
def make_material(name, base, rough=0.5, metal=0.0, emissive=None, opacity=None, noise=None):
    folder = f"{ASSET_DIR}/Materials"
    path = f"{folder}/{name}"
    if EAL.does_asset_exist(path):
        m = EAL.load_asset(path)
    else:
        m = AT.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    # Clear any default Substrate slab so the legacy inputs below drive the material.
    MEL.delete_all_material_expressions(m)

    def vec3(rgb, y):
        e = MEL.create_material_expression(m, unreal.MaterialExpressionConstant3Vector, -500, y)
        e.set_editor_property("constant", unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
        return e

    def scalar(v, y):
        e = MEL.create_material_expression(m, unreal.MaterialExpressionConstant, -300, y)
        e.set_editor_property("r", v)
        return e

    if noise:
        # Blotchy two-tone base colour (used for the moon).
        dark, scale = noise
        n = MEL.create_material_expression(m, unreal.MaterialExpressionNoise, -700, 0)
        n.set_editor_property("scale", scale)
        n.set_editor_property("levels", 5)
        n.set_editor_property("output_min", 0.0)
        n.set_editor_property("output_max", 1.0)
        lerp = MEL.create_material_expression(m, unreal.MaterialExpressionLinearInterpolate, -250, 0)
        MEL.connect_material_expressions(vec3(dark, -150), "", lerp, "A")
        MEL.connect_material_expressions(vec3(base, 150), "", lerp, "B")
        MEL.connect_material_expressions(n, "", lerp, "Alpha")
        MEL.connect_material_property(lerp, "", unreal.MaterialProperty.MP_BASE_COLOR)
    else:
        MEL.connect_material_property(vec3(base, 0), "", unreal.MaterialProperty.MP_BASE_COLOR)

    MEL.connect_material_property(scalar(rough, 200), "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(scalar(metal, 300), "", unreal.MaterialProperty.MP_METALLIC)
    if emissive:
        MEL.connect_material_property(vec3(emissive, 400), "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    if opacity is not None:
        m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
        MEL.connect_material_property(scalar(opacity, 500), "", unreal.MaterialProperty.MP_OPACITY)
    else:
        m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)

    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    return m


MATS = {}


def build_materials():
    MATS["hull"] = make_material("M_Hull", (0.80, 0.82, 0.84), rough=0.4)
    MATS["panel"] = make_material("M_HullPanel", (0.70, 0.72, 0.75), rough=0.5)
    MATS["trim"] = make_material("M_Trim", (0.90, 0.92, 0.94), rough=0.22)
    MATS["dark"] = make_material("M_DarkMetal", (0.07, 0.08, 0.09), rough=0.45, metal=0.6)
    MATS["glass"] = make_material("M_WindowGlass", (0.8, 0.9, 1.0), rough=0.03, opacity=0.06)
    MATS["light"] = make_material("M_LightPanel", (0.0, 0.0, 0.0), rough=0.5, emissive=(6.0, 6.2, 6.5))
    MATS["moon"] = make_material("M_Moon", (0.55, 0.56, 0.58), rough=0.95,
                                 noise=((0.28, 0.29, 0.31), 0.00012))


# --------------------------------------------------------------------------
# Geometry Script helpers (boolean-cut hero meshes baked to static meshes)
# --------------------------------------------------------------------------
def gs_box(mesh, x0, x1, y0, y1, z0, z1):
    GSP.append_box(mesh, POPTS, xf(((x0 + x1) * .5, (y0 + y1) * .5, (z0 + z1) * .5)),
                   x1 - x0, y1 - y0, z1 - z0, 0, 0, 0, ORIGIN_CENTER)


def gs_cyl_x(mesh, x0, x1, y, z, r, steps=128):
    # Pitch 90 turns the Z-up cylinder to run along X.
    GSP.append_cylinder(mesh, POPTS, xf(((x0 + x1) * .5, y, z), (90, 0, 0)),
                        r, x1 - x0, steps, 0, True, ORIGIN_CENTER)


def gs_torus_x(mesh, x, y, z, major, minor, major_steps=128, minor_steps=16):
    GSP.append_torus(mesh, POPTS, xf((x, y, z), (90, 0, 0)), unreal.GeometryScriptRevolveOptions(),
                     major, minor, major_steps, minor_steps, ORIGIN_CENTER)


def subtract(target, builder):
    tool = unreal.DynamicMesh()
    builder(tool)
    GSB.apply_mesh_boolean(target, IDENTITY, tool, IDENTITY, SUBTRACT, BOOL_OPTS)


def rrect_pieces(x0, x1, half_w, z0, z1, r):
    """Rounded rectangle prism (in the YZ plane, extruded along X) as boolean tool pieces."""
    pieces = [
        lambda m: gs_box(m, x0, x1, -half_w + r, half_w - r, z0, z1),
        lambda m: gs_box(m, x0, x1, -half_w, half_w, z0 + r, z1 - r),
    ]
    for cy in (-half_w + r, half_w - r):
        for cz in (z0 + r, z1 - r):
            pieces.append(lambda m, cy=cy, cz=cz: gs_cyl_x(m, x0, x1, cy, cz, r, 48))
    return pieces


def unique_path(path):
    if not EAL.does_asset_exist(path) or EAL.delete_asset(path):
        return path
    i = 1
    while EAL.does_asset_exist(f"{path}_{i}"):
        i += 1
    return f"{path}_{i}"


def bake(mesh, name):
    try:
        GSN.compute_split_normals(mesh, unreal.GeometryScriptSplitNormalsOptions(),
                                  unreal.GeometryScriptCalculateNormalsOptions())
    except Exception:
        unreal.log_warning(f"[OrbitalWindow] normals recompute skipped for {name}")
    path = unique_path(f"{ASSET_DIR}/Meshes/{name}")
    result = GSA.create_new_static_mesh_asset_from_mesh(
        mesh, path, unreal.GeometryScriptCreateNewStaticMeshAssetOptions())
    sm = result[0] if isinstance(result, (tuple, list)) else result
    if not sm:
        raise RuntimeError(f"could not create static mesh {path}")
    EAL.save_loaded_asset(sm)
    return sm


def place_mesh(sm, mat, label, sub, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), shadows=True):
    a = spawn(unreal.StaticMeshActor, label, sub, loc, rot)
    a.set_actor_scale3d(V(*scale))
    c = a.get_editor_property("static_mesh_component")
    c.set_static_mesh(sm)
    if mat:
        c.set_material(0, mat)
    if not shadows:
        c.set_cast_shadow(False)
    return a


CUBE = None
SPHERE = None


def box(label, sub, mat, x0, x1, y0, y1, z0, z1, shadows=True):
    return place_mesh(CUBE, mat, label, sub,
                      ((x0 + x1) * .5, (y0 + y1) * .5, (z0 + z1) * .5), (0, 0, 0),
                      ((x1 - x0) / 100.0, (y1 - y0) / 100.0, (z1 - z0) / 100.0), shadows)


# --------------------------------------------------------------------------
# Scene parts
# --------------------------------------------------------------------------
def build_back_wall():
    m = unreal.DynamicMesh()
    gs_box(m, WALL_FACE_X, WALL_BACK_X, -ROOM_HALF_W - 40, ROOM_HALF_W + 40, -30, ROOM_H + 30)
    # Shallow outer step, then the deep rounded bay, then the porthole itself.
    for p in rrect_pieces(WALL_FACE_X - 10, WALL_FACE_X + 20, BAY_HALF_W + 30,
                          BAY_Z0 - 15, BAY_Z1 + 15, BAY_RADIUS + 30):
        subtract(m, p)
    for p in rrect_pieces(WALL_FACE_X - 10, RECESS_X, BAY_HALF_W, BAY_Z0, BAY_Z1, BAY_RADIUS):
        subtract(m, p)
    subtract(m, lambda t: gs_cyl_x(t, WALL_FACE_X, WALL_BACK_X + 50, 0, WIN_Z, WIN_R, 160))
    place_mesh(bake(m, "SM_BackWall"), MATS["hull"], "BackWall", "Shell")


def build_porthole():
    # Thick bezel ring proud of the bay face.
    bezel = unreal.DynamicMesh()
    gs_cyl_x(bezel, RECESS_X - 22, RECESS_X + 2, 0, WIN_Z, WIN_R + 55, 160)
    subtract(bezel, lambda t: gs_cyl_x(t, RECESS_X - 40, RECESS_X + 20, 0, WIN_Z, WIN_R, 160))
    place_mesh(bake(bezel, "SM_PortholeBezel"), MATS["trim"], "PortholeBezel", "Porthole")

    lip = unreal.DynamicMesh()
    gs_torus_x(lip, RECESS_X - 22, 0, WIN_Z, WIN_R + 3, 10)
    place_mesh(bake(lip, "SM_PortholeLip"), MATS["trim"], "PortholeLip", "Porthole")

    gasket = unreal.DynamicMesh()
    gs_torus_x(gasket, WALL_BACK_X - 20, 0, WIN_Z, WIN_R, 7)
    place_mesh(bake(gasket, "SM_PortholeGasket"), MATS["dark"], "PortholeGasket", "Porthole")

    glass = unreal.DynamicMesh()
    gs_cyl_x(glass, WALL_BACK_X - 17, WALL_BACK_X - 15, 0, WIN_Z, WIN_R + 4, 160)
    place_mesh(bake(glass, "SM_PortholeGlass"), MATS["glass"], "PortholeGlass", "Porthole", shadows=False)

    # Plates and vents on the bay face around the window.
    for side in (-1, 1):
        box(f"BayPlate_{side}", "Porthole", MATS["panel"],
            RECESS_X - 6, RECESS_X, side * 420 - 22, side * 420 + 22, WIN_Z - 70, WIN_Z + 70)
    for i, a in enumerate((45, 135, 225, 315)):
        y = (WIN_R + 115) * math.cos(math.radians(a))
        z = WIN_Z + (WIN_R + 115) * math.sin(math.radians(a))
        box(f"BayVent_{i}", "Porthole", MATS["dark"], RECESS_X - 3, RECESS_X, y - 18, y + 18, z - 18, z + 18)


def build_room():
    w, h = ROOM_HALF_W, ROOM_H
    box("Floor", "Shell", MATS["hull"], ROOM_BACK_X, WALL_BACK_X, -w - 40, w + 40, -30, 0)
    box("Ceiling", "Shell", MATS["hull"], ROOM_BACK_X, WALL_FACE_X + 1, -w - 40, w + 40, h, h + 30)
    box("Wall_L", "Shell", MATS["hull"], ROOM_BACK_X, WALL_FACE_X + 1, -w - 40, -w, 0, h)
    box("Wall_R", "Shell", MATS["hull"], ROOM_BACK_X, WALL_FACE_X + 1, w, w + 40, 0, h)
    box("Wall_Rear", "Shell", MATS["hull"], ROOM_BACK_X - 30, ROOM_BACK_X, -w - 40, w + 40, -30, h + 30)

    # Side wall panelling.
    rows = ((20, 250), (264, 540), (554, 780))
    for side in (-1, 1):
        x, i = -640.0, 0
        while x + 200 < 360:
            for z0, z1 in rows:
                mat = MATS["panel"] if (i % 2) else MATS["trim"]
                y0, y1 = sorted((side * w, side * (w - 5)))
                box(f"WallPanel_{side}_{i}", "Panels", mat, x, x + 246, y0, y1, z0, z1)
                i += 1
            x += 260

    # Floor plates, and a slatted grille in front of the bay.
    i = 0
    for x in range(-700, 280, 245):
        for y in range(-720, 720, 240):
            box(f"FloorPlate_{i}", "Floor", MATS["panel"], x + 4, x + 241, y + 4, y + 236, 0, 1)
            i += 1
    box("Grille_Base", "Floor", MATS["dark"], 280, WALL_FACE_X, -560, 560, 0, 1)
    x, i = 286.0, 0
    while x + 16 < WALL_FACE_X:
        box(f"Grille_Slat_{i}", "Floor", MATS["trim"], x, x + 16, -560, 560, 1, 5)
        x, i = x + 28, i + 1


def build_greebles():
    rng = random.Random(7)
    w = ROOM_HALF_W
    for side in (-1, 1):
        z, i = 30.0, 0
        while z < ROOM_H - 60:
            hgt = rng.uniform(40, 140)
            depth = rng.uniform(15, 45)
            x0 = rng.uniform(370, 450)
            y0, y1 = sorted((side * w, side * (w - depth)))
            mat = rng.choice((MATS["hull"], MATS["panel"], MATS["panel"], MATS["dark"]))
            box(f"Rack_{side}_{i}", "Greebles", mat, x0, WALL_FACE_X, y0, y1, z, min(z + hgt, ROOM_H - 20))
            z += hgt + rng.uniform(6, 20)
            i += 1
        # Vertical light strip beside the bay and small pods by the ceiling.
        y0, y1 = sorted((side * w, side * (w - 3)))
        box(f"LightStrip_{side}", "Lights", MATS["light"], 350, 362, y0, y1, 100, 700, shadows=False)
        y0, y1 = sorted((side * 640, side * 690))
        box(f"CeilingPod_{side}", "Lights", MATS["light"], 490, 540, y0, y1, ROOM_H - 6, ROOM_H, shadows=False)


def build_exterior():
    cam_x, _, cam_z = CAM_LOC
    over_end = cam_x + (OVERHANG_Z - cam_z) / math.tan(math.radians(OVERHANG_EDGE_ELEV))
    deck_end = cam_x + (DECK_Z - cam_z) / math.tan(math.radians(DECK_EDGE_ELEV))
    hw = 1800
    # Overhang doesn't cast shadows so the sun can still pour in through the porthole.
    box("Overhang", "Exterior", MATS["hull"], WALL_BACK_X, over_end, -hw, hw, OVERHANG_Z, OVERHANG_Z + 80, shadows=False)
    x, i = WALL_BACK_X + 150, 0
    while x < over_end - 60:
        box(f"OverhangRib_{i}", "Exterior", MATS["panel"], x, x + 40, -hw, hw, OVERHANG_Z - 60, OVERHANG_Z, shadows=False)
        x, i = x + 350, i + 1
    for y in (-600, 600):
        box(f"OverhangBeam_{y}", "Exterior", MATS["trim"], WALL_BACK_X, over_end, y - 30, y + 30,
            OVERHANG_Z - 90, OVERHANG_Z, shadows=False)

    box("Deck", "Exterior", MATS["hull"], WALL_BACK_X, deck_end, -hw, hw, DECK_Z - 80, DECK_Z)
    rng = random.Random(11)
    for i in range(14):
        x0 = rng.uniform(WALL_BACK_X + 200, deck_end - 200)
        y0 = rng.uniform(-hw + 100, hw - 300)
        box(f"DeckGear_{i}", "Exterior", rng.choice((MATS["panel"], MATS["trim"], MATS["dark"])),
            x0, x0 + rng.uniform(60, 220), y0, y0 + rng.uniform(60, 260), DECK_Z, DECK_Z + rng.uniform(30, 120))

    # Hull facade tying the window wall to the overhang and deck.
    box("Facade_Top", "Exterior", MATS["hull"], WALL_BACK_X - 1, WALL_BACK_X + 60, -hw, hw, ROOM_H + 30, OVERHANG_Z + 80)
    box("Facade_Bottom", "Exterior", MATS["hull"], WALL_BACK_X - 1, WALL_BACK_X + 60, -hw, hw, DECK_Z - 80, -30)
    for side in (-1, 1):
        y0, y1 = sorted((side * (ROOM_HALF_W + 40), side * hw))
        box(f"Facade_Side_{side}", "Exterior", MATS["hull"], WALL_BACK_X - 1, WALL_BACK_X + 60, y0, y1, -30, ROOM_H + 30)


def build_sky():
    # Sun
    sun = spawn(unreal.DirectionalLight, "Sun", "Sky", (0, 0, 1500), (-SUN_ELEV, SUN_YAW + 180, 0))
    lc = sun.get_component_by_class(unreal.DirectionalLightComponent)
    lc.set_mobility(MOVABLE)
    lc.set_editor_property("intensity", SUN_LUX)
    lc.set_editor_property("atmosphere_sun_light", True)
    lc.set_editor_property("light_source_angle", 0.53)

    # Planet: centre placed below and slightly ahead so the horizon rises into the window.
    t = math.radians(PLANET_TILT_DEG)
    d = (PLANET_RADIUS_KM + ALTITUDE_KM) * 1e5
    atmo = spawn(unreal.SkyAtmosphere, "SkyAtmosphere", "Sky", (d * math.sin(t), 0, -d * math.cos(t)))
    ac = atmo.get_component_by_class(unreal.SkyAtmosphereComponent)
    ac.set_editor_property("transform_mode", unreal.SkyAtmosphereTransformMode.PLANET_CENTER_AT_COMPONENT_TRANSFORM)
    ac.set_editor_property("bottom_radius", PLANET_RADIUS_KM)
    ac.set_editor_property("ground_albedo", unreal.Color(r=14, g=38, b=78, a=255))  # ocean blue between clouds

    clouds = spawn(unreal.VolumetricCloud, "VolumetricCloud", "Sky")
    cc = clouds.get_component_by_class(unreal.VolumetricCloudComponent)
    cloud_mat = EAL.load_asset("/Engine/EngineSky/VolumetricClouds/m_SimpleVolumetricCloud_Inst")
    if cloud_mat:
        cc.set_editor_property("material", cloud_mat)
    cc.set_editor_property("layer_bottom_altitude", 2.0)
    cc.set_editor_property("layer_height", 8.0)
    cc.set_editor_property("tracing_start_max_distance", 3000.0)  # see clouds all the way to the horizon

    sky = spawn(unreal.SkyLight, "SkyLight", "Sky", (0, 0, 600))
    sc = sky.get_component_by_class(unreal.SkyLightComponent)
    sc.set_mobility(MOVABLE)
    sc.set_editor_property("real_time_capture", True)

    # Moon
    dx, dy, dz = direction(MOON_YAW, MOON_ELEV)
    loc = (CAM_LOC[0] + dx * MOON_DIST, CAM_LOC[1] + dy * MOON_DIST, CAM_LOC[2] + dz * MOON_DIST)
    s = 2 * MOON_DIST * math.tan(math.radians(MOON_ANGULAR_DEG * .5)) / 100.0
    place_mesh(SPHERE, MATS["moon"], "Moon", "Sky", loc, (20, 30, 0), (s, s, s), shadows=False)


def build_lights():
    for side in (-1, 1):
        y = side * 340
        box(f"CeilingStrip_{side}", "Lights", MATS["light"], -600, 450, y - 40, y + 40, ROOM_H - 4, ROOM_H, shadows=False)
        for i, x in enumerate((-430, -75, 280)):
            rl = spawn(unreal.RectLight, f"CeilingRect_{side}_{i}", "Lights", (x, y, ROOM_H - 6), (-90, 0, 0))
            c = rl.get_component_by_class(unreal.RectLightComponent)
            c.set_mobility(MOVABLE)
            c.set_editor_property("intensity", 30.0)
            c.set_editor_property("source_width", 80.0)
            c.set_editor_property("source_height", 300.0)
            c.set_editor_property("attenuation_radius", 2000.0)
            c.set_editor_property("light_color", unreal.Color(r=240, g=246, b=255, a=255))


def build_camera_and_post():
    cam = spawn(unreal.CineCameraActor, "ShotCamera", "Camera", CAM_LOC, (0, 0, 0))
    cc = cam.get_cine_camera_component()
    fb = cc.get_editor_property("filmback")
    fb.set_editor_property("sensor_width", 36.0)
    fb.set_editor_property("sensor_height", 20.25)
    cc.set_editor_property("filmback", fb)
    cc.set_editor_property("current_focal_length", CAM_FOCAL_MM)
    fs = cc.get_editor_property("focus_settings")
    fs.set_editor_property("focus_method", unreal.CameraFocusMethod.DISABLE)
    cc.set_editor_property("focus_settings", fs)
    cam.set_editor_property("auto_activate_for_player", unreal.AutoReceiveInput.PLAYER0)

    UES.set_level_viewport_camera_info(V(*CAM_LOC), R(0, 0, 0))


def build_dreamy_look():
    # Soft, high-key grade: bright exposure, wide bloom, lifted blacks, low contrast,
    # a touch less saturation and a faint cool tint, like the reference.
    ppv = spawn(unreal.PostProcessVolume, "PostProcess", "Camera")
    ppv.set_editor_property("unbound", True)
    s = ppv.get_editor_property("settings")
    for k, v in (("auto_exposure_bias", POST_EXPOSURE_BIAS),
                 ("bloom_intensity", POST_BLOOM),
                 ("bloom_threshold", -1.0),
                 ("vignette_intensity", 0.18),
                 ("film_toe", 0.62),
                 ("film_shoulder", 0.30),
                 ("color_contrast", unreal.Vector4(0.88, 0.88, 0.88, 0.88)),
                 ("color_saturation", unreal.Vector4(0.88, 0.90, 0.95, 0.90)),
                 ("scene_color_tint", unreal.LinearColor(0.97, 0.99, 1.03, 1.0))):
        try_set(s, f"override_{k}", True)
        try_set(s, k, v)
    ppv.set_editor_property("settings", s)

    # Thin interior haze so the sun throws soft shafts through the porthole. The cutoff
    # keeps it off the sky so the planet and clouds stay crisp behind the glass.
    fog = spawn(unreal.ExponentialHeightFog, "InteriorHaze", "Camera", (0, 0, 0))
    fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    for k, v in (("fog_density", HAZE_DENSITY),
                 ("fog_height_falloff", 0.05),
                 ("fog_max_opacity", 0.35),
                 ("fog_cutoff_distance", 4000.0),
                 ("fog_inscattering_luminance", unreal.LinearColor(0.55, 0.68, 0.85, 1.0)),
                 ("volumetric_fog", True),
                 ("volumetric_fog_scattering_distribution", 0.6),
                 ("volumetric_fog_albedo", unreal.Color(r=245, g=250, b=255, a=255)),
                 ("volumetric_fog_extinction_scale", 0.6),
                 ("volumetric_fog_distance", 3000.0)):
        try_set(fc, k, v)

    sun = next((a for a in EAS.get_all_level_actors()
                if isinstance(a, unreal.DirectionalLight) and a.get_actor_label() == "Sun"), None)
    if sun:
        lc = sun.get_component_by_class(unreal.DirectionalLightComponent)
        try_set(lc, "volumetric_scattering_intensity", SUN_SHAFT_STRENGTH)
        try_set(lc, "cast_volumetric_shadow", True)


# --------------------------------------------------------------------------
def main():
    global CUBE, SPHERE
    open_level()
    CUBE = EAL.load_asset("/Engine/BasicShapes/Cube")
    SPHERE = EAL.load_asset("/Engine/BasicShapes/Sphere")

    with unreal.ScopedSlowTask(10, "Building orbital window scene") as task:
        task.make_dialog(False)
        for name, fn in (("materials", build_materials), ("back wall", build_back_wall),
                         ("porthole", build_porthole), ("room", build_room),
                         ("greebles", build_greebles), ("exterior", build_exterior),
                         ("sky", build_sky), ("lights", build_lights),
                         ("camera", build_camera_and_post), ("dreamy look", build_dreamy_look)):
            task.enter_progress_frame(1, f"Building {name}")
            step(name, fn)

    LES.save_current_level()
    if FAILURES:
        unreal.log_error(f"[OrbitalWindow] finished with failures in: {', '.join(FAILURES)}")
    else:
        unreal.log(f"[OrbitalWindow] done -> {LEVEL_PATH}")


main()
