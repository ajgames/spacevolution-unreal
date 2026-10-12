"""The ocean surface: a flat grid that is dense in the middle and sparse toward the horizon (the AOcean actor
keeps its middle under the camera), and the Single Layer Water material that moves it.

The vertex displacement must match AOcean::Displace in C++ exactly, since riders sample the waves there:
Gerstner waves from the Wave0..7 parameters, damped near the islands by the Calm0..15 zones and faded out where
the grid gets too coarse to carry them. The pixel normals add the same waves at full strength plus small ripples,
and the foam comes from folding crests and from shallow water at the shore.
"""
import unreal

from colony.geo import Buffers, bake, graded
from ship.geo import Part
from ship.materials import _expr, _math, _new_material, _scalar, _vector
from .materials import NOISE_HLSL, _custom, _mask
from .util import EAL, MEL, ROOT, V, log, try_set

FOLDER = f"{ROOT}/Ocean"
EXTENT = 30000.0    # m from the middle of the grid
CORE = 200.0
STEP = 2.0
GROWTH = 1.045

MAX_WAVES = 8       # AOcean::MaxWaves
MAX_CALM = 16       # AOcean::MaxCalmZones

_ARRAYS = """
float4 W[8] = {Wave0, Wave1, Wave2, Wave3, Wave4, Wave5, Wave6, Wave7};
float4 C[16] = {Calm0, Calm1, Calm2, Calm3, Calm4, Calm5, Calm6, Calm7,
                Calm8, Calm9, Calm10, Calm11, Calm12, Calm13, Calm14, Calm15};
float2 p = P.xy * 0.01;
float open = 1.0;
for (int z = 0; z < 16; z++)
{
    if (C[z].w > 0.0)
    {
        open = min(open, smoothstep(C[z].z, C[z].w, distance(p, C[z].xy)));
    }
}
float calm = lerp(CalmFloor, 1.0, open);
"""

# Vertex offset in cm. Keep the waves in step with AOcean::Displace; the fade toward the coarse edge of the mesh and
# the planet's curvature are drawn only, as both are nothing near the view.
WPO_HLSL = _ARRAYS + """
float r = distance(p, Centre.xy);
float3 o = 0;
for (int i = 0; i < 8; i++)
{
    float4 w = W[i];
    if (w.w <= 0.0)
    {
        continue;
    }
    float k = 6.2831853 / w.z;
    float om = sqrt(9.81 * k);
    float fs = Fade * w.z;
    float a = w.w * calm * (1.0 - smoothstep(fs, fs * 1.6, r));
    float q = Steep / (k * w.w * Count);
    float s, c;
    sincos(k * dot(w.xy, p) - om * T + i * 2.39996, s, c);
    o.xy += q * a * w.xy * c;
    o.z += a * s;
}
// The sea curves away with the planet (visual only, like the fade: neither matters near the view).
o.z -= r * r / (2.0 * PlanetRadius);
return o * 100.0;
"""

# World normal (xyz) and foam (w). Waves fade from the normals only far away, where they'd sparkle.
SURFACE_HLSL = NOISE_HLSL.replace("float3 m = WP * 0.01;", "") + _ARRAYS + """
float dist = distance(CamPos, P) * 0.01;
float3 n = float3(0, 0, 1);
float jxx = 1, jyy = 1, jxy = 0;
for (int i = 0; i < 8; i++)
{
    float4 w = W[i];
    if (w.w <= 0.0)
    {
        continue;
    }
    float k = 6.2831853 / w.z;
    float om = sqrt(9.81 * k);
    float a = w.w * calm * (1.0 - smoothstep(80.0 * w.z, 200.0 * w.z, dist));
    float q = Steep / (k * w.w * Count);
    float s, c;
    sincos(k * dot(w.xy, p) - om * T + i * 2.39996, s, c);
    n.xy -= w.xy * k * a * c;
    n.z -= q * k * a * s;
    jxx -= q * k * a * w.x * w.x * s;
    jyy -= q * k * a * w.y * w.y * s;
    jxy -= q * k * a * w.x * w.y * s;
}
// Wind ripples, in the normals only: sixteen short waves spread about the wind, out of step with each other so
// they never line up into stripes. They ruffle even the sheltered canals, and fade out with distance.
float chop = lerp(0.5, 1.0, open);
for (int j = 0; j < 16; j++)
{
    float fj = j;
    float L = RippleScale * 0.5 * pow(1.17, fj);
    float k = 6.2831853 / L;
    float om = sqrt(9.81 * k);
    float ang = 0.4 + 1.25 * sin(fj * 2.39996);
    float2 d = float2(cos(ang), sin(ang));
    float a = RippleStrength * L * 0.01 * chop * (1.0 - smoothstep(25.0 * L, 70.0 * L, dist));
    n.xy -= d * k * a * cos(k * dot(d, p) - om * T + fj * 10.166);
}
float det = jxx * jyy - jxy * jxy;
float crest = saturate((FoamFold - det) * 2.5) * smoothstep(0.35, 0.75, K.Fbm(float3(p * 0.35, T * 0.15)));
// Shore foam where the water is shallow: the depth behind the surface, turned roughly into a vertical thickness.
float thick = max(SceneBehind - Depth, 0.0) * abs(View.z) * 0.01;
float shore = (1.0 - smoothstep(0.0, ShoreFoam, thick)) * smoothstep(0.3, 0.7, K.Fbm(float3(p * 0.6, T * 0.4)) + 0.25);
return float4(normalize(n), saturate(max(crest, shore)));
"""

