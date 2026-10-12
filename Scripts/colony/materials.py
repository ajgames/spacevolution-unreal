"""Colony materials.

Building finishes are instances of the ship kit's surface and glass masters. The ground gets its own master:
world-space sandstone strata on steep faces and sand wherever the surface faces up, so terrain and every rock
formation share one set of layers with no UVs. The sky gets a thin, wind-stretched high cloud layer.
"""
import unreal

from ship import materials as ship_materials
from ship.materials import _expr, _math, _new_material, _scalar, _vector
from .util import EAL, MEL, ROOT, load_or_create, try_set

FOLDER = f"{ROOT}/Materials"

# name: (base colour, roughness, metallic, emissive colour, emissive strength, extra scalar params)
FINISHES = {
    "Concrete":   ((0.42, 0.36, 0.30), 0.75, 0.0, None, 0.0, {"ColorVariation": 0.08, "RoughnessVariation": 0.10}),
    "Hull":       ((0.62, 0.60, 0.57), 0.40, 0.0, None, 0.0, {"ColorVariation": 0.05}),
    "TowerMetal": ((0.86, 0.72, 0.54), 0.18, 1.0, None, 0.0, {"RoughnessVariation": 0.05, "ColorVariation": 0.03}),
    "TowerDark":  ((0.05, 0.05, 0.055), 0.28, 1.0, None, 0.0, {}),
    "Frame":      ((0.55, 0.50, 0.42), 0.30, 1.0, None, 0.0, {}),
    "WindowWarm": ((0.04, 0.035, 0.03), 0.30, 0.0, (1.0, 0.62, 0.32), 2.5, {}),
}
GLASS = {"Tint": (0.85, 0.75, 0.62), "Opacity": 0.5, "Roughness": 0.05, "Specular": 0.8}

# name: (slope where sand starts, slope where it's all sand) as the surface normal's Z
GROUNDS = {"Sand": (0.55, 0.78), "Rock": (0.86, 0.97)}

GROUND_HLSL = """
struct FGround
{
    float Hash(float3 p)
    {
        p = frac(p * 0.3183099 + 0.1);
        p *= 17.0;
        return frac(p.x * p.y * p.z * (p.x + p.y + p.z));
    }
    float Noise(float3 x)
    {
        float3 i = floor(x);
        float3 f = frac(x);
        f = f * f * (3.0 - 2.0 * f);
        return lerp(lerp(lerp(Hash(i), Hash(i + float3(1, 0, 0)), f.x),
                         lerp(Hash(i + float3(0, 1, 0)), Hash(i + float3(1, 1, 0)), f.x), f.y),
                    lerp(lerp(Hash(i + float3(0, 0, 1)), Hash(i + float3(1, 0, 1)), f.x),
                         lerp(Hash(i + float3(0, 1, 1)), Hash(i + float3(1, 1, 1)), f.x), f.y), f.z);
    }
    float Fbm(float3 p)
    {
        float s = 0.0;
        float a = 0.5;
        for (int k = 0; k < 4; k++)
        {
            s += a * Noise(p);
            p = p * 2.03 + 17.1;
            a *= 0.5;
        }
        return s;
    }
};
FGround G;
float3 m = WP * 0.01;
// Strata: horizontal layers whose boundaries wander a little, each with its own shade.
float wander = (G.Fbm(m * 0.004) - 0.5) * BandWarp + (G.Fbm(m * 0.05) - 0.5) * BandWarp * 0.15;
float z = (m.z + wander) / BandHeight;
float layer = floor(z);
float3 rock = lerp(RockA.rgb, RockB.rgb, G.Hash(float3(layer, 0.37, 1.7)));
rock = lerp(rock, RockPale.rgb, step(0.82, G.Hash(float3(layer, 4.1, 0.2))));
rock *= 0.82 + 0.36 * G.Fbm(m * float3(0.08, 0.08, 0.5));
rock *= lerp(1.0, 0.7, smoothstep(0.85, 1.0, frac(z)));
// Sand: two shades at large scale and a little speckle, settling wherever the surface faces up.
float3 sand = lerp(SandA.rgb, SandB.rgb, G.Fbm(m * 0.01));
sand *= 0.92 + 0.16 * G.Noise(m * 0.7);
float settle = smoothstep(SlopeLo, SlopeHi, N.z + (G.Noise(m * 0.2) - 0.5) * 0.15);
return lerp(rock, sand, settle);
"""

