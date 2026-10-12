"""Town materials.

Buildings need no UVs: facades lay a window grid out in world space along each wall (floors at fixed heights),
and roofs, foliage and facades pick their colour from a small palette by the instance's random number, so one
instanced mesh shows a whole street of different houses. The ground reads its land use (paving, lawn, forest)
from vertex colours and its sand, seabed and seagrass from height. Hard finishes reuse the ship kit's master.
"""
import unreal

from ship import materials as ship_materials
from ship.materials import _expr, _math, _new_material, _scalar, _vector
from .util import EAL, MEL, ROOT, load_or_create, try_set

FOLDER = f"{ROOT}/Materials"

# Value noise shared by the custom nodes below.
NOISE_HLSL = """
struct FTownNoise
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
        return s / 0.9375;
    }
};
FTownNoise K;
float3 m = WP * 0.01;
"""

# Walls: a palette colour per building, with windows on a world-space grid along each wall. Returns the colour,
# and in alpha how much of the pixel is glass. The grid fades to its average as a window shrinks toward a pixel.
FACADE_HLSL = NOISE_HLSL + """
float3 n = normalize(N);
float3 wall = Rand < 0.34 ? WallA.rgb : (Rand < 0.67 ? WallB.rgb : WallC.rgb);
wall *= 0.93 + 0.14 * frac(Rand * 11.17);
wall *= 0.95 + 0.1 * K.Noise(m * 0.35);
if (abs(n.z) > 0.5)
{
    return float4(wall, 0.0);
}
float spacing = WindowSpacing * lerp(0.85, 1.25, frac(Rand * 3.71));
float ratio = WindowRatio * lerp(0.8, 1.15, frac(Rand * 5.33));
float2 t = normalize(float2(-n.y, n.x));
float u = dot(m.xy, t) / spacing;
float v = m.z / FloorHeight;
float fu = frac(u);
float fv = frac(v);
float glass = step(0.5 - ratio * 0.5, fu) * step(fu, 0.5 + ratio * 0.5) * step(Sill, fv) * step(fv, Head);
float band = Bands * (1.0 - step(0.07, fv));
float2 w = fwidth(float2(u, v));
float far = saturate(max(w.x, w.y) * 1.5 - 0.2);
glass = lerp(glass, ratio * (Head - Sill), far);
band *= 1.0 - far;
float3 col = lerp(wall, Glass.rgb * (0.8 + 0.4 * frac(Rand * 17.3)), glass) * (1.0 - band * 0.35);
return float4(col, glass);
"""

# Roofs: a palette colour per building, mottled, or a garden on a share of them.
ROOF_HLSL = NOISE_HLSL + """
float3 roof = Rand < 0.34 ? RoofA.rgb : (Rand < 0.67 ? RoofB.rgb : RoofC.rgb);
roof *= 0.9 + 0.2 * frac(Rand * 7.77);
roof *= 0.88 + 0.24 * K.Noise(m * 0.4);
float3 garden = lerp(GardenA.rgb, GardenB.rgb, K.Fbm(m * 0.15));
float green = step(frac(Rand * 13.7), GreenChance);
return lerp(roof, garden, green);
"""

# Foliage: a palette green per tree, darker underneath and in the folds.
FOLIAGE_HLSL = NOISE_HLSL + """
float3 n = normalize(N);
float3 leaf = Rand < 0.34 ? LeafA.rgb : (Rand < 0.67 ? LeafB.rgb : LeafC.rgb);
leaf *= 0.75 + 0.5 * K.Fbm(m * 0.6 + Rand * 13.0);
leaf *= lerp(0.45, 1.0, saturate(n.z * 0.6 + 0.5));
return leaf;
"""

