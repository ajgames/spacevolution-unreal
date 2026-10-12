"""First-person player: Enhanced Input assets, the character and controller Blueprints, and the game mode.

Assets are regenerated in place under /Game/Player; edit bindings here (or rebind in the mapping context and
stop running this step) so a rebuild doesn't undo them.
"""
import unreal

from .util import EAL, load_or_create, log

FOLDER = "/Game/Player"
INPUT_FOLDER = f"{FOLDER}/Input"
VT = unreal.InputActionValueType


def _action(name, value_type, description, cumulative=False):
    ia = load_or_create(f"{INPUT_FOLDER}/{name}", unreal.InputAction, unreal.InputAction_Factory())
    ia.set_editor_property("value_type", value_type)
    ia.set_editor_property("action_description", description)
    if cumulative:
        # W and S both held cancel out instead of the larger one winning.
        ia.set_editor_property("accumulation_behavior", unreal.InputActionAccumulationBehavior.CUMULATIVE)
    EAL.save_loaded_asset(ia)
    return ia


def _key(name):
    k = unreal.Key()
    k.set_editor_property("key_name", name)
    return k


def _negate(imc, x=False, y=False, z=False):
    m = unreal.new_object(unreal.InputModifierNegate, outer=imc)
    m.set_editor_property("x", x)
    m.set_editor_property("y", y)
    m.set_editor_property("z", z)
    return m


def _swizzle(imc, order=unreal.InputAxisSwizzle.YXZ):
    """YXZ moves a 1D key onto Y; ZYX moves it onto Z."""
    m = unreal.new_object(unreal.InputModifierSwizzleAxis, outer=imc)
    m.set_editor_property("order", order)
    return m


def _scalar(imc, x, y=None, z=1.0):
    m = unreal.new_object(unreal.InputModifierScalar, outer=imc)
    m.set_editor_property("scalar", unreal.Vector(x, x if y is None else y, z))
    return m


def _dead_zone(imc):
    m = unreal.new_object(unreal.InputModifierDeadZone, outer=imc)
    m.set_editor_property("lower_threshold", 0.18)
    return m


def _stick_rate(imc, degrees_per_second):
    """Thumbsticks report a rate, so scale by frame time to make look speed framerate independent."""
    per_dt = unreal.new_object(unreal.InputModifierScaleByDeltaTime, outer=imc)
    scale = unreal.new_object(unreal.InputModifierScalar, outer=imc)
    # Legacy look scales (2.5x yaw, -2.5x pitch) are on in this project, hence the division.
    scale.set_editor_property("scalar", unreal.Vector(degrees_per_second / 2.5, degrees_per_second / 2.5, 1.0))
    return [per_dt, scale]


def _map(imc, action, key, modifiers=()):
    return unreal.EnhancedActionKeyMapping(action=action, key=_key(key), modifiers=list(modifiers))


def build_input():
    move = _action("IA_Move", VT.AXIS2D, "Walk", cumulative=True)
    look = _action("IA_Look", VT.AXIS2D, "Look around")
    jump = _action("IA_Jump", VT.BOOLEAN, "Jump")
    sprint = _action("IA_Sprint", VT.BOOLEAN, "Sprint")

    imc = load_or_create(f"{INPUT_FOLDER}/IMC_Crew", unreal.InputMappingContext, unreal.InputMappingContext_Factory())
    mappings = [
        _map(imc, move, "W", [_swizzle(imc)]),
        _map(imc, move, "S", [_swizzle(imc), _negate(imc, y=True)]),
        _map(imc, move, "D"),
        _map(imc, move, "A", [_negate(imc, x=True)]),
        _map(imc, move, "Gamepad_Left2D", [_dead_zone(imc)]),
        # Pitch is already inverted by the legacy -2.5 scale, so negating Y gives mouse-up = look-up.
        _map(imc, look, "Mouse2D", [_negate(imc, y=True)]),
        _map(imc, look, "Gamepad_Right2D", [_dead_zone(imc), _negate(imc, y=True)] + _stick_rate(imc, 150.0)),
        _map(imc, jump, "SpaceBar"),
        _map(imc, jump, "Gamepad_FaceButton_Bottom"),
        _map(imc, sprint, "LeftShift"),
        _map(imc, sprint, "Gamepad_LeftThumbstick"),
    ]
    imc.set_editor_property("default_key_mappings", unreal.InputMappingContextMappingData(mappings=mappings))
    imc.set_editor_property("context_description", "Crew on foot")
    EAL.save_loaded_asset(imc)
    return imc, move, look, jump, sprint


