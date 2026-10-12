"""Blueprints and catalogue data assets for fixtures and modules.

Existing assets are reused and their generated components replaced, so references from levels and other
assets survive a rebuild. Components added by hand in the Blueprint editor are also cleared on rebuild.
"""
import unreal

from . import audio
from .geo import bake, frame
from .util import AT, EAL, ROOT, V, V2, load_or_create, log

SDS = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
BFL = unreal.SubobjectDataBlueprintFunctionLibrary

MESH_FOLDER = f"{ROOT}/Meshes"
FIXTURE_FOLDER = f"{ROOT}/Fixtures"
MODULE_FOLDER = f"{ROOT}/Modules"

FACES = {"Forward": unreal.ShipCellFace.FORWARD, "Right": unreal.ShipCellFace.RIGHT,
         "Back": unreal.ShipCellFace.BACK, "Left": unreal.ShipCellFace.LEFT,
         "Up": unreal.ShipCellFace.UP, "Down": unreal.ShipCellFace.DOWN}


def _blueprint(path, parent):
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", parent)
    return load_or_create(path, unreal.Blueprint, factory)


def _reset_components(bp):
    """Removes every non-native component; returns the actor's handle and the native root's handle."""
    handles = SDS.k2_gather_subobject_data_for_blueprint(bp)
    root, doomed = None, []
    for h in handles[1:]:
        data = BFL.get_data(h)
        if BFL.is_native_component(data) or BFL.is_inherited_component(data):
            if BFL.is_root_component(data):
                root = h
        else:
            doomed.append(h)
    if doomed:
        SDS.delete_subobjects(handles[0], doomed, bp)
    return handles[0], root


def _add(bp, root, cls, name):
    handle, fail = SDS.add_new_subobject(unreal.AddNewSubobjectParams(
        parent_handle=root, new_class=cls, blueprint_context=bp))
    if not BFL.is_handle_valid(handle):
        raise RuntimeError(f"couldn't add {name} to {bp.get_name()}: {fail}")
    SDS.rename_subobject(handle, name)
    return BFL.get_associated_object(BFL.get_data(handle))


def _place(comp, xf, scale=(1, 1, 1)):
    comp.set_editor_property("relative_location", xf.translation)
    comp.set_editor_property("relative_rotation", xf.rotation.rotator())
    comp.set_editor_property("relative_scale3d", V(*scale))


def _rect_light(comp, c):
    comp.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    comp.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
    comp.set_editor_property("intensity", c["intensity"])
    comp.set_editor_property("source_width", c["width"])
    comp.set_editor_property("source_height", c["height"])
    comp.set_editor_property("barn_door_angle", c.get("barn", 60.0))
    comp.set_editor_property("barn_door_length", 8.0)
    comp.set_editor_property("attenuation_radius", c.get("radius", 700.0))
    comp.set_editor_property("cast_shadows", c["shadows"])
    r, g, b = c.get("color", (242, 247, 255))
    comp.set_editor_property("light_color", unreal.Color(r=r, g=g, b=b, a=255))