# Ground: sand below the beach line, seabed and seagrass under water, and above it lawn, paving or forest from the
# land use in UV channel 1 (urban share, forest share). Paving takes the urban share of the ground in crisp patches.
GROUND_HLSL = NOISE_HLSL + """
float z = m.z;
float3 sand = lerp(SandA.rgb, SandB.rgb, K.Fbm(m * 0.04)) * (0.94 + 0.12 * K.Noise(m * 0.9));
float depth = max(-z, 0.0);
float seagrass = smoothstep(0.55, 0.68, K.Fbm(m * 0.012)) * smoothstep(2.0, 6.0, depth);
float3 seabed = lerp(sand, Seagrass.rgb, seagrass) * lerp(1.0, 0.7, saturate(depth / 40.0));

float3 lawn = lerp(GrassA.rgb, GrassB.rgb, K.Fbm(m * 0.025)) * (0.85 + 0.3 * K.Noise(m * 0.5));
float3 paving = lerp(PaveA.rgb, PaveB.rgb, K.Noise(m * 0.12)) * (0.92 + 0.16 * K.Noise(m * 1.3));
float urban = smoothstep(-0.04, 0.04, LU.x - K.Fbm(m * 0.018));
float3 forest = lerp(ForestA.rgb, ForestB.rgb, K.Fbm(m * 0.004)) * (0.55 + 0.7 * K.Fbm(m * 0.085));
float steep = 1.0 - smoothstep(0.35, 0.55, normalize(N).z);
float3 rock = lerp(RockA.rgb, RockB.rgb, K.Fbm(m * 0.03));
float3 land = lerp(lawn, paving, urban);
land = lerp(land, lerp(forest, rock, steep * 0.6), saturate(LU.y));

float beach = 1.0 - smoothstep(BeachTop - 0.25, BeachTop + 0.1, z + (K.Noise(m * 0.25) - 0.5) * 0.4);
float3 col = lerp(land, sand, beach);
col *= 1.0 - 0.3 * (1.0 - smoothstep(-0.1, 0.5, z));
return lerp(col, seabed, smoothstep(0.0, -0.3, z));
"""

# name: (wall A, B, C, glass, floor height m, window spacing m, window ratio, sill, head, bands, wall roughness)
FACADES = {
    "White":   ((0.82, 0.82, 0.80), (0.74, 0.75, 0.74), (0.86, 0.84, 0.78), (0.05, 0.08, 0.10),
                3.4, 3.0, 0.55, 0.2, 0.85, 0.6, 0.7),
    "Tower":   ((0.85, 0.86, 0.86), (0.78, 0.80, 0.82), (0.88, 0.87, 0.84), (0.06, 0.10, 0.13),
                3.6, 2.4, 0.72, 0.12, 0.9, 0.9, 0.55),
    "Village": ((0.85, 0.82, 0.74), (0.86, 0.72, 0.58), (0.70, 0.76, 0.78), (0.04, 0.05, 0.06),
                3.1, 3.2, 0.36, 0.3, 0.78, 0.0, 0.85),
    "Timber":  ((0.46, 0.30, 0.18), (0.55, 0.38, 0.22), (0.80, 0.78, 0.74), (0.05, 0.08, 0.09),
                4.2, 2.6, 0.65, 0.1, 0.9, 0.4, 0.75),
}
# name: (roof A, B, C, green chance)
ROOFS = {
    "Terracotta": ((0.50, 0.17, 0.08), (0.62, 0.27, 0.12), (0.42, 0.20, 0.13), 0.0),
    "Flat":       ((0.62, 0.62, 0.60), (0.50, 0.51, 0.52), (0.70, 0.69, 0.66), 0.35),
    "Green":      ((0.55, 0.55, 0.53), (0.60, 0.60, 0.58), (0.50, 0.50, 0.50), 0.85),
}
GARDEN = ((0.10, 0.22, 0.06), (0.20, 0.32, 0.09))
LEAVES = ((0.08, 0.20, 0.05), (0.12, 0.26, 0.06), (0.17, 0.27, 0.07))
PALM_LEAVES = ((0.17, 0.27, 0.07), (0.22, 0.30, 0.08), (0.14, 0.24, 0.06))

