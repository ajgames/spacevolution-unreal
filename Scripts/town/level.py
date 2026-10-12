"""The BiodiverCity level: terrain, instanced buildings and trees, bridges and the spire, the ocean, an afternoon
sky over the Penang hills, the hero camera matching the reference render, and the wave rider's start."""
import unreal

from . import layout, shape
from .util import EAL, EAS, LES, M, ROOT, UES, R, V, V2, log, try_set

LEVEL_PATH = f"{ROOT}/Maps/L_BiodiverCity"
FOLDERS = ("Terrain", "Town", "Ocean", "Environment", "Camera")

# Yachts at anchor in sheltered water: (x, y, yaw)
YACHTS = [(-1400.0, -600.0, 20.0), (160.0, -210.0, 120.0), (1180.0, -900.0, -10.0), (1080.0, 260.0, 170.0),
          (-1980.0, 1180.0, 60.0), (-2320.0, 2150.0, 100.0), (-560.0, -1620.0, 75.0)]

ATMOSPHERE = {"aerial_pespective_view_distance_scale": 1.0, "height_fog_contribution": 1.0}
CLOUDS = {"layer_bottom_altitude": 1.6, "layer_height": 4.0}
FOG = {
    "fog_density": 0.006,
    # Height fog is flat-world: seen from high up it lays a hard band of haze along the eye-level horizon. Beyond this
    # the sky atmosphere's own aerial perspective does the hazing.
    "fog_cutoff_distance": 3.0e6,
    "fog_height_falloff": 0.15,
    "fog_max_opacity": 0.6,
    "start_distance": 3000.0,
    "fog_inscattering_luminance": unreal.LinearColor(0.32, 0.42, 0.55, 1.0),
    "directional_inscattering_exponent": 6.0,
    "directional_inscattering_luminance": unreal.LinearColor(0.9, 0.75, 0.55, 1.0),
}
EXPOSURE = {"min_ev100": 2.0, "max_ev100": 9.0, "bias": 0.7}
SCREEN = (1600, 900)


def _tag(actor, label, folder):
    actor.set_actor_label(label)
    actor.set_folder_path(folder)
    return actor


def _spawn(cls, label, folder, loc=(0, 0, 0), rot=(0, 0, 0)):
    return _tag(EAS.spawn_actor_from_class(cls, V(*loc), R(*rot)), label, folder)


def _mesh_actor(mesh, label, folder, loc=(0, 0, 0), yaw=0.0):
    actor = _spawn(unreal.StaticMeshActor, label, folder, loc, (0, yaw, 0))
    actor.static_mesh_component.set_static_mesh(mesh)
    return actor


def _xf(x, y, z, yaw, sx=1.0, sy=1.0, sz=1.0):
    return unreal.Transform(location=V(x * M, y * M, z * M), rotation=R(0.0, yaw, 0.0), scale=V(sx, sy, sz))


def open_level():
    """Opens the town level with everything the generator owns removed, creating it on the first run."""
    if EAL.does_asset_exist(LEVEL_PATH):
        LES.load_level(LEVEL_PATH)
        ours = [a for a in EAS.get_all_level_actors() if str(a.get_folder_path()).split("/")[0] in FOLDERS]
        if ours:
            EAS.destroy_actors(ours)
    else:
        LES.new_level(LEVEL_PATH, False)


def build_town(plan, kit, materials, bridge_mesh):
    groups = {}
    for kind, facade, roof, x, y, z, yaw, sx, sy, sz in plan.buildings:
        groups.setdefault((kind, facade, roof), []).append(_xf(x, y, z, yaw, sx, sy, sz))
    buildings = _spawn(unreal.TownInstances, "Buildings", "Town")
    for (kind, facade, roof), xfs in sorted(groups.items()):
        buildings.add_instances(kit[kind], xfs, [materials[f"Facade_{facade}"], materials[f"Roof_{roof}"]],
                                True, True, 0.0)
    trees = {}
    for kind, x, y, z, yaw, scale in plan.trees:
        trees.setdefault(kind, []).append(_xf(x, y, z, yaw, scale, scale, scale * (0.9 + 0.2 * ((x * 7.3) % 1.0))))
    grove = _spawn(unreal.TownInstances, "Trees", "Town")
    for kind, xfs in sorted(trees.items()):
        grove.add_instances(kit[kind], xfs, [], False, True, 0.0)
    log(f"{len(plan.buildings)} buildings in {len(groups)} groups, {len(plan.trees)} trees")

    lx, ly, _ = layout.LANDMARK
    _mesh_actor(kit["landmark"], "Spire", "Town", (lx * M, ly * M, shape.height(lx, ly) * M - 50.0))
    _mesh_actor(bridge_mesh, "Bridges", "Town")
    for i, (x, y, yaw) in enumerate(YACHTS):
        if shape.height(x, y) < -1.5:
            _mesh_actor(kit["yacht"], f"Yacht_{i}", "Town/Boats", (x * M, y * M, -10.0), yaw)


def build_spaceport(meshes):
    port = shape.spaceport()
    px, py = port["pad"]
    _mesh_actor(meshes["pad"], "Pad", "Town/Spaceport", (px * M, py * M, 0.0))
    bx, by = layout.BEACON_OFFSET
    _mesh_actor(meshes["beacon"], "Beacon", "Town/Spaceport", ((px + bx) * M, (py + by) * M, layout.PAD_TOP * M - 20.0))
    sx, sy = port["pier_start"]
    _mesh_actor(meshes["pier"], "Pier", "Town/Spaceport", (sx * M, sy * M, 0.0))