def _build_components(bp, components, meshes, fixtures, materials=None):
    actor, root = _reset_components(bp)
    for c in components:
        kind = c["kind"]
        if kind == "mesh":
            comp = _add(bp, root, unreal.StaticMeshComponent, c["name"])
            comp.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE if c.get("movable")
                                     else unreal.ComponentMobility.STATIC)
            comp.set_editor_property("static_mesh", meshes[c["part"]])
            _place(comp, c["xf"], c["scale"])
        elif kind == "rect":
            comp = _add(bp, root, unreal.RectLightComponent, c["name"])
            _rect_light(comp, c)
            _place(comp, c["xf"])
        elif kind == "hardpoint":
            comp = _add(bp, root, unreal.ShipHardpointComponent, c["name"])
            comp.set_editor_property("slot_type", c["slot"])
            comp.set_editor_property("extent", V2(*c["extent"]))
            if c["default"]:
                comp.set_editor_property("default_fixture", fixtures[c["default"]])
            _place(comp, c["xf"])
        elif kind == "camera":
            comp = _add(bp, root, unreal.CameraComponent, c["name"])
            comp.set_editor_property("field_of_view", c["fov"])
            comp.set_editor_property("constrain_aspect_ratio", False)
            _place(comp, c["xf"])
        elif kind == "box":
            comp = _add(bp, root, unreal.BoxComponent, c["name"])
            comp.set_editor_property("box_extent", V(*c["extent"]))
            comp.set_collision_profile_name("Trigger")
            _place(comp, c["xf"])
        elif kind == "door":
            comp = _add(bp, actor, unreal.ShipSlidingDoorComponent, c["name"])
            leaves = []
            for leaf in c["leaves"]:
                pitch, yaw, roll = leaf[2] if len(leaf) > 2 else (0.0, 0.0, 0.0)
                leaves.append(unreal.ShipDoorLeaf(component=leaf[0], open_offset=V(*leaf[1]),
                                                  open_rotation=unreal.Rotator(roll=roll, pitch=pitch, yaw=yaw)))
            comp.set_editor_property("leaves", leaves)
            comp.set_editor_property("trigger", c["trigger"] or "")
            comp.set_editor_property("locked", c.get("locked", False))
            comp.set_editor_property("open_seconds", c.get("seconds", 0.7))
            if c["lamp"]:
                comp.set_editor_property("status_lamp", c["lamp"])
                comp.set_editor_property("open_lamp_material", materials[c["open_slot"]])
                comp.set_editor_property("closed_lamp_material", materials[c["closed_slot"]])
            open_sound, close_sound = c.get("sounds") or audio.DOOR
            comp.set_editor_property("open_sound", audio.sound(open_sound))
            comp.set_editor_property("close_sound", audio.sound(close_sound))
            comp.set_editor_property("sound_attenuation", audio.attenuation())
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    EAL.save_loaded_asset(bp)


def _definition(path, cls, display, description, category):
    factory = unreal.DataAssetFactory()
    factory.set_editor_property("data_asset_class", cls)
    da = load_or_create(path, cls, factory)
    da.set_editor_property("display_name", display)
    da.set_editor_property("description", description)
    da.set_editor_property("category", category)
    return da


def build_fixtures(fixtures, materials):
    """Bakes fixture meshes, then makes BP_Fixture_* and DA_Fixture_* for each. Returns {key: definition}."""
    defs = {}
    for fx in fixtures:
        sm = bake(fx.part, f"{MESH_FOLDER}/Fixtures", materials)
        bp = _blueprint(f"{FIXTURE_FOLDER}/BP_Fixture_{fx.key}", unreal.ShipFixture)
        comps = [{"kind": "mesh", "name": "Mesh", "part": fx.part.name, "xf": unreal.Transform(), "scale": (1, 1, 1)}]
        for name, loc, direction, width, height, intensity in fx.lights:
            comps.append({"kind": "rect", "name": f"{name}Light", "xf": frame(loc, direction, (0, 1, 0)),
                          "width": width, "height": height, "intensity": intensity, "shadows": False, "barn": 80.0})
        _build_components(bp, comps, {fx.part.name: sm}, {})
        da = _definition(f"{FIXTURE_FOLDER}/DA_Fixture_{fx.key}", unreal.ShipFixtureDefinition,
                         fx.display, fx.description, fx.category)
        da.set_editor_property("fixture_class", bp.generated_class())
        da.set_editor_property("slot_types", fx.slots)
        EAL.save_loaded_asset(da)
        defs[fx.key] = da
        log(f"fixture {fx.key} ready")
    return defs


def build_modules(modules, shared_parts, materials, fixture_defs):
    """Bakes module meshes, then makes BP_Module_* and DA_Module_* for each. Returns {key: definition}."""
    meshes = {p.name: bake(p, f"{MESH_FOLDER}/Modules", materials) for p in shared_parts}
    defs = {}
    for mod in modules:
        for part in mod.spec.parts:
            meshes[part.name] = bake(part, f"{MESH_FOLDER}/Modules", materials)
        bp = _blueprint(f"{MODULE_FOLDER}/BP_Module_{mod.key}", unreal.ShipModule)
        _build_components(bp, mod.spec.components, meshes, fixture_defs, materials)
        da = _definition(f"{MODULE_FOLDER}/DA_Module_{mod.key}", unreal.ShipModuleDefinition,
                         mod.display, mod.description, mod.category)
        da.set_editor_property("module_class", bp.generated_class())
        da.set_editor_property("occupied_cells", [unreal.IntVector(0, 0, 0)])
        da.set_editor_property("connectors", [
            unreal.ShipConnector(cell=unreal.IntVector(0, 0, 0), face=FACES[face], connector_type=kind)
            for face, kind in mod.connectors])
        EAL.save_loaded_asset(da)
        defs[mod.key] = da
        log(f"module {mod.key} ready")
    return defs
