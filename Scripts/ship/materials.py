"""Master materials and the instances every kit mesh slot maps onto.

Slot names used by the meshes (Hull, Panel, LED, ...) are the keys of FINISHES, so restyling the ship is
a matter of editing the instances, not the meshes.
"""
import unreal

from .util import EAL, MEL, ROOT, load_or_create, try_set

FOLDER = f"{ROOT}/Materials"

# name: (base colour, roughness, metallic, emissive colour, emissive strength, extra scalar params)
FINISHES = {
    "Hull":      ((0.70, 0.72, 0.75), 0.30, 0.0, None, 0.0, {"RoughnessVariation": 0.10, "ColorVariation": 0.05}),
    "Trim":      ((0.50, 0.53, 0.57), 0.26, 0.0, None, 0.0, {}),
    "Panel":     ((0.34, 0.37, 0.41), 0.42, 0.0, None, 0.0, {}),
    "Floor":     ((0.44, 0.46, 0.49), 0.30, 0.0, None, 0.0, {"RoughnessVariation": 0.10, "ColorVariation": 0.07}),
    "Structure": ((0.030, 0.034, 0.040), 0.55, 0.0, None, 0.0, {}),
    "Metal":     ((0.62, 0.64, 0.67), 0.42, 1.0, None, 0.0, {"RoughnessVariation": 0.05}),
    "Chrome":    ((0.95, 0.95, 0.96), 0.12, 1.0, None, 0.0, {"RoughnessVariation": 0.03, "ColorVariation": 0.0}),
    "Rubber":    ((0.012, 0.012, 0.014), 0.85, 0.0, None, 0.0, {}),
    "Hazard":    ((0.78, 0.50, 0.04), 0.42, 0.0, None, 0.0, {"ColorVariation": 0.08}),
    "LED":       ((0.05, 0.05, 0.05), 0.30, 0.0, (0.92, 0.96, 1.00), 40.0, {}),
    "LEDSoft":   ((0.80, 0.82, 0.85), 0.40, 0.0, (0.95, 0.97, 1.00), 9.0, {}),
    "LEDAmber":  ((0.05, 0.03, 0.01), 0.30, 0.0, (1.00, 0.36, 0.05), 30.0, {}),
    "LEDGreen":  ((0.02, 0.05, 0.03), 0.30, 0.0, (0.10, 1.00, 0.30), 18.0, {}),
}


def _expr(m, cls, x, y):
    return MEL.create_material_expression(m, cls, x, y)


def _scalar(m, name, default, x, y, group="Surface"):
    e = _expr(m, unreal.MaterialExpressionScalarParameter, x, y)
    e.set_editor_property("parameter_name", name)
    e.set_editor_property("default_value", default)
    e.set_editor_property("group", group)
    return e


