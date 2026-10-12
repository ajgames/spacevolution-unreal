"""The mock-up level: a ship laid out from the kit, an orbital sky beyond the porthole, a hero camera and grade."""
import math

import unreal

from . import audio
from .util import EAL, EAS, LES, ROOT, UES, R, V, log, try_set

LEVEL_PATH = f"{ROOT}/Maps/L_ShipInterior"

# Layout: entry door at cell 0, then corridor sections, then the observation porthole.
CORRIDOR_CELLS = (1, 2, 3)
OVERRIDES = {
    2: {"B0_WallR": "Console", "B0_Ceiling": "CeilingLight", "B1_LowerL": "RodRack", "B1_LowerR": "RodRack",
        "B1_Floor": "FloorHatch"},
    3: {"B0_WallL": "Locker", "B1_WallR": "Locker", "B1_Ceiling": "CeilingFan", "B0_Floor": "FloorGrate"},
}

HERO_CAM = (1450.0, 0.0, 185.0)
HERO_FOCAL_MM = 19.0  # on a 36 x 20.25 mm filmback, ~87 degrees horizontal

# Orbit and sky
PLANET_RADIUS_KM = 6360.0
ALTITUDE_KM = 120.0
PLANET_PITCH_DEG = 11.5  # tilts the planet forward so the horizon crosses the porthole, half Earth, half sky
PLANET_ROLL_DEG = 9.0    # banks the horizon
# Sun high behind the ship: the planet below is in full daylight, and none leaks in through the porthole.
SUN_PITCH, SUN_YAW, SUN_LUX = -70.0, 25.0, 10.0

# Backdrop, as (yaw, pitch) seen from the hero camera looking down the corridor at the porthole.
DISTANT_STAR = (-3.0, 4.6)                         # upper left of the porthole, clear of the limb glow
GALAXY_PLANE = ((-14.0, 14.0), (14.0, -2.0))       # two points on the Milky Way's great circle
GALAXY_CORE = (4.0, 4.0)
BACKDROP_RADIUS_CM = 2.0e7                         # 200 km shell; content is drawn at infinity regardless

EXPOSURE_BIAS = -1.0  # manual exposure, stops relative to the default
BLOOM = 1.0


def _tag(actor, label, folder):
    actor.set_actor_label(label)
    actor.set_folder_path(folder)
    return actor


def _spawn(cls, label, folder, loc=(0, 0, 0), rot=(0, 0, 0)):
    return _tag(EAS.spawn_actor_from_class(cls, V(*loc), R(*rot)), label, folder)


def open_level():
    if EAL.does_asset_exist(LEVEL_PATH):
        LES.load_level(LEVEL_PATH)
        ships = [a for a in EAS.get_all_level_actors() if isinstance(a, unreal.Ship)]
        if ships:
            EAS.destroy_actors(ships)  # takes its modules and fixtures with it
        rest = [a for a in EAS.get_all_level_actors()
                if str(a.get_folder_path()).split("/")[0] in ("Ship", "Environment", "Camera")]
        if rest:
            EAS.destroy_actors(rest)
    else:
        LES.new_level(LEVEL_PATH, False)


def build_ship(modules, fixtures):
    ship = _spawn(unreal.Ship, "Ship", "Ship")
    placements = [unreal.ShipModulePlacement(module=modules["Entry"], cell=unreal.IntVector(0, 0, 0))]
    for x in CORRIDOR_CELLS:
        p = unreal.ShipModulePlacement(module=modules["Corridor"], cell=unreal.IntVector(x, 0, 0))
        overrides = {hp: fixtures[key] for hp, key in OVERRIDES.get(x, {}).items()}
        if overrides:
            p.set_editor_property("fixture_overrides", overrides)
        placements.append(p)
    placements.append(unreal.ShipModulePlacement(module=modules["ObservationEnd"],
                                                 cell=unreal.IntVector(CORRIDOR_CELLS[-1] + 1, 0, 0)))
    ship.set_editor_property("layout", unreal.ShipLayout(modules=placements))
    audio.apply_to_ship(ship)
    ship.rebuild()
    spawned = [a for a in EAS.get_all_level_actors() if isinstance(a, unreal.ShipModule)]
    log(f"ship rebuilt with {len(spawned)} modules")
    return ship


