"""Which takes the ship plays, from /Game/Audio/SFX (imported from SourceAudio by Scripts/audio_import.py).

To audition a take without rebuilding, swap it in the editor and press Play: the Ship actor's Audio component holds
the ship sounds, and the Door / Hatch components in BP_Module_Entry hold the door sounds. Make the choice stick by
changing it here, since the next build resets both.
"""
import unreal

from .util import EAL, ROOT, load_or_create, log

SFX = "/Game/Audio/SFX"
ATTENUATION = f"{ROOT}/Audio/ATT_ShipFixture"

# (open, close). The pressure door opens in 0.7 s, so its clunks land early; the hatch ramp takes 3 s.
DOOR = ("Door/DoorOpen_01", "Door/DoorClose_01")
HATCH = ("Door/DoorOpen_05", "Door/DoorClose_04")

# UShipAudioComponent property -> take.
SHIP = {
    "interior_ambience": "Ambience/ShipInteriorLoop_01",
    "drive_hum": "Drive/DriveHumLoop_01",
    "surge_engage_sound": "Drive/SurgeEngage_02",
    "surge_release_sound": "Drive/SurgeDisengage_03",
    "helm_engage_sound": "Helm/HelmEngage_02",
    "helm_leave_sound": "Helm/HelmEngage_01",
}


def sound(name):
    path = f"{SFX}/{name}"
    if not EAL.does_asset_exist(path):
        unreal.log_warning(f"[ShipKit] missing sound {path}; run `python3 Scripts/sfx.py import` from WSL")
        return None
    return EAL.load_asset(path)


def attenuation():
    """For sounds fixed in the ship, like doors: full volume within a doorway's reach, gone about 35 m away."""
    att = load_or_create(ATTENUATION, unreal.SoundAttenuation, unreal.SoundAttenuationFactory())
    settings = att.get_editor_property("attenuation")
    settings.set_editor_property("attenuate", True)
    settings.set_editor_property("spatialize", True)
    settings.set_editor_property("attenuation_shape", unreal.AttenuationShape.SPHERE)
    settings.set_editor_property("attenuation_shape_extents", unreal.Vector(300.0, 0.0, 0.0))
    settings.set_editor_property("falloff_distance", 3500.0)
    settings.set_editor_property("distance_algorithm", unreal.AttenuationDistanceModel.NATURAL_SOUND)
    settings.set_editor_property("d_b_attenuation_at_max", -50.0)
    att.set_editor_property("attenuation", settings)
    EAL.save_loaded_asset(att)
    return att


def apply_to_ship(ship):
    comp = ship.get_component_by_class(unreal.ShipAudioComponent)
    if comp is None:
        unreal.log_warning("[ShipKit] Ship has no Audio component; rebuild the C++ module")
        return
    for prop, name in SHIP.items():
        comp.set_editor_property(prop, sound(name))
    log(f"ship sounds: {', '.join(SHIP.values())}")
