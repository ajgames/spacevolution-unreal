"""The colony level: terrain, rocks and buildings from the layout, a low sun in a dusty Mars sky, the hero camera
and the grade."""
import math

import unreal

from . import layout, rocks, terrain
from .util import EAL, EAS, LES, M, ROOT, UES, R, V, log, try_set

LEVEL_PATH = f"{ROOT}/Maps/L_MarsColony"
FOLDERS = ("Terrain", "Rocks", "Colony", "Environment", "Camera")

PLANET_RADIUS_KM = 3389.5

# Dust does most of the work: it scatters warm light, absorbs blue (so the low sun turns gold), and the
# aerial-perspective scale thickens it over distance so the far ranges fade into orange haze.
ATMOSPHERE = {
    "atmosphere_height": 60.0,
    "rayleigh_scattering": unreal.LinearColor(1.0, 0.62, 0.32, 1.0),
    "rayleigh_scattering_scale": 0.008,
    "rayleigh_exponential_distribution": 11.0,
    "mie_scattering": unreal.LinearColor(1.0, 0.72, 0.45, 1.0),
    "mie_scattering_scale": 0.018,
    "mie_absorption": unreal.LinearColor(0.1, 0.4, 1.0, 1.0),
    "mie_absorption_scale": 0.02,
    "mie_anisotropy": 0.7,
    "mie_exponential_distribution": 4.0,
    "other_absorption_scale": 0.0,
    "multi_scattering_factor": 1.0,
    "aerial_pespective_view_distance_scale": 2.0,
    "height_fog_contribution": 1.0,
}
GROUND_ALBEDO = unreal.Color(r=170, g=100, b=60, a=255)

FOG = {
    "fog_density": 0.003,
    "fog_height_falloff": 0.05,
    "fog_max_opacity": 0.7,
    "start_distance": 20000.0,
    "fog_inscattering_luminance": unreal.LinearColor(0.60, 0.30, 0.12, 1.0),
    "directional_inscattering_exponent": 8.0,
    "directional_inscattering_luminance": unreal.LinearColor(1.0, 0.62, 0.32, 1.0),
    "directional_inscattering_start_distance": 30000.0,
    "enable_volumetric_fog": True,
    "volumetric_fog_scattering_distribution": 0.6,
    "volumetric_fog_albedo": unreal.Color(r=255, g=205, b=160, a=255),
    "volumetric_fog_extinction_scale": 0.6,
    "volumetric_fog_distance": 250000.0,
}

CLOUDS = {"layer_bottom_altitude": 7.0, "layer_height": 1.0, "tracing_start_max_distance": 400.0}

EXPOSURE_BIAS = 0.4
BLOOM = 0.7
# The reference is graded warm and rich; white balance above 6500 K pushes the scene toward orange.
WHITE_TEMP = 7200.0
SATURATION = 1.15
SCREEN = (1500, 1000)  # 3:2 like the reference


def _tag(actor, label, folder):
    actor.set_actor_label(label)
    actor.set_folder_path(folder)
    return actor


def _spawn(cls, label, folder, loc=(0, 0, 0), rot=(0, 0, 0)):
    return _tag(EAS.spawn_actor_from_class(cls, V(*loc), R(*rot)), label, folder)


def _mesh_actor(mesh, label, folder, loc=(0, 0, 0), yaw=0.0, scale=(1, 1, 1)):
    actor = _spawn(unreal.StaticMeshActor, label, folder, loc, (0, yaw, 0))
    actor.set_actor_scale3d(V(*scale))
    actor.static_mesh_component.set_static_mesh(mesh)
    return actor


def open_level():
    """Opens the colony level with everything the generator owns removed, creating it on the first run."""
    if EAL.does_asset_exist(LEVEL_PATH):
        LES.load_level(LEVEL_PATH)
        ours = [a for a in EAS.get_all_level_actors() if str(a.get_folder_path()).split("/")[0] in FOLDERS]
        if ours:
            EAS.destroy_actors(ours)
    else:
        LES.new_level(LEVEL_PATH, False)


def build_ground(ground, rock_meshes):
    _mesh_actor(ground, "Terrain", "Terrain")
    for i, (shape, loc, yaw, scale) in enumerate(rocks.placements()):
        folder = "Rocks/Formations" if i < len(layout.ROCKS) else "Rocks/Boulders"
        _mesh_actor(rock_meshes[shape], f"Rock_{i:03d}_{shape}", folder, loc, yaw, scale)