def build_ocean(water):
    ocean = _spawn(unreal.Ocean, "Ocean", "Ocean")
    ocean.set_editor_property("ocean_material", water["material"])
    ocean.set_editor_property("waves", [unreal.OceanWave(direction_degrees=d, wavelength=l, amplitude=a)
                                        for d, l, a in layout.WAVES])
    ocean.set_editor_property("steepness", layout.WAVE_STEEPNESS)
    ocean.set_editor_property("calm_zones", [unreal.OceanCalmZone(centre=V2(x, y), inner_radius=i, outer_radius=o)
                                             for x, y, i, o in shape.calm_zones()])
    ocean.set_editor_property("calm_floor", layout.CALM_FLOOR)
    surface = ocean.get_component_by_class(unreal.StaticMeshComponent)
    surface.set_static_mesh(water["mesh"])
    return ocean


def build_sky():
    # The light travels away from the sun: from the west-south-west, down onto the town.
    sun = _spawn(unreal.DirectionalLight, "Sun", "Environment", (0, 0, 10000), (-layout.SUN_ELEVATION, layout.SUN_YAW, 0))
    lc = sun.get_component_by_class(unreal.DirectionalLightComponent)
    lc.set_mobility(unreal.ComponentMobility.MOVABLE)
    lc.set_editor_property("intensity", layout.SUN_LUX)
    lc.set_editor_property("atmosphere_sun_light", True)
    lc.set_editor_property("light_source_angle", 0.53)
    try_set(lc, "cast_cloud_shadows", True)

    atmo = _spawn(unreal.SkyAtmosphere, "SkyAtmosphere", "Environment")
    ac = atmo.get_component_by_class(unreal.SkyAtmosphereComponent)
    for key, value in ATMOSPHERE.items():
        try_set(ac, key, value)

    clouds = _spawn(unreal.VolumetricCloud, "VolumetricCloud", "Environment")
    cc = clouds.get_component_by_class(unreal.VolumetricCloudComponent)
    for key, value in CLOUDS.items():
        try_set(cc, key, value)

    sky = _spawn(unreal.SkyLight, "SkyLight", "Environment", (0, 0, 5000))
    sc = sky.get_component_by_class(unreal.SkyLightComponent)
    sc.set_mobility(unreal.ComponentMobility.MOVABLE)
    sc.set_editor_property("real_time_capture", True)

    fog = _spawn(unreal.ExponentialHeightFog, "Haze", "Environment")
    fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    for key, value in FOG.items():
        try_set(fc, key, value)


def build_camera_and_grade(game_mode):
    cx, cy, cz = layout.CAMERA
    loc, rot = (cx * M, cy * M, cz * M), (layout.CAMERA_PITCH, 0.0, 0.0)
    cam = _spawn(unreal.CineCameraActor, "HeroCam", "Camera", loc, rot)
    cc = cam.get_cine_camera_component()
    fb = cc.get_editor_property("filmback")
    fb.set_editor_property("sensor_width", 36.0)
    fb.set_editor_property("sensor_height", 20.25)
    cc.set_editor_property("filmback", fb)
    cc.set_editor_property("current_focal_length", layout.FOCAL_MM)
    fs = cc.get_editor_property("focus_settings")
    fs.set_editor_property("focus_method", unreal.CameraFocusMethod.DISABLE)
    cc.set_editor_property("focus_settings", fs)

    px, py, pz = layout.PLAYER_START
    _spawn(unreal.PlayerStart, "PlayerStart", "Camera", (px * M, py * M, pz * M), (0.0, layout.PLAYER_YAW, 0.0))

    ppv = _spawn(unreal.PostProcessVolume, "PostProcess", "Camera")
    ppv.set_editor_property("unbound", True)
    s = ppv.get_editor_property("settings")
    for key, value in (
            ("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM),
            ("auto_exposure_min_brightness", EXPOSURE["min_ev100"]),
            ("auto_exposure_max_brightness", EXPOSURE["max_ev100"]),
            ("auto_exposure_bias", EXPOSURE["bias"]),
            ("bloom_intensity", 0.5),
            ("vignette_intensity", 0.25),
            ("white_temp", 6900.0),
            ("lumen_final_gather_quality", 1.5),
            ("lumen_reflection_quality", 1.5),
            ("lumen_front_layer_translucency_reflections", True)):
        try_set(s, f"override_{key}", True)
        try_set(s, key, value)
    ppv.set_editor_property("settings", s)

    world = UES.get_editor_world()
    world.get_world_settings().set_editor_property("default_game_mode", game_mode.generated_class())
    UES.set_level_viewport_camera_info(V(*loc), R(*rot))
    return cam


def build(plan, ground, kit, materials, bridge_mesh, water, rider, port):
    _mesh_actor(ground, "Terrain", "Terrain")
    build_town(plan, kit, materials, bridge_mesh)
    build_spaceport(port)
    build_ocean(water)
    build_sky()
    build_camera_and_grade(rider["mode"])
    LES.save_current_level()
    log(f"level saved -> {LEVEL_PATH}")