def _direction(yaw_deg, pitch_deg):
    y, p = math.radians(yaw_deg), math.radians(pitch_deg)
    return (math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def planet_centre_cm():
    """Planet centre below and ahead of the ship, so the curved horizon sits high in the porthole."""
    d = (PLANET_RADIUS_KM + ALTITUDE_KM) * 1e5
    p, r = math.radians(PLANET_PITCH_DEG), math.radians(PLANET_ROLL_DEG)
    return (d * math.sin(p), -d * math.cos(p) * math.sin(r), -d * math.cos(p) * math.cos(r))


def ship_start_km():
    """The ship's starting position in the space frame (planet at the origin): the planet sits at
    planet_centre_cm() from the ship, so the ship sits at minus that from the planet."""
    return tuple(-c * 1e-5 for c in planet_centre_cm())


def build_backdrop():
    """Stars, Milky Way, dust lanes, nebulae and a distant star on an additive shell over the atmosphere."""
    mi = EAL.load_asset(f"{ROOT}/Materials/MI_SpaceBackdrop")
    MEL = unreal.MaterialEditingLibrary
    vec = lambda v: unreal.LinearColor(v[0], v[1], v[2], 0.0)
    # The space frame starts aligned with the world, so these directions are the ones seen from the ship at rest.
    MEL.set_material_instance_vector_parameter_value(mi, "SpaceOrigin", vec(ship_start_km()))
    MEL.set_material_instance_scalar_parameter_value(mi, "PlanetRadius", PLANET_RADIUS_KM)
    MEL.set_material_instance_vector_parameter_value(mi, "StarDir", vec(_direction(*DISTANT_STAR)))
    MEL.set_material_instance_vector_parameter_value(mi, "GalaxyNormal",
                                                     vec(_cross(_direction(*GALAXY_PLANE[0]), _direction(*GALAXY_PLANE[1]))))
    MEL.set_material_instance_vector_parameter_value(mi, "GalaxyCore", vec(_direction(*GALAXY_CORE)))
    MEL.update_material_instance(mi)
    EAL.save_loaded_asset(mi)

    shell = _spawn(unreal.StaticMeshActor, "SpaceBackdrop", "Environment")
    shell.set_actor_scale3d(V(*(BACKDROP_RADIUS_CM / 50.0,) * 3))  # engine sphere has a 50 cm radius
    c = shell.static_mesh_component
    c.set_static_mesh(EAL.load_asset("/Engine/BasicShapes/Sphere"))
    c.set_material(0, mi)
    # No collision at all: a 200 km blocking sphere around the ship pushes spawning players out into space.
    c.set_collision_profile_name("NoCollision")
    c.set_editor_property("generate_overlap_events", False)
    for key, value in (("cast_shadow", False), ("visible_in_ray_tracing", False), ("visible_in_reflections", False),
                       ("affect_distance_field_lighting", False), ("affect_dynamic_indirect_lighting", False),
                       ("visible_in_real_time_sky_captures", False), ("visible_in_reflection_captures", False),
                       ("translucency_sort_priority", -100)):  # behind the porthole glass
        try_set(c, key, value)
    return shell


def build_sky():
    sun = _spawn(unreal.DirectionalLight, "Sun", "Environment", (0, 0, 2000), (SUN_PITCH, SUN_YAW, 0))
    lc = sun.get_component_by_class(unreal.DirectionalLightComponent)
    lc.set_mobility(unreal.ComponentMobility.MOVABLE)
    lc.set_editor_property("intensity", SUN_LUX)
    lc.set_editor_property("atmosphere_sun_light", True)
    lc.set_editor_property("light_source_angle", 0.53)

    atmo = _spawn(unreal.SkyAtmosphere, "SkyAtmosphere", "Environment", planet_centre_cm())
    ac = atmo.get_component_by_class(unreal.SkyAtmosphereComponent)
    ac.set_mobility(unreal.ComponentMobility.MOVABLE)  # the space environment moves it as the ship flies
    ac.set_editor_property("transform_mode", unreal.SkyAtmosphereTransformMode.PLANET_CENTER_AT_COMPONENT_TRANSFORM)
    ac.set_editor_property("bottom_radius", PLANET_RADIUS_KM)
    ac.set_editor_property("ground_albedo", unreal.Color(r=10, g=34, b=80, a=255))

    clouds = _spawn(unreal.VolumetricCloud, "VolumetricCloud", "Environment")
    cc = clouds.get_component_by_class(unreal.VolumetricCloudComponent)
    cloud_mat = EAL.load_asset(f"{ROOT}/Materials/MI_OrbitClouds")
    if cloud_mat:
        unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
            cloud_mat, "SpaceOrigin", unreal.LinearColor(*ship_start_km(), 0.0))
        unreal.MaterialEditingLibrary.update_material_instance(cloud_mat)
        EAL.save_loaded_asset(cloud_mat)
        cc.set_editor_property("material", cloud_mat)
    try_set(cc, "layer_bottom_altitude", 2.0)
    try_set(cc, "layer_height", 8.0)
    try_set(cc, "tracing_start_max_distance", 3000.0)
    try_set(cc, "view_sample_count_scale", 4.0)  # crisper cloud tops seen from orbit

    sky = _spawn(unreal.SkyLight, "SkyLight", "Environment", (0, 0, 800))
    sc = sky.get_component_by_class(unreal.SkyLightComponent)
    sc.set_mobility(unreal.ComponentMobility.MOVABLE)
    sc.set_editor_property("real_time_capture", True)
    shell = build_backdrop()
    return {"sun": sun, "planet": atmo, "clouds": clouds, "backdrop": shell}