# Thin high cloud: Perlin-Worley noise stretched across the view so it forms long streaks.
CLOUD_HLSL = """
float3 km = P * 1e-5;
float3 q = float3(km.x / Scale, km.y / (Scale * Stretch), km.z / (Scale * 0.6));
float n = Texture3DSampleLevel(Tex, TexSampler, q + 0.21, 0).r * 0.62
        + Texture3DSampleLevel(Tex, TexSampler, q * 3.3 + 0.57, 0).g * 0.38;
float cover = saturate((n - (1.0 - Coverage)) / Softness);
float shape = saturate(H / 0.25) * saturate((1.0 - H) / 0.45);
return cover * shape;
"""


def _instance(name, parent):
    """Instance under the colony's folder; its overrides are cleared so callers set exactly what they want."""
    mi = load_or_create(f"{FOLDER}/{name}", unreal.MaterialInstanceConstant,
                        unreal.MaterialInstanceConstantFactoryNew())
    mi.set_editor_property("parent", parent)
    MEL.clear_all_material_instance_parameters(mi)
    return mi


def _custom(m, code, output_type, description, inputs, x, y):
    custom = _expr(m, unreal.MaterialExpressionCustom, x, y)
    custom.set_editor_property("code", code)
    custom.set_editor_property("output_type", output_type)
    custom.set_editor_property("description", description)
    pins = []
    for name in inputs:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", name)
        pins.append(ci)
    custom.set_editor_property("inputs", pins)
    return custom


