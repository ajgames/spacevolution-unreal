"""The arrival level: the ship 110 km up over the ocean, south of BiodiverCity, with the town level streamed in below.

The player starts aboard and is walked through taking the helm, flying down, landing at the spaceport and riding
off on the PWC-01 moored there. Sky, sea and town all come from the streamed town level; this one adds the ship and
its hull, the stars above the atmosphere, the landing pad marker, the moored rider, the director that hands out
objectives, and the game mode.
"""
import unreal

from ship import level as ship_level
from town import spaceport
from .util import EAL, EAS, LES, M, ROOT, UES, R, V, load_or_create, log, try_set

LEVEL_PATH = f"{ROOT}/Maps/L_Arrival"
TOWN_LEVEL = "/Game/Town/Maps/L_BiodiverCity"
FOLDERS = ("Ship", "Arrival")

START = (-28000.0, -900.0, 110000.0)   # metres: south of the town, over open sea, nose north toward it
PLAYER_START = (150.0, 0.0, 100.0)      # cm in the ship: just inside the entry bay, facing the helm
BACKDROP_CENTRE = (-14000.0, 0.0, 55000.0)
BACKDROP_RADIUS_CM = 2.0e7
PAD_ZONE = (300.0, 600.0)               # m: how far out and how high the ship can call for the autopilot


def _spawn(cls, label, folder, loc=(0, 0, 0), rot=(0, 0, 0)):
    actor = EAS.spawn_actor_from_class(cls, V(*loc), R(*rot))
    actor.set_actor_label(label)
    actor.set_folder_path(folder)
    return actor


def open_level():
    """Opens the arrival level with everything the generator owns removed, creating it on the first run, and makes
    sure the town is streamed in."""
    if EAL.does_asset_exist(LEVEL_PATH):
        LES.load_level(LEVEL_PATH)
        ships = [a for a in EAS.get_all_level_actors() if isinstance(a, unreal.Ship)]
        if ships:
            EAS.destroy_actors(ships)  # takes its modules and fixtures with it
        ours = [a for a in EAS.get_all_level_actors() if str(a.get_folder_path()).split("/")[0] in FOLDERS]
        if ours:
            EAS.destroy_actors(ours)
    else:
        LES.new_level(LEVEL_PATH, False)
    world = UES.get_editor_world()
    if not unreal.GameplayStatics.get_streaming_level(world, TOWN_LEVEL):
        unreal.EditorLevelUtils.add_level_to_world(world, TOWN_LEVEL, unreal.LevelStreamingAlwaysLoaded)
        log("town streamed in")


def _kit():
    """The ship kit's module and fixture definitions, by key, as ship.level lays them out."""
    modules = {key: EAL.load_asset(f"/Game/Ship/Modules/DA_Module_{key}") for key in ("Entry", "Corridor", "ObservationEnd")}
    fixtures = {}
    for path in EAL.list_assets("/Game/Ship/Fixtures", recursive=False):
        name = path.split(".")[-1]
        if name.startswith("DA_Fixture_"):
            fixtures[name[len("DA_Fixture_"):]] = EAL.load_asset(path)
    return modules, fixtures


def build_ship(hull_mesh):
    ship = ship_level.build_ship(*_kit())
    ship.set_folder_path("Ship")
    flight = ship.get_flight()
    for key, value in (("fly_in_world", True), ("planet_radius_km", 6360.0), ("min_altitude_km", 0.004),
                       ("min_cruise_km_per_second", 0.012), ("gear_height", 80.0)):
        flight.set_editor_property(key, value)
    ship.set_actor_location(V(*(c * M for c in START)), False, False)

    at = ship.get_actor_location()
    hull = _spawn(unreal.StaticMeshActor, "ShipHull", "Ship", (at.x, at.y, at.z))
    hull.static_mesh_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    hull.static_mesh_component.set_static_mesh(hull_mesh)
    hull.attach_to_actor(ship, "", unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                         unreal.AttachmentRule.KEEP_WORLD, False)

    start = ship.get_actor_transform().transform_location(V(*PLAYER_START))
    player_start = _spawn(unreal.PlayerStart, "PlayerStart", "Arrival", (start.x, start.y, start.z))
    player_start.set_editor_property("player_start_tag", "Arrival")
    return ship