GROUND = {
    "SandA": (0.80, 0.74, 0.60), "SandB": (0.90, 0.85, 0.72), "Seagrass": (0.10, 0.16, 0.08),
    "GrassA": (0.12, 0.24, 0.06), "GrassB": (0.22, 0.32, 0.09),
    "PaveA": (0.36, 0.36, 0.34), "PaveB": (0.46, 0.45, 0.42),
    "ForestA": (0.06, 0.15, 0.04), "ForestB": (0.11, 0.20, 0.06),
    "RockA": (0.33, 0.29, 0.24), "RockB": (0.45, 0.40, 0.33),
}

# name: (base colour, roughness, metallic, emissive colour, emissive strength) on the ship kit's surface master
FINISHES = {
    "Concrete": ((0.80, 0.80, 0.78), 0.7, 0.0, None, 0.0),
    "Deck":     ((0.36, 0.37, 0.38), 0.8, 0.0, None, 0.0),
    "Rail":     ((0.85, 0.86, 0.87), 0.35, 1.0, None, 0.0),
    "Trunk":    ((0.22, 0.15, 0.09), 0.9, 0.0, None, 0.0),
    "PalmTrunk": ((0.42, 0.34, 0.24), 0.9, 0.0, None, 0.0),
    "Spire":    ((0.90, 0.90, 0.89), 0.3, 0.0, None, 0.0),
    "SpireGlass": ((0.38, 0.45, 0.50), 0.12, 0.0, None, 0.0),
    "SpireLight": ((0.9, 0.9, 0.9), 0.4, 0.0, (1.0, 0.85, 0.6), 6.0),
    "BoatHull": ((0.92, 0.93, 0.94), 0.25, 0.0, None, 0.0),
    # The spaceport.
    "PadLine":  ((0.90, 0.90, 0.88), 0.6, 0.0, None, 0.0),
    "PadMark":  ((0.85, 0.58, 0.06), 0.55, 0.0, None, 0.0),
    "PadLight": ((0.3, 0.2, 0.1), 0.4, 0.0, (1.0, 0.55, 0.15), 30.0),
    "BeaconMast": ((0.75, 0.76, 0.78), 0.35, 1.0, None, 0.0),
    "BoatDeck": ((0.55, 0.40, 0.26), 0.6, 0.0, None, 0.0),
    # The wave rider.
    "Carbon":   ((0.07, 0.072, 0.08), 0.28, 0.5, None, 0.0),
    "Gunmetal": ((0.34, 0.35, 0.38), 0.22, 1.0, None, 0.0),
    "Trim":     ((0.09, 0.09, 0.095), 0.4, 0.4, None, 0.0),
    "Turbine":  ((0.30, 0.31, 0.33), 0.35, 1.0, None, 0.0),
    "Seat":     ((0.02, 0.02, 0.022), 0.75, 0.0, None, 0.0),
    "LED":      ((0.10, 0.06, 0.02), 0.3, 0.0, (1.0, 0.50, 0.12), 14.0),
    "ThrusterGlow": ((0.10, 0.06, 0.02), 0.3, 0.0, (1.0, 0.45, 0.10), 14.0),
    "Suit":     ((0.018, 0.018, 0.02), 0.3, 0.3, None, 0.0),
    "Visor":    ((0.01, 0.01, 0.012), 0.05, 1.0, None, 0.0),
}


def _instance(name, parent):
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


def _mask(m, source, channels, x, y):
    e = _expr(m, unreal.MaterialExpressionComponentMask, x, y)
    for c in "rgba":
        e.set_editor_property(c, c in channels)
    MEL.connect_material_expressions(source, "", e, "")
    return e


def _wire_params(m, custom, scalars, vectors, x=-1100, y=0, group="Look"):
    for name, value in scalars.items():
        MEL.connect_material_expressions(_scalar(m, name, value, x, y, group), "", custom, name)
        y += 80
    for name, rgb in vectors.items():
        MEL.connect_material_expressions(_vector(m, name, rgb, x, y, group), "", custom, name)
        y += 110