def build_ground_master():
    m = _new_material("M_ColonyGround", FOLDER)
    scalars = {"BandHeight": (6.0, "Strata"), "BandWarp": (8.0, "Strata"),
               "SlopeLo": (0.55, "Sand"), "SlopeHi": (0.78, "Sand")}
    vectors = {"RockA": ((0.35, 0.10, 0.035), "Strata"), "RockB": ((0.48, 0.17, 0.06), "Strata"),
               "RockPale": ((0.60, 0.32, 0.16), "Strata"),
               "SandA": ((0.50, 0.18, 0.06), "Sand"), "SandB": ((0.58, 0.25, 0.09), "Sand")}
    custom = _custom(m, GROUND_HLSL, unreal.CustomMaterialOutputType.CMOT_FLOAT3, "Ground",
                     ["WP", "N"] + list(scalars) + list(vectors), -500, 0)
    MEL.connect_material_expressions(_expr(m, unreal.MaterialExpressionWorldPosition, -800, -200), "", custom, "WP")
    MEL.connect_material_expressions(_expr(m, unreal.MaterialExpressionVertexNormalWS, -800, -100), "", custom, "N")
    y = 0
    for name, (value, group) in scalars.items():
        MEL.connect_material_expressions(_scalar(m, name, value, -800, y, group), "", custom, name)
        y += 80
    for name, (rgb, group) in vectors.items():
        MEL.connect_material_expressions(_vector(m, name, rgb, -800, y, group), "", custom, name)
        y += 110
    MEL.connect_material_property(custom, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(_scalar(m, "Roughness", 0.92, -300, 200), "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(_scalar(m, "Specular", 0.35, -300, 300), "", unreal.MaterialProperty.MP_SPECULAR)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    return m


def build_cloud_material():
    m = _new_material("M_ColonyClouds", FOLDER)
    m.set_editor_property("material_domain", unreal.MaterialDomain.MD_VOLUME)
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
    m.set_editor_property("used_with_volumetric_cloud", True)  # without it the cloud pass renders garbage

    tex = _expr(m, unreal.MaterialExpressionTextureObjectParameter, -1000, 0)
    tex.set_editor_property("parameter_name", "Noise")
    tex.set_editor_property("group", "Clouds")
    tex.set_editor_property("texture", EAL.load_asset("/Engine/EngineSky/VolumetricClouds/VT_PerlinWorley_Balanced"))
    tex.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
    attr = _expr(m, unreal.MaterialExpressionCloudSampleAttribute, -1000, -300)
    params = {"Coverage": 0.24, "Softness": 0.35, "Scale": 14.0, "Stretch": 5.0}
    custom = _custom(m, CLOUD_HLSL, unreal.CustomMaterialOutputType.CMOT_FLOAT1, "CloudDensity",
                     ["P", "H", "Tex"] + list(params), -600, 0)
    MEL.connect_material_expressions(_expr(m, unreal.MaterialExpressionWorldPosition, -1000, -150), "", custom, "P")
    MEL.connect_material_expressions(attr, "NormAltitudeInLayer", custom, "H")
    MEL.connect_material_expressions(tex, "", custom, "Tex")
    y = 200
    for name, value in params.items():
        MEL.connect_material_expressions(_scalar(m, name, value, -900, y, "Clouds"), "", custom, name)
        y += 90
    extinction = _math(m, unreal.MaterialExpressionMultiply, custom,
                       _scalar(m, "Extinction", 0.01, -600, 300, "Clouds"), -300, 100)
    MEL.connect_material_property(_vector(m, "Albedo", (0.95, 0.92, 0.88), -300, -150, "Clouds"), "",
                                  unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(extinction, "", unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
    adv = _expr(m, unreal.MaterialExpressionVolumetricAdvancedMaterialOutput, -200, 500)
    for key, value in (("const_phase_g", 0.7), ("const_phase_g2", -0.2), ("const_phase_blend", 0.3),
                       ("multi_scattering_approximation_octave_count", 2),
                       ("const_multi_scattering_contribution", 0.5), ("const_multi_scattering_occlusion", 0.4),
                       ("const_multi_scattering_eccentricity", 0.6), ("ground_contribution", True)):
        try_set(adv, key, value)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    mi = _instance("MI_ColonyClouds", m)  # tuning lives in the master's defaults above
    EAL.save_loaded_asset(mi)
    return mi


def build_all():
    """Returns {slot name: material} for every slot the colony meshes use, plus "Clouds"."""
    surface = EAL.load_asset(f"{ship_materials.FOLDER}/M_ShipSurface") or ship_materials.build_surface_master()
    glass_master = EAL.load_asset(f"{ship_materials.FOLDER}/M_ShipGlass") or ship_materials.build_glass()
    mats = {}
    for name, (base, rough, metal, em_col, em_str, extra) in FINISHES.items():
        mi = _instance(f"MI_Colony_{name}", surface)
        MEL.set_material_instance_vector_parameter_value(mi, "BaseColor", unreal.LinearColor(*base, 1.0))
        MEL.set_material_instance_scalar_parameter_value(mi, "Roughness", rough)
        MEL.set_material_instance_scalar_parameter_value(mi, "Metallic", metal)
        if em_col:
            MEL.set_material_instance_vector_parameter_value(mi, "EmissiveColor", unreal.LinearColor(*em_col, 1.0))
            MEL.set_material_instance_scalar_parameter_value(mi, "EmissiveStrength", em_str)
        for key, value in extra.items():
            MEL.set_material_instance_scalar_parameter_value(mi, key, value)
        MEL.update_material_instance(mi)
        EAL.save_loaded_asset(mi)
        mats[name] = mi

    glass = _instance("MI_Colony_DomeGlass", glass_master)
    MEL.set_material_instance_vector_parameter_value(glass, "Tint", unreal.LinearColor(*GLASS["Tint"], 1.0))
    for key in ("Opacity", "Roughness", "Specular"):
        MEL.set_material_instance_scalar_parameter_value(glass, key, GLASS[key])
    MEL.update_material_instance(glass)
    EAL.save_loaded_asset(glass)
    mats["DomeGlass"] = glass

    ground = build_ground_master()
    for name, (lo, hi) in GROUNDS.items():
        mi = _instance(f"MI_Colony_{name}", ground)
        MEL.set_material_instance_scalar_parameter_value(mi, "SlopeLo", lo)
        MEL.set_material_instance_scalar_parameter_value(mi, "SlopeHi", hi)
        MEL.update_material_instance(mi)
        EAL.save_loaded_asset(mi)
        mats[name] = mi

    mats["Clouds"] = build_cloud_material()
    return mats