def build_environment(ship, sky):
    """Zero-point flight: the ship starts where the view already puts it, and SpaceEnvironment arranges
    the planet, sun, clouds and stars around it as it flies."""
    flight = ship.get_flight()
    flight.set_editor_property("start_position_km", V(*ship_start_km()))
    flight.set_editor_property("start_rotation", R(0, 0, 0))
    flight.set_editor_property("planet_radius_km", PLANET_RADIUS_KM)

    env = _spawn(unreal.SpaceEnvironment, "SpaceEnvironment", "Environment")
    env.set_editor_property("ship", ship)
    env.set_editor_property("planet", sky["planet"])
    env.set_editor_property("sun", sky["sun"])
    env.set_editor_property("clouds", sky["clouds"])
    env.set_editor_property("backdrop", sky["backdrop"])
    # Toward the sun, in the space frame (aligned with the world at the start): opposite the light's travel.
    env.set_editor_property("sun_direction", sky["sun"].get_actor_forward_vector() * -1.0)


def build_camera_and_grade():
    cam = _spawn(unreal.CineCameraActor, "HeroCam", "Camera", HERO_CAM)
    cc = cam.get_cine_camera_component()
    fb = cc.get_editor_property("filmback")
    fb.set_editor_property("sensor_width", 36.0)
    fb.set_editor_property("sensor_height", 20.25)
    cc.set_editor_property("filmback", fb)
    cc.set_editor_property("current_focal_length", HERO_FOCAL_MM)
    fs = cc.get_editor_property("focus_settings")
    fs.set_editor_property("focus_method", unreal.CameraFocusMethod.DISABLE)
    cc.set_editor_property("focus_settings", fs)

    _spawn(unreal.PlayerStart, "PlayerStart", "Camera", (150, 0, 100))

    ppv = _spawn(unreal.PostProcessVolume, "PostProcess", "Camera")
    ppv.set_editor_property("unbound", True)
    s = ppv.get_editor_property("settings")
    for key, value in (
            ("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL),
            ("auto_exposure_apply_physical_camera_exposure", False),
            ("auto_exposure_bias", EXPOSURE_BIAS),
            ("bloom_intensity", BLOOM),
            ("vignette_intensity", 0.22),
            ("film_toe", 0.58),
            ("color_saturation", unreal.Vector4(0.95, 0.96, 1.0, 0.95)),
            ("scene_color_tint", unreal.LinearColor(0.98, 0.99, 1.02, 1.0)),
            ("lumen_final_gather_quality", 2.0),
            ("lumen_reflection_quality", 2.0),
            ("lumen_scene_lighting_quality", 2.0),
            ("lumen_front_layer_translucency_reflections", True)):
        try_set(s, f"override_{key}", True)
        try_set(s, key, value)
    ppv.set_editor_property("settings", s)

    fog = _spawn(unreal.ExponentialHeightFog, "InteriorHaze", "Environment", (0, 0, -200))
    fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    for key, value in (("fog_density", 0.012), ("fog_height_falloff", 0.06), ("fog_max_opacity", 0.25),
                       ("fog_cutoff_distance", 4500.0),
                       ("fog_inscattering_luminance", unreal.LinearColor(0.55, 0.62, 0.72, 1.0)),
                       ("enable_volumetric_fog", False)):
        try_set(fc, key, value)

    UES.set_level_viewport_camera_info(V(*HERO_CAM), R(0, 0, 0))
    return cam


def build(modules, fixtures):
    open_level()
    ship = build_ship(modules, fixtures)
    build_environment(ship, build_sky())
    build_camera_and_grade()
    LES.save_current_level()
    log(f"level saved -> {LEVEL_PATH}")