def _custom_master(name, code, output_type, scalars, vectors, extra_inputs):
    """A material whose look is one custom node fed by world position, the vertex normal and the parameters."""
    m = _new_material(name, FOLDER)
    inputs = ["WP", "N"] + list(extra_inputs) + list(scalars) + list(vectors)
    custom = _custom(m, code, output_type, name, inputs, -600, 0)
    MEL.connect_material_expressions(_expr(m, unreal.MaterialExpressionWorldPosition, -1100, -400), "", custom, "WP")
    MEL.connect_material_expressions(_expr(m, unreal.MaterialExpressionVertexNormalWS, -1100, -300), "", custom, "N")
    for pin, (cls, props) in extra_inputs.items():
        e = _expr(m, cls, -1100, -200)
        for key, value in props.items():
            e.set_editor_property(key, value)
        MEL.connect_material_expressions(e, "", custom, pin)
    _wire_params(m, custom, scalars, vectors)
    return m, custom


def build_facade():
    scalars = {"FloorHeight": 3.4, "WindowSpacing": 3.0, "WindowRatio": 0.55, "Sill": 0.2, "Head": 0.85,
               "Bands": 0.5}
    vectors = {"WallA": (0.8, 0.8, 0.8), "WallB": (0.7, 0.7, 0.7), "WallC": (0.85, 0.85, 0.8),
               "Glass": (0.05, 0.08, 0.1)}
    m, custom = _custom_master("M_TownFacade", FACADE_HLSL, unreal.CustomMaterialOutputType.CMOT_FLOAT4,
                               scalars, vectors, {"Rand": (unreal.MaterialExpressionPerInstanceRandom, {})})
    colour = _mask(m, custom, "rgb", -300, -100)
    glass = _mask(m, custom, "a", -300, 100)
    rough = _expr(m, unreal.MaterialExpressionLinearInterpolate, -100, 200)
    MEL.connect_material_expressions(_scalar(m, "WallRoughness", 0.7, -400, 250), "", rough, "A")
    MEL.connect_material_expressions(_scalar(m, "GlassRoughness", 0.06, -400, 330), "", rough, "B")
    MEL.connect_material_expressions(glass, "", rough, "Alpha")
    spec = _expr(m, unreal.MaterialExpressionLinearInterpolate, -100, 400)
    spec.set_editor_property("const_a", 0.4)
    spec.set_editor_property("const_b", 0.9)
    MEL.connect_material_expressions(glass, "", spec, "Alpha")
    MEL.connect_material_property(colour, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(spec, "", unreal.MaterialProperty.MP_SPECULAR)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    return m


def build_roof():
    vectors = {"RoofA": (0.5, 0.2, 0.1), "RoofB": (0.6, 0.3, 0.1), "RoofC": (0.4, 0.2, 0.1),
               "GardenA": GARDEN[0], "GardenB": GARDEN[1]}
    m, custom = _custom_master("M_TownRoof", ROOF_HLSL, unreal.CustomMaterialOutputType.CMOT_FLOAT3,
                               {"GreenChance": 0.0}, vectors, {"Rand": (unreal.MaterialExpressionPerInstanceRandom, {})})
    MEL.connect_material_property(custom, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(_scalar(m, "Roughness", 0.8, -300, 200), "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    return m


def build_foliage():
    vectors = {"LeafA": LEAVES[0], "LeafB": LEAVES[1], "LeafC": LEAVES[2]}
    m, custom = _custom_master("M_TownFoliage", FOLIAGE_HLSL, unreal.CustomMaterialOutputType.CMOT_FLOAT3,
                               {}, vectors, {"Rand": (unreal.MaterialExpressionPerInstanceRandom, {})})
    MEL.connect_material_property(custom, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(_scalar(m, "Roughness", 0.75, -300, 200), "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(_scalar(m, "Specular", 0.3, -300, 300), "", unreal.MaterialProperty.MP_SPECULAR)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    return m


def build_ground():
    m, custom = _custom_master("M_TownGround", GROUND_HLSL, unreal.CustomMaterialOutputType.CMOT_FLOAT3,
                               {"BeachTop": 1.8}, GROUND, {"LU": (unreal.MaterialExpressionTextureCoordinate, {"coordinate_index": 1})})
    MEL.connect_material_property(custom, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(_scalar(m, "Roughness", 0.9, -300, 200), "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(_scalar(m, "Specular", 0.35, -300, 300), "", unreal.MaterialProperty.MP_SPECULAR)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    return m


# Spray: droplet noise streaming along the sheet (UV y), fading at its edges (UV x) and toward its end. Tube
# meshes wrap UV x round them, so they skip the edge fade.
SPRAY_HLSL = NOISE_HLSL.replace("float3 m = WP * 0.01;", "") + """
float flow = UV.y * 5.0 - T * 3.5;
float n = K.Fbm(float3(UV.x * 7.0, flow, T * 0.7));
float streak = K.Noise(float3(UV.x * 26.0, flow * 0.4, 1.3));
float edge = lerp(smoothstep(0.0, 0.3, UV.x) * (1.0 - smoothstep(0.7, 1.0, UV.x)), 1.0, Tube);
float along = smoothstep(0.0, 0.1, UV.y) * (1.0 - smoothstep(0.45, 1.0, UV.y));
return saturate(Spray * Density * edge * along * (n * 2.4 - 1.0 + streak * 0.7));
"""


def build_spray():
    m = _new_material("M_Spray", FOLDER)
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property("two_sided", True)
    # Lit by the sun per pixel, so spray catches the light white instead of going muddy in ambient light.
    try_set(m, "translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
    custom = _custom(m, SPRAY_HLSL, unreal.CustomMaterialOutputType.CMOT_FLOAT1, "Spray",
                     ["UV", "T", "Spray", "Tube", "Density"], -600, 0)
    MEL.connect_material_expressions(_expr(m, unreal.MaterialExpressionTextureCoordinate, -1000, -200), "", custom, "UV")
    MEL.connect_material_expressions(_expr(m, unreal.MaterialExpressionTime, -1000, -100), "", custom, "T")
    MEL.connect_material_expressions(_scalar(m, "Spray", 1.0, -1000, 0, "Spray"), "", custom, "Spray")
    MEL.connect_material_expressions(_scalar(m, "Tube", 0.0, -1000, 100, "Spray"), "", custom, "Tube")
    MEL.connect_material_expressions(_scalar(m, "Density", 1.0, -1000, 200, "Spray"), "", custom, "Density")
    colour = _vector(m, "Color", (0.9, 0.93, 0.95), -300, -200, "Spray")
    MEL.connect_material_property(colour, "", unreal.MaterialProperty.MP_BASE_COLOR)
    # A little glow of its own, as sunlit spray scatters light through itself.
    MEL.connect_material_property(_math(m, unreal.MaterialExpressionMultiply, colour,
                                        _scalar(m, "Glow", 0.6, -300, -50, "Spray"), -150, -100), "",
                                  unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.connect_material_property(custom, "", unreal.MaterialProperty.MP_OPACITY)
    MEL.connect_material_property(_scalar(m, "Roughness", 0.35, -300, 100, "Spray"), "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    return m


def build_beam():
    """Light thrown straight up from the spaceport beacon: additive, brightest where the view looks through the
    middle of the column, fading out toward the top, and out of the way when the view comes close."""
    m = _new_material("M_BeaconBeam", FOLDER)
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property("two_sided", True)
    code = """
float face = abs(dot(normalize(N), normalize(V)));
float fade = 1.0 - smoothstep(Base, Top, WP.z * 0.01);
fade *= smoothstep(Near, Near * 4.0, distance(Cam, WP) * 0.01);
return Color.rgb * Intensity * fade * (0.15 + 0.85 * face * face);
"""
    custom = _custom(m, code, unreal.CustomMaterialOutputType.CMOT_FLOAT3, "Beam",
                     ["N", "V", "WP", "Cam", "Base", "Top", "Near", "Color", "Intensity"], -500, 0)
    MEL.connect_material_expressions(_expr(m, unreal.MaterialExpressionVertexNormalWS, -900, -200), "", custom, "N")
    MEL.connect_material_expressions(_expr(m, unreal.MaterialExpressionCameraVectorWS, -900, -100), "", custom, "V")
    MEL.connect_material_expressions(_expr(m, unreal.MaterialExpressionWorldPosition, -900, 0), "", custom, "WP")
    MEL.connect_material_expressions(_expr(m, unreal.MaterialExpressionCameraPositionWS, -900, 50), "", custom, "Cam")
    MEL.connect_material_expressions(_scalar(m, "Near", 120.0, -900, 220, "Beam"), "", custom, "Near")
    MEL.connect_material_expressions(_scalar(m, "Base", 20.0, -900, 100, "Beam"), "", custom, "Base")
    MEL.connect_material_expressions(_scalar(m, "Top", 2600.0, -900, 180, "Beam"), "", custom, "Top")
    MEL.connect_material_expressions(_vector(m, "Color", (1.0, 0.6, 0.2), -900, 260, "Beam"), "", custom, "Color")
    MEL.connect_material_expressions(_scalar(m, "Intensity", 3.5, -900, 370, "Beam"), "", custom, "Intensity")
    MEL.connect_material_property(custom, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    return m


def _set(mi, scalars=None, vectors=None):
    for key, value in (scalars or {}).items():
        MEL.set_material_instance_scalar_parameter_value(mi, key, value)
    for key, rgb in (vectors or {}).items():
        MEL.set_material_instance_vector_parameter_value(mi, key, unreal.LinearColor(*rgb, 1.0))
    MEL.update_material_instance(mi)
    EAL.save_loaded_asset(mi)
    return mi


def build_all():
    """Returns {name: material}: Facade_*, Roof_*, Leaves, PalmLeaves, Ground and every finish."""
    mats = {}
    facade = build_facade()
    for name, (a, b, c, glass, floor, spacing, ratio, sill, head, bands, rough) in FACADES.items():
        mats[f"Facade_{name}"] = _set(_instance(f"MI_Facade_{name}", facade), {
            "FloorHeight": floor, "WindowSpacing": spacing, "WindowRatio": ratio, "Sill": sill, "Head": head,
            "Bands": bands, "WallRoughness": rough}, {"WallA": a, "WallB": b, "WallC": c, "Glass": glass})
    roof = build_roof()
    for name, (a, b, c, green) in ROOFS.items():
        mats[f"Roof_{name}"] = _set(_instance(f"MI_Roof_{name}", roof), {"GreenChance": green},
                                    {"RoofA": a, "RoofB": b, "RoofC": c})
    foliage = build_foliage()
    mats["Leaves"] = _set(_instance("MI_Leaves", foliage))
    mats["PalmLeaves"] = _set(_instance("MI_PalmLeaves", foliage), vectors=dict(zip(("LeafA", "LeafB", "LeafC"), PALM_LEAVES)))
    mats["Ground"] = _set(_instance("MI_Ground", build_ground()))
    mats["Beam"] = _set(_instance("MI_BeaconBeam", build_beam()))
    spray = build_spray()
    mats["Spray"] = _set(_instance("MI_Spray", spray))
    mats["Wake"] = _set(_instance("MI_Wake", spray), {"Tube": 1.0, "Density": 0.45})

    surface = EAL.load_asset(f"{ship_materials.FOLDER}/M_ShipSurface") or ship_materials.build_surface_master()
    for name, (base, rough, metal, em_col, em_str) in FINISHES.items():
        mi = _instance(f"MI_Town_{name}", surface)
        MEL.set_material_instance_vector_parameter_value(mi, "BaseColor", unreal.LinearColor(*base, 1.0))
        MEL.set_material_instance_scalar_parameter_value(mi, "Roughness", rough)
        MEL.set_material_instance_scalar_parameter_value(mi, "Metallic", metal)
        if em_col:
            MEL.set_material_instance_vector_parameter_value(mi, "EmissiveColor", unreal.LinearColor(*em_col, 1.0))
            MEL.set_material_instance_scalar_parameter_value(mi, "EmissiveStrength", em_str)
        MEL.update_material_instance(mi)
        EAL.save_loaded_asset(mi)
        mats[name] = mi
    return mats