def build_backdrop():
    """The kit's star backdrop, which the space environment keeps on the camera and fades out in the air."""
    mi = load_or_create(f"{ROOT}/Materials/MI_ArrivalBackdrop", unreal.MaterialInstanceConstant,
                        unreal.MaterialInstanceConstantFactoryNew())
    mi.set_editor_property("parent", EAL.load_asset("/Game/Ship/Materials/MI_SpaceBackdrop"))
    EAL.save_loaded_asset(mi)
    shell = _spawn(unreal.StaticMeshActor, "SpaceBackdrop", "Arrival", tuple(c * M for c in BACKDROP_CENTRE))
    shell.set_actor_scale3d(V(*(BACKDROP_RADIUS_CM / 50.0,) * 3))  # engine sphere has a 50 cm radius
    c = shell.static_mesh_component
    c.set_static_mesh(EAL.load_asset("/Engine/BasicShapes/Sphere"))
    c.set_material(0, mi)
    c.set_collision_profile_name("NoCollision")
    c.set_editor_property("generate_overlap_events", False)
    for key, value in (("cast_shadow", False), ("visible_in_ray_tracing", False), ("visible_in_reflections", False),
                       ("affect_distance_field_lighting", False), ("affect_dynamic_indirect_lighting", False),
                       ("visible_in_real_time_sky_captures", False), ("visible_in_reflection_captures", False),
                       ("translucency_sort_priority", -100)):
        try_set(c, key, value)
    return shell


def build_arrival(ship, backdrop):
    env = _spawn(unreal.SpaceEnvironment, "SpaceEnvironment", "Arrival")
    env.set_editor_property("planet_fixed", True)
    env.set_editor_property("ship", ship)
    env.set_editor_property("backdrop", backdrop)

    x, y, z = spaceport.landing_point()
    pad = _spawn(unreal.LandingPad, "LandingPad", "Arrival", (x * M, y * M, z * M))
    pad.set_editor_property("display_name", "BiodiverCity spaceport")
    pad.set_editor_property("zone_radius", PAD_ZONE[0] * M)
    pad.set_editor_property("zone_height", PAD_ZONE[1] * M)

    (mx, my, mz), yaw = spaceport.mooring()
    rider = EAL.load_asset("/Game/Town/Rider/BP_WaveRider")
    _spawn(rider.generated_class(), "PWC-01", "Arrival", (mx * M, my * M, mz * M), (0.0, yaw, 0.0))

    director = _spawn(unreal.ArrivalDirector, "ArrivalDirector", "Arrival")
    director.set_editor_property("ship", ship)


def build_game_mode():
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.ArrivalGameMode)
    bp = load_or_create(f"{ROOT}/BP_ArrivalGameMode", unreal.Blueprint, factory)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    cdo = unreal.get_default_object(bp.generated_class())
    cdo.set_editor_property("default_pawn_class", EAL.load_asset("/Game/Player/BP_CrewCharacter").generated_class())
    cdo.set_editor_property("player_controller_class", EAL.load_asset("/Game/Player/BP_CrewPlayerController").generated_class())
    cdo.set_editor_property("hud_class", unreal.WaveRiderHUD)
    # Compile again: spawned instances only copy defaults the compiler saw differ from the parent class.
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    EAL.save_loaded_asset(bp)
    return bp


def build(hull_mesh):
    ship = build_ship(hull_mesh)
    build_arrival(ship, build_backdrop())
    mode = build_game_mode()
    UES.get_editor_world().get_world_settings().set_editor_property("default_game_mode", mode.generated_class())
    # Look down the corridor toward the helm.
    eye = ship.get_actor_transform().transform_location(V(-150.0, 0.0, 170.0))
    UES.set_level_viewport_camera_info(eye, R(0.0, 0.0, 0.0))
    LES.save_current_level()
    log(f"level saved -> {LEVEL_PATH}")