# Per metre; the water shading works in centimetres, so they're scaled down on the way in.
WATER = {
    "Scattering": (0.0, 0.024, 0.048), "Absorption": (0.45, 0.085, 0.03), "FoamColor": (0.9, 0.93, 0.95),
}


def _wave_inputs(m, custom, x, y):
    for i in range(MAX_WAVES):
        MEL.connect_material_expressions(_vector(m, f"Wave{i}", (1.0, 0.0, 10.0), x, y, "Waves"), "RGBA", custom, f"Wave{i}")
        y += 60
    for i in range(MAX_CALM):
        MEL.connect_material_expressions(_vector(m, f"Calm{i}", (0.0, 0.0, 0.0), x, y, "Calm"), "RGBA", custom, f"Calm{i}")
        y += 60
    return y


def build_material():
    # Start from a fresh asset: clearing a water material's graph makes it fail to compile, noisily. Only the
    # level's ocean refers to it, and the level is cleared before this runs.
    if EAL.does_asset_exist(f"{FOLDER}/M_Ocean"):
        EAL.delete_asset(f"{FOLDER}/M_Ocean")
    m = _new_material("M_Ocean", FOLDER)
    # The water output goes in first so every compile along the way is valid water.
    water = _expr(m, unreal.MaterialExpressionSingleLayerWaterMaterialOutput, -300, 900)
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    m.set_editor_property("tangent_space_normal", False)
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_SINGLE_LAYER_WATER)

    wave_pins = [f"Wave{i}" for i in range(MAX_WAVES)] + [f"Calm{i}" for i in range(MAX_CALM)]
    shared = {"T": ("OceanTime", 0.0), "Steep": ("Steepness", 0.55), "Count": ("WaveCount", 8.0),
              "CalmFloor": ("CalmFloor", 0.1)}

    undisplaced = _expr(m, unreal.MaterialExpressionWorldPosition, -2400, -600)
    undisplaced.set_editor_property("world_position_shader_offset",
                                    unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
    scalars = {name: _scalar(m, param, value, -2400, -500 + 80 * k, "Ocean")
               for k, (name, (param, value)) in enumerate(shared.items())}

    # Vertex displacement.
    wpo = _custom(m, WPO_HLSL, unreal.CustomMaterialOutputType.CMOT_FLOAT3, "GerstnerOffset",
                  ["P", "Centre", "Fade", "PlanetRadius"] + list(shared) + wave_pins, -1200, -800)
    MEL.connect_material_expressions(undisplaced, "", wpo, "P")
    MEL.connect_material_expressions(_vector(m, "SurfaceCentre", (0.0, 0.0, 0.0), -2400, -150, "Ocean"), "", wpo, "Centre")
    MEL.connect_material_expressions(_scalar(m, "FadeWavelengths", 7.0, -2400, -50, "Ocean"), "", wpo, "Fade")
    MEL.connect_material_expressions(_scalar(m, "PlanetRadius", 6.36e6, -2400, 30, "Ocean"), "", wpo, "PlanetRadius")
    for name, e in scalars.items():
        MEL.connect_material_expressions(e, "", wpo, name)
    y = _wave_inputs(m, wpo, -1700, -800)

    # Normals and foam.
    surface = _custom(m, SURFACE_HLSL, unreal.CustomMaterialOutputType.CMOT_FLOAT4, "OceanSurface",
                      ["P", "CamPos", "SceneBehind", "Depth", "View", "RippleScale", "RippleStrength", "FoamFold",
                       "ShoreFoam"] + list(shared) + wave_pins, -1200, 400)
    MEL.connect_material_expressions(undisplaced, "", surface, "P")
    MEL.connect_material_expressions(_expr(m, unreal.MaterialExpressionCameraPositionWS, -2400, 100), "", surface, "CamPos")
    MEL.connect_material_expressions(_expr(m, unreal.MaterialExpressionSceneDepthWithoutWater, -2400, 180), "", surface, "SceneBehind")
    MEL.connect_material_expressions(_expr(m, unreal.MaterialExpressionPixelDepth, -2400, 260), "", surface, "Depth")
    MEL.connect_material_expressions(_expr(m, unreal.MaterialExpressionCameraVectorWS, -2400, 340), "", surface, "View")
    for k, (name, value) in enumerate((("RippleScale", 1.0), ("RippleStrength", 1.0), ("FoamFold", 0.45),
                                       ("ShoreFoam", 0.6))):
        MEL.connect_material_expressions(_scalar(m, name, value, -2400, 420 + 80 * k, "Look"), "", surface, name)
    for name, e in scalars.items():
        MEL.connect_material_expressions(e, "", surface, name)
    _wave_inputs(m, surface, -1700, y + 100)

    normal = _mask(m, surface, "rgb", -800, 300)
    foam = _mask(m, surface, "a", -800, 500)
    far = _math(m, unreal.MaterialExpressionMultiply, _expr(m, unreal.MaterialExpressionPixelDepth, -1100, 650), None,
                -950, 650, const_b=1.0 / 300000.0)
    far_sat = _expr(m, unreal.MaterialExpressionSaturate, -850, 650)
    MEL.connect_material_expressions(far, "", far_sat, "")
    base_rough = _math(m, unreal.MaterialExpressionAdd, _scalar(m, "Roughness", 0.04, -800, 600, "Look"),
                       _math(m, unreal.MaterialExpressionMultiply, far_sat, None, -700, 650, const_b=0.07), -600, 600)
    rough = _expr(m, unreal.MaterialExpressionLinearInterpolate, -500, 600)
    MEL.connect_material_expressions(base_rough, "", rough, "A")
    rough.set_editor_property("const_b", 0.6)
    MEL.connect_material_expressions(foam, "", rough, "Alpha")

    MEL.connect_material_property(_vector(m, "FoamColor", WATER["FoamColor"], -800, 100, "Look"), "",
                                  unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(foam, "", unreal.MaterialProperty.MP_OPACITY)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(_scalar(m, "Specular", 0.5, -800, 700, "Look"), "", unreal.MaterialProperty.MP_SPECULAR)
    MEL.connect_material_property(normal, "", unreal.MaterialProperty.MP_NORMAL)
    MEL.connect_material_property(wpo, "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)

    for k, (name, pin) in enumerate((("Scattering", "ScatteringCoefficients"), ("Absorption", "AbsorptionCoefficients"))):
        per_cm = _math(m, unreal.MaterialExpressionMultiply, _vector(m, name, WATER[name], -800, 850 + 100 * k, "Water"),
                       None, -550, 850 + 100 * k, const_b=0.01)
        MEL.connect_material_expressions(per_cm, "", water, pin)
    MEL.connect_material_expressions(_scalar(m, "PhaseG", 0.2, -800, 1050, "Water"), "", water, "PhaseG")
    MEL.connect_material_expressions(_scalar(m, "ColorScaleBehindWater", 1.0, -800, 1130, "Water"), "", water,
                                     "ColorScaleBehindWater")
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    return m


def build_mesh(material):
    xs = graded(-EXTENT, EXTENT, -CORE, CORE, STEP, GROWTH)
    log(f"ocean grid {len(xs)} x {len(xs)}")
    buf = Buffers()
    n = len(xs)
    for x in xs:
        for y in xs:
            buf.vert((x * 100.0, y * 100.0, 0.0))
    for i in range(n - 1):
        for j in range(n - 1):
            a, b = i * n + j, (i + 1) * n + j
            buf.quad(a, b, b + 1, a + 1)
    part = Part("SM_OceanSurface")
    buf.add_to(part, "Water")
    sm = bake(part, FOLDER, {"Water": material}, collision=False, nanite=False, smooth_angle=90.0)
    # The waves rise and fall a few metres off the flat grid; keep it from being culled or shadow-clipped.
    sm.set_editor_property("positive_bounds_extension", V(0.0, 0.0, 800.0))
    sm.set_editor_property("negative_bounds_extension", V(0.0, 0.0, 800.0))
    sme = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    settings = sme.get_lod_build_settings(sm, 0)
    try_set(settings, "distance_field_resolution_scale", 0.0)
    sme.set_lod_build_settings(sm, 0, settings)
    EAL.save_loaded_asset(sm)
    return sm


def build():
    material = build_material()
    return {"material": material, "mesh": build_mesh(material)}