def build_helm_input():
    """Zero-point helm: shadows the walking keys while piloting (higher priority, consumed)."""
    SW = unreal.InputAxisSwizzle
    move = _action("IA_HelmMove", VT.AXIS3D, "Fly: X forward, Y right, Z up", cumulative=True)
    steer = _action("IA_HelmSteer", VT.AXIS2D, "Steer: yaw and pitch, degrees")
    roll = _action("IA_HelmRoll", VT.AXIS1D, "Roll", cumulative=True)
    surge = _action("IA_HelmSurge", VT.BOOLEAN, "Surge the drive")
    imc = load_or_create(f"{INPUT_FOLDER}/IMC_Helm", unreal.InputMappingContext, unreal.InputMappingContext_Factory())
    mappings = [
        _map(imc, move, "W"),
        _map(imc, move, "S", [_negate(imc, x=True)]),
        _map(imc, move, "D", [_swizzle(imc)]),
        _map(imc, move, "A", [_swizzle(imc), _negate(imc, y=True)]),
        _map(imc, move, "SpaceBar", [_swizzle(imc, SW.ZYX)]),
        _map(imc, move, "LeftControl", [_swizzle(imc, SW.ZYX), _negate(imc, z=True)]),
        _map(imc, move, "Gamepad_Left2D", [_dead_zone(imc), _swizzle(imc)]),  # stick up = forward
        _map(imc, move, "Gamepad_RightTriggerAxis", [_swizzle(imc, SW.ZYX)]),
        _map(imc, move, "Gamepad_LeftTriggerAxis", [_swizzle(imc, SW.ZYX), _negate(imc, z=True)]),
        # Mouse up = nose up. Mouse counts become degrees; sticks become degrees per second.
        _map(imc, steer, "Mouse2D", [_scalar(imc, 0.07)]),
        _map(imc, steer, "Gamepad_Right2D", [_dead_zone(imc), unreal.new_object(unreal.InputModifierScaleByDeltaTime, outer=imc),
                                             _scalar(imc, 95.0, 70.0)]),
        _map(imc, roll, "E"),
        _map(imc, roll, "Q", [_negate(imc, x=True)]),
        _map(imc, roll, "Gamepad_RightShoulder"),
        _map(imc, roll, "Gamepad_LeftShoulder", [_negate(imc, x=True)]),
        _map(imc, surge, "LeftShift"),
        _map(imc, surge, "Gamepad_FaceButton_Bottom"),
    ]
    imc.set_editor_property("default_key_mappings", unreal.InputMappingContextMappingData(mappings=mappings))
    imc.set_editor_property("context_description", "Zero-point helm")
    EAL.save_loaded_asset(imc)
    return {"helm_mapping_context": imc, "helm_move_action": move, "helm_steer_action": steer,
            "helm_roll_action": roll, "helm_surge_action": surge}


def build_interface_input():
    """Interface keys live on the player controller, so they work whatever the player is controlling."""
    overlay = _action("IA_TogglePerformanceOverlay", VT.BOOLEAN, "Cycle the performance overlay (full, compact, off)")
    helm = _action("IA_ToggleHelm", VT.BOOLEAN, "Take or leave the helm")
    imc = load_or_create(f"{INPUT_FOLDER}/IMC_Interface", unreal.InputMappingContext,
                         unreal.InputMappingContext_Factory())
    mappings = [
        _map(imc, overlay, "F6"),  # F1-F5 and F9 are engine debug keys
        _map(imc, overlay, "Gamepad_Special_Left"),
        _map(imc, helm, "F"),
        _map(imc, helm, "Gamepad_FaceButton_Top"),
    ]
    imc.set_editor_property("default_key_mappings", unreal.InputMappingContextMappingData(mappings=mappings))
    imc.set_editor_property("context_description", "Interface")
    EAL.save_loaded_asset(imc)
    return imc, overlay, helm


def _blueprint(path, parent, defaults):
    """Blueprint subclass with the given class defaults."""
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


def build():
    imc, move, look, jump, sprint = build_input()
    character = _blueprint(f"{FOLDER}/BP_CrewCharacter", unreal.SpacevolutionCharacter, {
        "default_mapping_context": imc, "move_action": move, "look_action": look,
        "jump_action": jump, "sprint_action": sprint})
    interface_imc, overlay, helm = build_interface_input()
    controller = _blueprint(f"{FOLDER}/BP_CrewPlayerController", unreal.SpacevolutionPlayerController, {
        "interface_mapping_context": interface_imc, "toggle_performance_overlay_action": overlay,
        "toggle_helm_action": helm, **build_helm_input()})
    mode = _blueprint(f"{FOLDER}/BP_ShipGameMode", unreal.SpacevolutionGameMode, {
        "default_pawn_class": character.generated_class(),
        "player_controller_class": controller.generated_class()})
    log("player character, controller and game mode ready")
    return mode