def _vector(m, name, rgb, x, y, group="Surface"):
    e = _expr(m, unreal.MaterialExpressionVectorParameter, x, y)
    e.set_editor_property("parameter_name", name)
    e.set_editor_property("default_value", unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
    e.set_editor_property("group", group)
    return e


def _math(m, cls, a, b, x, y, const_b=None):
    e = _expr(m, cls, x, y)
    MEL.connect_material_expressions(a, "", e, "A")
    if b is not None:
        MEL.connect_material_expressions(b, "", e, "B")
    elif const_b is not None:
        e.set_editor_property("const_b", const_b)
    return e


def _world_noise(m, scale_param, x, y, levels=4):
    wp = _expr(m, unreal.MaterialExpressionWorldPosition, x - 400, y)
    scaled = _math(m, unreal.MaterialExpressionMultiply, wp, scale_param, x - 250, y)
    noise = _expr(m, unreal.MaterialExpressionNoise, x - 100, y)
    noise.set_editor_property("scale", 1.0)
    noise.set_editor_property("levels", levels)
    noise.set_editor_property("output_min", 0.0)
    noise.set_editor_property("output_max", 1.0)
    MEL.connect_material_expressions(scaled, "", noise, "Position")
    return noise


def _new_material(name, folder=FOLDER):
    """Loads or creates a material and empties its graph so it can be rebuilt from scratch."""
    m = load_or_create(f"{folder}/{name}", unreal.Material, unreal.MaterialFactoryNew())
    MEL.delete_all_material_expressions(m)
    # delete_all can leave nodes behind across rebuilds; stale duplicates of parameter names are a trap, so make sure.
    for _ in range(3):
        leftovers = MEL.get_material_expressions(m)
        if not leftovers:
            break
        for e in leftovers:
            MEL.delete_material_expression(m, e)
    if MEL.get_material_expressions(m):
        raise RuntimeError(f"could not clear the graph of {name}")
    return m


def build_surface_master():
    """Opaque PBR surface with world-space roughness and tint breakup, plus emissive for LEDs."""
    m = _new_material("M_ShipSurface")
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    base = _vector(m, "BaseColor", (0.7, 0.7, 0.7), -900, -300)
    rough = _scalar(m, "Roughness", 0.35, -900, 0)
    metal = _scalar(m, "Metallic", 0.0, -900, 150)
    spec = _scalar(m, "Specular", 0.5, -900, 250)
    rvar = _scalar(m, "RoughnessVariation", 0.08, -900, 350, "Variation")
    cvar = _scalar(m, "ColorVariation", 0.03, -900, 450, "Variation")
    vscale = _scalar(m, "VariationScale", 0.012, -1500, 600, "Variation")
    em_col = _vector(m, "EmissiveColor", (0, 0, 0), -900, 650, "Emissive")
    em_str = _scalar(m, "EmissiveStrength", 0.0, -900, 800, "Emissive")

    noise = _world_noise(m, vscale, -900, 1000)
    # Roughness + (noise - 0.5) * 2 * variation
    centred = _math(m, unreal.MaterialExpressionSubtract, noise, None, -650, 1000, const_b=0.5)
    swing = _math(m, unreal.MaterialExpressionMultiply, centred, rvar, -500, 1000)
    swing2 = _math(m, unreal.MaterialExpressionMultiply, swing, None, -350, 1000, const_b=2.0)
    rough_out = _math(m, unreal.MaterialExpressionAdd, rough, swing2, -200, 0)
    # BaseColor * (1 - colorVariation * noise): faint grime that follows the noise
    grime = _math(m, unreal.MaterialExpressionMultiply, cvar, noise, -650, 450)
    keep = _expr(m, unreal.MaterialExpressionOneMinus, -500, 450)
    MEL.connect_material_expressions(grime, "", keep, "")
    base_out = _math(m, unreal.MaterialExpressionMultiply, base, keep, -200, -300)
    emissive = _math(m, unreal.MaterialExpressionMultiply, em_col, em_str, -200, 650)

    MEL.connect_material_property(base_out, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(rough_out, "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(metal, "", unreal.MaterialProperty.MP_METALLIC)
    MEL.connect_material_property(spec, "", unreal.MaterialProperty.MP_SPECULAR)
    MEL.connect_material_property(emissive, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    return m


def build_screen_master():
    """Glossy dark screen glowing with rows of 'readout' blocks, laid out in world space so it needs no UVs."""
    m = _new_material("M_ShipScreen")
    col = _vector(m, "ScreenColor", (0.25, 0.65, 1.0), -900, 0, "Screen")
    strength = _scalar(m, "Strength", 6.0, -900, 150, "Screen")
    rows = _scalar(m, "RowDensity", 0.55, -1500, 300, "Screen")
    blocks_scale = _scalar(m, "BlockScale", 0.09, -1500, 600, "Screen")

    wp = _expr(m, unreal.MaterialExpressionWorldPosition, -1500, 400)
    wz = _expr(m, unreal.MaterialExpressionComponentMask, -1350, 400)
    wz.set_editor_property("r", False)
    wz.set_editor_property("g", False)
    wz.set_editor_property("b", True)
    MEL.connect_material_expressions(wp, "", wz, "")
    zrows = _math(m, unreal.MaterialExpressionMultiply, wz, rows, -1200, 400)
    frac = _expr(m, unreal.MaterialExpressionFrac, -1050, 400)
    MEL.connect_material_expressions(zrows, "", frac, "")
    lines = _math(m, unreal.MaterialExpressionSubtract, frac, None, -900, 400, const_b=0.45)
    lines = _math(m, unreal.MaterialExpressionMultiply, lines, None, -750, 400, const_b=12.0)
    lines_sat = _expr(m, unreal.MaterialExpressionSaturate, -600, 400)
    MEL.connect_material_expressions(lines, "", lines_sat, "")

    noise = _world_noise(m, blocks_scale, -900, 650, levels=2)
    blocks = _math(m, unreal.MaterialExpressionSubtract, noise, None, -750, 650, const_b=0.42)
    blocks = _math(m, unreal.MaterialExpressionMultiply, blocks, None, -600, 650, const_b=8.0)
    blocks_sat = _expr(m, unreal.MaterialExpressionSaturate, -450, 650)
    MEL.connect_material_expressions(blocks, "", blocks_sat, "")

    pattern = _math(m, unreal.MaterialExpressionMultiply, lines_sat, blocks_sat, -300, 500)
    lifted = _math(m, unreal.MaterialExpressionMultiply, pattern, None, -150, 500, const_b=0.8)
    lifted = _math(m, unreal.MaterialExpressionAdd, lifted, None, -50, 500, const_b=0.2)
    glow = _math(m, unreal.MaterialExpressionMultiply, col, strength, -300, 100)
    emissive = _math(m, unreal.MaterialExpressionMultiply, glow, lifted, 50, 200)

    black = _expr(m, unreal.MaterialExpressionConstant3Vector, -300, -200)
    black.set_editor_property("constant", unreal.LinearColor(0.01, 0.012, 0.016, 1))
    gloss = _expr(m, unreal.MaterialExpressionConstant, -300, -50)
    gloss.set_editor_property("r", 0.12)
    MEL.connect_material_property(black, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(gloss, "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(emissive, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    return m


def build_glass():
    m = _new_material("M_ShipGlass")
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    mode = getattr(unreal.TranslucencyLightingMode, "TLM_SURFACE_PER_PIXEL_LIGHTING",
                   unreal.TranslucencyLightingMode.TLM_SURFACE)
    try_set(m, "translucency_lighting_mode", mode)
    tint = _vector(m, "Tint", (0.80, 0.90, 1.0), -600, 0, "Glass")
    opacity = _scalar(m, "Opacity", 0.04, -600, 200, "Glass")
    rough = _scalar(m, "Roughness", 0.04, -600, 300, "Glass")
    # Just a hint of the lit corridor on the pane; a full-strength mirror hides the planet.
    spec = _scalar(m, "Specular", 0.12, -600, 400, "Glass")
    MEL.connect_material_property(tint, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(opacity, "", unreal.MaterialProperty.MP_OPACITY)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(spec, "", unreal.MaterialProperty.MP_SPECULAR)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    return m


# Cloud density seen from orbit. Coverage comes from a domain-warped, multi-octave weather field
# hundreds of km across (fronts, swirls and clear ocean), and the cloud bodies are carved from it
# with flat bases, taller tops where cover is thick, and km-scale erosion.
# Cloud density seen from orbit, evaluated in the planet-fixed space frame (km, planet at the origin) so the
# clouds stay on the planet while the ship flies over them. Coverage comes from a domain-warped, multi-octave
# weather field sampled on the sphere (fronts, swirls and clear ocean); the cloud bodies are carved from it
# with flat bases, taller tops where cover is thick, and km-scale erosion.
CLOUD_DENSITY_HLSL = """
float3 w = P * 1e-5;
float3 km = SpaceOrigin.xyz + SpaceAxisX.xyz * w.x + SpaceAxisY.xyz * w.y + SpaceAxisZ.xyz * w.z;
float3 q = normalize(km) * (PlanetRadius / WeatherScale);
float3 warp = float3(Texture3DSampleLevel(Tex, TexSampler, q * 0.85 + 0.17, 0).r,
                     Texture3DSampleLevel(Tex, TexSampler, q * 0.85 + 0.43, 0).r,
                     Texture3DSampleLevel(Tex, TexSampler, q * 0.85 + 0.71, 0).r) - 0.5;
q += warp * Warp;
float cw = Texture3DSampleLevel(Tex, TexSampler, q + 0.31, 0).r * 0.58
         + Texture3DSampleLevel(Tex, TexSampler, q * 2.7 + 0.53, 0).r * 0.28
         + Texture3DSampleLevel(Tex, TexSampler, q * 8.3 + 0.79, 0).g * 0.14;
float cover = saturate((cw - (1.0 - Coverage)) / Softness);
float top = lerp(0.15, 1.0, cover * cover);
float shape = saturate(H / 0.05) * saturate((top - H) / max(top * 0.55, 0.01));
float detail = Texture3DSampleLevel(Tex, TexSampler, km / DetailScale, 0).g;
return saturate(cover * shape - detail * Erosion * (1.0 - 0.5 * cover));
"""


def build_cloud_material():
    """Volumetric cloud material for the planet below: large-scale weather systems instead of uniform popcorn."""
    m = _new_material("M_OrbitClouds")
    m.set_editor_property("material_domain", unreal.MaterialDomain.MD_VOLUME)
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
    m.set_editor_property("used_with_volumetric_cloud", True)  # without it the cloud shaders never compile

    noise = _expr(m, unreal.MaterialExpressionTextureObjectParameter, -1200, 0)
    noise.set_editor_property("parameter_name", "Noise")
    noise.set_editor_property("group", "Clouds")
    noise.set_editor_property("texture", EAL.load_asset("/Engine/EngineSky/VolumetricClouds/VT_PerlinWorley_Balanced"))
    noise.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
    wp = _expr(m, unreal.MaterialExpressionWorldPosition, -1200, -200)
    attr = _expr(m, unreal.MaterialExpressionCloudSampleAttribute, -1200, -350)

    params = {
        "Coverage": (0.50, "How much of the planet is clouded (0..1)."),
        "Softness": (0.34, "Feathering at cloud-field edges."),
        "WeatherScale": (1100.0, "Size of weather systems, km."),
        "Warp": (0.75, "Swirl / front distortion of the weather."),
        "DetailScale": (10.0, "Size of cloud cells, km."),
        "Erosion": (0.55, "How much the cells break up thin cloud."),
    }
    custom = _expr(m, unreal.MaterialExpressionCustom, -700, 0)
    custom.set_editor_property("code", CLOUD_DENSITY_HLSL)
    custom.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    custom.set_editor_property("description", "CloudDensity")
    params["PlanetRadius"] = (6360.0, "Planet radius, km.")
    frame = {"SpaceOrigin": (0.0, 0.0, 6480.0), "SpaceAxisX": (1.0, 0.0, 0.0),
             "SpaceAxisY": (0.0, 1.0, 0.0), "SpaceAxisZ": (0.0, 0.0, 1.0)}
    inputs = []
    for name in ["P", "H", "Tex"] + list(params) + list(frame):
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", name)
        inputs.append(ci)
    custom.set_editor_property("inputs", inputs)
    MEL.connect_material_expressions(wp, "", custom, "P")
    MEL.connect_material_expressions(attr, "NormAltitudeInLayer", custom, "H")
    MEL.connect_material_expressions(noise, "", custom, "Tex")
    y = 200
    for name, (value, _) in params.items():
        MEL.connect_material_expressions(_scalar(m, name, value, -1000, y, "Clouds"), "", custom, name)
        y += 90
    # Space frame: set by the level for the editor view, and every frame by ASpaceEnvironment in play.
    for name, value in frame.items():
        MEL.connect_material_expressions(_vector(m, name, value, -1000, y, "Space Frame"), "", custom, name)
        y += 110

    extinction = _math(m, unreal.MaterialExpressionMultiply, custom,
                       _scalar(m, "Extinction", 0.06, -700, 300, "Clouds"), -400, 100)
    albedo = _vector(m, "Albedo", (0.96, 0.97, 0.98), -400, -150, "Clouds")
    # Brighter ambient toward the cloud tops.
    ao = _expr(m, unreal.MaterialExpressionMultiply, -700, -450)
    ao.set_editor_property("const_b", 0.6)
    MEL.connect_material_expressions(attr, "NormAltitudeInLayer", ao, "A")
    ao = _math(m, unreal.MaterialExpressionAdd, ao, None, -550, -450, const_b=0.4)

    MEL.connect_material_property(albedo, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(extinction, "", unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
    MEL.connect_material_property(ao, "", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)

    adv = _expr(m, unreal.MaterialExpressionVolumetricAdvancedMaterialOutput, -200, 500)
    for key, value in (("const_phase_g", 0.6), ("const_phase_g2", -0.25), ("const_phase_blend", 0.45),
                       ("multi_scattering_approximation_octave_count", 2),
                       ("const_multi_scattering_contribution", 0.55), ("const_multi_scattering_occlusion", 0.45),
                       ("const_multi_scattering_eccentricity", 0.6), ("ground_contribution", True)):
        try_set(adv, key, value)

    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    mi = _instance("MI_OrbitClouds", m)
    MEL.clear_all_material_instance_parameters(mi)  # tuning lives in the master's defaults above
    EAL.save_loaded_asset(mi)
    return mi


# Space backdrop, drawn additively over the sky atmosphere on a huge shell. Stars, galaxy and nebulae are a
# function of the view direction in the space frame, so they sit at infinity and turn with the ship; the
# planet is ray-traced analytically to hide what's behind it; dust motes sit at finite distances and stream past.
SPACE_HLSL = """
struct FSpace
{
    float Hash(float3 p)
    {
        p = frac(p * 0.3183099 + 0.1);
        p *= 17.0;
        return frac(p.x * p.y * p.z * (p.x + p.y + p.z));
    }
    float3 Hash3(float3 p) { return float3(Hash(p), Hash(p + 31.7), Hash(p + 71.3)); }
    float Noise(float3 p)
    {
        float3 i = floor(p);
        float3 f = frac(p);
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
        for (int k = 0; k < 5; k++) { s += a * Noise(p); p = p * 2.07 + 13.1; a *= 0.5; }
        return s;
    }
    // Rough blackbody ramp: cool red dwarfs -> sun-like -> white -> hot blue giants.
    float3 Temperature(float t)
    {
        float3 c = lerp(float3(1.0, 0.50, 0.30), float3(1.0, 0.83, 0.60), saturate(t * 3.0));
        c = lerp(c, float3(1.0, 0.97, 0.93), saturate(t * 3.0 - 1.0));
        return lerp(c, float3(0.66, 0.79, 1.0), saturate(t * 3.0 - 2.0));
    }
    // One layer of stars on a grid of cells over the sphere; at most one star per cell.
    float3 Stars(float3 d, float cells, float density, float size, float pix, float seed)
    {
        float3 c = floor(d * cells);
        float3 h = Hash3(c + seed);
        if (h.x > density) return 0;
        float3 sd = normalize(c + 0.3 + 0.4 * Hash3(c + seed + 5.3));
        float ang = length(cross(d, sd));
        float mag = pow(h.y, 8.0);                 // most stars faint, a few brilliant
        float r0 = size * (0.35 + 1.6 * mag);
        float r = max(r0, pix * 0.7);              // never smaller than a pixel...
        float flux = (r0 * r0) / (r * r);          // ...but keep its total light, so no sparkle
        return Temperature(h.z) * (0.035 + 5.0 * mag) * flux * exp(-ang * ang / (r * r));
    }
    // Dust motes on a 3D grid of cells (cellKm across) around the ship, at a few depths along the view ray.
    // Each mote is smeared back along the ship's velocity, so speed shows as streaks.
    float Dust(float3 d, float3 ship, float3 vel, float cellKm, float density, float streak, float pix, float groundKm, float seed)
    {
        float sum = 0.0;
        for (int i = 0; i < 4; i++)
        {
            float t = cellKm * (0.9 + 1.7 * i);
            // Smear back along the motion, but never longer than half the mote's distance:
            // it should read as a streak, not a slash across the window.
            float3 e = -vel * streak;
            float elen = length(e);
            e *= min(1.0, 0.5 * t / max(elen, 1e-6));
            float3 cell = floor((ship + d * t) / cellKm);
            float3 h = Hash3(cell + seed * 13.0);
            if (h.x > density) continue;
            float3 m = (cell + 0.25 + 0.5 * Hash3(cell + seed * 13.0 + 9.1)) * cellKm - ship;
            float3 mp = m - d * dot(m, d);
            float3 ep = e - d * dot(e, d);
            float s = saturate(-dot(mp, ep) / max(dot(ep, ep), 1e-12));
            float3 p = m + e * s;
            float depth = dot(p, d);
            if (depth <= 0.0 || depth > groundKm) continue;
            float ang = length(p - d * depth) / depth;
            float r = max(pix * 0.8, 0.00025);
            float smear = 1.0 + length(ep) / (depth * r);          // a streak spreads the light thinner...
            float fade = saturate(1.0 - t / (cellKm * 6.0)) * saturate(t / cellKm);
            sum += (0.25 + h.y) * fade * rsqrt(smear) * exp(-ang * ang / (r * r));  // ...but stays visible
        }
        return float3(sum, sum, sum);
    }
};
FSpace S;
float3 dw = normalize(D);
float pix = max(length(ddx(dw)), length(ddy(dw)));
// Everything lives in the space frame (km, planet at the origin), so it turns and slides as the ship flies.
float3 d = normalize(SpaceAxisX.xyz * dw.x + SpaceAxisY.xyz * dw.y + SpaceAxisZ.xyz * dw.z);
float3 o = SpaceOrigin.xyz;   // the ship, relative to the planet's centre
// Inside the atmosphere the daylit sky drowns the stars and the dust: fade them out on the way down.
float airFade = saturate((length(o) - PlanetRadius - 15.0) / 45.0);

// Where the view ray meets the planet, if it does.
float b = dot(o, d);
float c = dot(o, o) - PlanetRadius * PlanetRadius;
float hit = b * b - c;
float groundKm = (b < 0.0 && hit > 0.0) ? (-b - sqrt(hit)) : 1e9;

// Space dust: motes fixed in space at three scales. They drift past slowly and smear into streaks at speed.
float3 dust = 0;
dust += S.Dust(d, o, DustVelocity.xyz, 1.0, DustDensity, DustStreak, pix, groundKm, 1.0);
dust += S.Dust(d, o, DustVelocity.xyz, 9.0, DustDensity, DustStreak, pix, groundKm, 2.0);
dust += S.Dust(d, o, DustVelocity.xyz, 80.0, DustDensity, DustStreak, pix, groundKm, 3.0);
dust *= DustBrightness * airFade * float3(1.0, 0.93, 0.85);

// Hide the sky behind the planet, and fade it through the atmosphere's glow at the limb.
float visible = 1.0;
if (b < 0.0)
{
    float altitude = sqrt(max(dot(o, o) - b * b, 0.0)) - PlanetRadius;
    visible = saturate((altitude - 8.0) / AtmosphereFade);
}
if (visible <= 0.0) return dust;

// Milky Way: a band round the galactic plane, brightest toward the core, cut by dark dust lanes.
float g = dot(d, normalize(GalaxyNormal.xyz));
float band = exp(-g * g / (BandWidth * BandWidth));
float core = pow(saturate(dot(d, normalize(GalaxyCore.xyz))), 5.0);
float glow = band * (0.3 + 0.7 * S.Fbm(d * 6.0)) * (1.0 + 3.0 * core);
float lanes = saturate((S.Fbm(d * 11.0 + 3.7) - 0.47) * 4.0) * band;
float lanesDark = 1.0 - DustLanes * lanes;

// Nebulae: soft clouds of hydrogen red and oxygen teal.
float n1 = pow(saturate((S.Fbm(d * 2.3 + 11.0) - 0.46) * 2.4), 2.0);
float n2 = pow(saturate((S.Fbm(d * 3.4 - 7.0) - 0.48) * 2.6), 2.0);
float3 nebula = (NebulaColorA.xyz * n1 + NebulaColorB.xyz * n2) * Nebula * (0.35 + 0.65 * band + 0.6 * core);

float3 stars = S.Stars(d, 140.0, 0.32 * StarDensity, StarSize * 1.3, pix, 1.0)
             + S.Stars(d, 330.0, 0.45 * StarDensity, StarSize, pix, 2.0)
             + S.Stars(d, 760.0, (0.08 + 0.7 * band) * StarDensity, StarSize * 0.7, pix, 3.0) * (0.5 + core);
float3 col = (stars * StarBrightness + glow * MilkyWay * float3(1.0, 0.86, 0.72) + nebula) * lanesDark;

// Distant star: a hot blue-white point with a halo and four diffraction spikes.
float3 sdir = normalize(StarDir.xyz);
float cosA = dot(d, sdir);
if (cosA > 0.99)
{
    float ang = acos(min(cosA, 1.0));
    float3 t = normalize(cross(sdir, float3(0, 0, 1)));
    float3 u = cross(t, sdir);
    float x = dot(d, t * 0.866 + u * 0.5);
    float y = dot(d, u * 0.866 - t * 0.5);
    float rc = max(0.0005, pix * 0.8);
    float point_ = exp(-ang * ang / (rc * rc)) * (0.0005 * 0.0005) / (rc * rc);
    float halo = 0.02 * exp(-ang / 0.004) + 0.003 * exp(-ang / 0.02);
    float sw = max(0.0002, pix * 0.45);
    float spikes = exp(-abs(y) / sw) * exp(-abs(x) / 0.02) + exp(-abs(x) / sw) * exp(-abs(y) / 0.02);
    col += StarColor.xyz * StarIntensity * (point_ + halo + 0.05 * spikes);
}
return col * visible * airFade + dust;
"""


def build_space_backdrop():
    """Additive, unlit backdrop for a huge shell around the ship: stars, Milky Way, dust lanes, nebulae, a distant star."""
    m = _new_material("M_SpaceBackdrop")
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property("two_sided", True)
    m.set_editor_property("use_translucency_vertex_fog", False)
    m.set_editor_property("apply_cloud_fogging", False)
    m.set_editor_property("enable_responsive_aa", True)  # keeps pin-point stars crisp under TSR

    view = _expr(m, unreal.MaterialExpressionCameraVectorWS, -1400, -200)
    direction = _math(m, unreal.MaterialExpressionMultiply, view, None, -1250, -200, const_b=-1.0)
    scalars = {
        "StarBrightness": (1.0, "Stars"), "StarDensity": (0.4, "Stars"), "StarSize": (0.00035, "Stars"),
        "MilkyWay": (0.14, "Milky Way"), "BandWidth": (0.17, "Milky Way"), "DustLanes": (0.85, "Milky Way"),
        "Nebula": (1.4, "Nebula"),
        "StarIntensity": (380.0, "Distant Star"),
        "PlanetRadius": (6360.0, "Planet"), "AtmosphereFade": (70.0, "Planet"),
        "DustDensity": (0.32, "Space Dust"), "DustBrightness": (9.0, "Space Dust"), "DustStreak": (0.06, "Space Dust"),
    }
    vectors = {
        "NebulaColorA": ((1.0, 0.16, 0.48), "Nebula"), "NebulaColorB": ((0.05, 0.58, 0.95), "Nebula"),
        "GalaxyNormal": ((0.0, 0.5, 0.866), "Milky Way"), "GalaxyCore": ((1.0, 0.0, 0.0), "Milky Way"),
        "StarDir": ((1.0, 0.0, 0.1), "Distant Star"), "StarColor": ((0.72, 0.84, 1.0), "Distant Star"),
        "SpaceOrigin": ((0.0, 0.0, 6480.0), "Space Frame"), "SpaceAxisX": ((1.0, 0.0, 0.0), "Space Frame"),
        "SpaceAxisY": ((0.0, 1.0, 0.0), "Space Frame"), "SpaceAxisZ": ((0.0, 0.0, 1.0), "Space Frame"),
        "DustVelocity": ((0.0, 0.0, 0.0), "Space Dust"),
    }
    custom = _expr(m, unreal.MaterialExpressionCustom, -700, 0)
    custom.set_editor_property("code", SPACE_HLSL)
    custom.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    custom.set_editor_property("description", "SpaceBackdrop")
    inputs = []
    for name in ["D"] + list(scalars) + list(vectors):
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", name)
        inputs.append(ci)
    custom.set_editor_property("inputs", inputs)
    MEL.connect_material_expressions(direction, "", custom, "D")
    y = -100
    for name, (value, group) in scalars.items():
        MEL.connect_material_expressions(_scalar(m, name, value, -1000, y, group), "", custom, name)
        y += 80
    for name, (rgb, group) in vectors.items():
        MEL.connect_material_expressions(_vector(m, name, rgb, -1000, y, group), "", custom, name)
        y += 110
    MEL.connect_material_property(custom, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    mi = _instance("MI_SpaceBackdrop", m)
    MEL.clear_all_material_instance_parameters(mi)  # the level sets placement; the look lives in the defaults above
    EAL.save_loaded_asset(mi)
    return mi


def _instance(name, parent):
    mi = load_or_create(f"{FOLDER}/{name}", unreal.MaterialInstanceConstant,
                        unreal.MaterialInstanceConstantFactoryNew())
    mi.set_editor_property("parent", parent)
    return mi


def build_all():
    """Returns {slot name: material} for every slot the kit meshes use."""
    surface = build_surface_master()
    screen = build_screen_master()
    glass = build_glass()
    mats = {}
    for name, (base, rough, metal, em_col, em_str, extra) in FINISHES.items():
        mi = _instance(f"MI_Ship_{name}", surface)
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
    mats["Screen"] = _instance("MI_Ship_Screen", screen)
    EAL.save_loaded_asset(mats["Screen"])
    mats["Glass"] = _instance("MI_Ship_Glass", glass)
    EAL.save_loaded_asset(mats["Glass"])
    mats["Clouds"] = build_cloud_material()
    mats["Backdrop"] = build_space_backdrop()
    return mats