def build_colony(kit):
    for name, (x, y, d) in layout.DOMES.items():
        s = d / 100.0
        _mesh_actor(kit["dome"], f"Dome_{name}", "Colony/Domes", (x * M, y * M, 0.0), 0.0, (s, s, s))
    tx, ty, _ = layout.TERMINAL
    _mesh_actor(kit["terminal"], "Terminal", "Colony", (tx * M, ty * M, 0.0))
    for i, ((x, y, *_), mesh) in enumerate(zip(layout.TOWERS, kit["towers"])):
        _mesh_actor(mesh, f"Tower_{i}", "Colony/Towers", (x * M, y * M, 0.0))
    _mesh_actor(kit["blocks"], "Blocks", "Colony")


def build_sky(cloud_material):
    # The light travels away from the sun, so it faces the opposite azimuth and points down.
    sun = _spawn(unreal.DirectionalLight, "Sun", "Environment", (0, 0, 5000),
                 (-layout.SUN_ELEVATION, layout.SUN_AZIMUTH + 180.0, 0))
    lc = sun.get_component_by_class(unreal.DirectionalLightComponent)
    lc.set_mobility(unreal.ComponentMobility.MOVABLE)
    lc.set_editor_property("intensity", layout.SUN_LUX)
    lc.set_editor_property("atmosphere_sun_light", True)
    lc.set_editor_property("light_source_angle", 0.53)
    try_set(lc, "cast_shadows_on_atmosphere", True)
    try_set(lc, "cast_cloud_shadows", True)

    atmo = _spawn(unreal.SkyAtmosphere, "SkyAtmosphere", "Environment")
    ac = atmo.get_component_by_class(unreal.SkyAtmosphereComponent)
    ac.set_editor_property("bottom_radius", PLANET_RADIUS_KM)
    ac.set_editor_property("ground_albedo", GROUND_ALBEDO)
    for key, value in ATMOSPHERE.items():
        try_set(ac, key, value)

    clouds = _spawn(unreal.VolumetricCloud, "VolumetricCloud", "Environment")
    cc = clouds.get_component_by_class(unreal.VolumetricCloudComponent)
    cc.set_editor_property("material", cloud_material)
    for key, value in CLOUDS.items():
        try_set(cc, key, value)

    sky = _spawn(unreal.SkyLight, "SkyLight", "Environment", (0, 0, 3000))
    sc = sky.get_component_by_class(unreal.SkyLightComponent)
    sc.set_mobility(unreal.ComponentMobility.MOVABLE)
    sc.set_editor_property("real_time_capture", True)

    fog = _spawn(unreal.ExponentialHeightFog, "DustHaze", "Environment")
    fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    for key, value in FOG.items():
        try_set(fc, key, value)


def build_camera_and_grade():
    cx, cy, cz = layout.CAMERA
    loc, rot = (cx * M, cy * M, cz * M), (layout.CAMERA_PITCH, 0.0, 0.0)
    cam = _spawn(unreal.CineCameraActor, "HeroCam", "Camera", loc, rot)
    cc = cam.get_cine_camera_component()
    fb = cc.get_editor_property("filmback")
    fb.set_editor_property("sensor_width", 36.0)
    fb.set_editor_property("sensor_height", 24.0)
    cc.set_editor_property("filmback", fb)
    cc.set_editor_property("current_focal_length", layout.FOCAL_MM)
    fs = cc.get_editor_property("focus_settings")
    fs.set_editor_property("focus_method", unreal.CameraFocusMethod.DISABLE)
    cc.set_editor_property("focus_settings", fs)

    px, py = layout.PLAYER_START
    _spawn(unreal.PlayerStart, "PlayerStart", "Camera", (px * M, py * M, (terrain.height(px, py) + 1.2) * M))

    ppv = _spawn(unreal.PostProcessVolume, "PostProcess", "Camera")
    ppv.set_editor_property("unbound", True)
    s = ppv.get_editor_property("settings")
    for key, value in (
            ("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL),
            ("auto_exposure_apply_physical_camera_exposure", False),
            ("auto_exposure_bias", EXPOSURE_BIAS),
            ("bloom_intensity", BLOOM),
            ("vignette_intensity", 0.3),
            ("white_temp", WHITE_TEMP),
            ("color_saturation", unreal.Vector4(SATURATION, SATURATION, SATURATION, 1.0)),
            ("lumen_final_gather_quality", 2.0),
            ("lumen_reflection_quality", 2.0),
            ("lumen_scene_lighting_quality", 2.0),
            ("lumen_front_layer_translucency_reflections", True)):
        try_set(s, f"override_{key}", True)
        try_set(s, key, value)
    ppv.set_editor_property("settings", s)

    UES.set_level_viewport_camera_info(V(*loc), R(*rot))
    return cam


def build(ground, rock_meshes, kit, cloud_material):
    build_ground(ground, rock_meshes)
    build_colony(kit)
    build_sky(cloud_material)
    build_camera_and_grade()
    LES.save_current_level()
    log(f"level saved -> {LEVEL_PATH}")
