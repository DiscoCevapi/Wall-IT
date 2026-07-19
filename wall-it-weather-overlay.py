#!/usr/bin/env python3
"""
Wall-IT Weather Overlay v3 (GPU)
================================
A native GPU weather overlay rendered as a transparent, click-through Wayland
layer-shell surface that sits above the wallpaper but below application windows.

Instead of the old Pillow/CPU particle renderer (which pushed a JPEG to the
wallpaper roughly once per second and looked low-fidelity), this version runs
procedural GLSL fragment shaders at the monitor's native refresh rate using
moderngl inside a GTK4 GtkGLArea. The six effects are ports of the
noctalia-shell command-centre weather shaders:

    rain   - animated ripple/refraction distortion of the wallpaper
    snow   - layered procedural snowflake field
    cloud  - fbm turbulence haze (clouds, or fog via the "alternative" flag)
    sun    - god-rays + pulsing sun core/flare + warm wash over the wallpaper
    stars  - twinkling multi-density star field
    storm  - heavy rain ripple + storm-cloud darkening + lightning flashes

Process contract (unchanged so the GUI/tray need no edits):
  * Launched with no arguments; it resolves the current weather itself.
  * Watches  ~/.cache/wall-it/weather-ipc/stop  and exits when it appears.
  * Exits cleanly on SIGINT / SIGTERM.

Testing helpers:
  * --force <condition>   force an effect (e.g. rain, storm, snow, cloud,
                          fog, sun, clear-day, stars, sunset, dawn, night)
  * env WALLIT_FORCE_WEATHER=<condition>   same as --force
"""

import os
import sys
import json
import time
import signal
import argparse
import urllib.request
from pathlib import Path

# gtk4-layer-shell must be loaded BEFORE libwayland-client. If libwayland loads
# first, the layer-shell shim never registers and Gtk4LayerShell.init_for_window()
# silently fails (warning: "Failed to initialize layer surface ... GTK4 Layer
# Shell may have been linked after libwayland"), so the window becomes a normal
# decorated toplevel ("separate window") instead of a transparent, click-through
# wallpaper overlay. Preloading the .so here fixes it without recompiling.
# See https://github.com/wmww/gtk4-layer-shell/blob/main/linking.md
from ctypes import CDLL
for _lib in ("libgtk4-layer-shell.so", "libgtk4-layer-shell.so.0"):
    try:
        CDLL(_lib)
        break
    except OSError:
        continue

# Layer-shell only works under the Wayland backend. Force it so GTK4 does not
# fall back to X11/XWayland, where this surface would render as a normal,
# decorated toplevel "separate window" instead of being composited on the
# wallpaper.
os.environ.setdefault("GDK_BACKEND", "wayland")

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, Gdk, GLib, Gtk4LayerShell  # noqa: E402

try:
    import cairo  # for the empty input region (click-through)
    HAVE_CAIRO = True
except Exception:  # pragma: no cover
    HAVE_CAIRO = False

try:
    import moderngl
except Exception as exc:  # pragma: no cover
    print(f"\u274c moderngl is required: {exc}\n   Install: pip install --user --break-system-packages moderngl")
    sys.exit(1)

from PIL import Image

# ── Paths / IPC ──────────────────────────────────────────────────────────────
IPC_DIR = Path.home() / ".cache" / "wall-it" / "weather-ipc"
STOP_FILE = IPC_DIR / "stop"
CURRENT_WALLPAPER_LINK = Path.home() / ".current-wallpaper"
WALLPAPER_DIR = Path.home() / "Pictures" / "Wallpapers"
MAX_TEXTURE_SIDE = 2560  # cap wallpaper texture size to save VRAM/bandwidth

# ── Weather resolution ───────────────────────────────────────────────────────
WTTR_CONDITION_MAP = {
    "Clear": "clear-day", "Sunny": "clear-day", "Partly cloudy": "partly-cloudy",
    "Cloudy": "cloudy", "Overcast": "cloudy", "Mist": "fog", "Fog": "fog",
    "Freezing fog": "fog", "Patchy rain possible": "rain", "Light drizzle": "rain",
    "Patchy light drizzle": "rain", "Light rain": "rain", "Moderate rain": "rain",
    "Heavy rain": "rain", "Torrential rain": "rain", "Light rain shower": "rain",
    "Moderate rain shower": "rain", "Heavy rain shower": "rain",
    "Patchy snow possible": "snow", "Light snow": "snow", "Moderate snow": "snow",
    "Heavy snow": "snow", "Light snow shower": "snow", "Moderate snow shower": "snow",
    "Heavy snow shower": "snow", "Light sleet": "snow", "Moderate sleet": "snow",
    "Thundery outbreaks possible": "storm", "Patchy light rain with thunder": "storm",
    "Moderate or heavy rain with thunder": "storm", "Blowing snow": "snow",
    "Blizzard": "snow", "Hail": "snow",
}


def _parse_hhmm(value):
    """Parse wttr.in astronomy times ('07:01 AM', '04:55 PM', or '16:55')
    into minutes since midnight. Returns None on failure."""
    try:
        import re
        m = re.match(r"\s*(\d{1,2}):(\d{2})\s*(AM|PM)?", str(value).upper())
        if not m:
            return None
        h, mm, ap = int(m.group(1)), int(m.group(2)), m.group(3)
        if ap == "PM" and h != 12:
            h += 12
        elif ap == "AM" and h == 12:
            h = 0
        return h * 60 + mm
    except Exception:
        return None


def _time_phase(now_min, sunrise_min, sunset_min):
    """Return 'night' / 'sunset' / 'dawn' / 'day' from the real sun position.

    Uses actual sunrise/sunset from wttr.in astronomy when available (a twilight
    window of +/- 45 min around each). Falls back to a local-hour heuristic
    otherwise. Previously these phases were only applied when the weather fetch
    *failed* and used hardcoded hour windows that didn't match real sunset
    times, so 'sunset' never showed up when wttr.in succeeded."""
    twilight = 45  # minutes either side of sunrise/sunset
    if sunrise_min is not None and sunset_min is not None:
        dawn_start, dawn_end = sunrise_min - twilight, sunrise_min + twilight
        dusk_start, dusk_end = sunset_min - twilight, sunset_min + twilight
        if dusk_end <= now_min or now_min < dawn_start:
            return "night"
        if dusk_start <= now_min < dusk_end:
            return "sunset"
        if dawn_start <= now_min < dawn_end:
            return "dawn"
        return "day"
    # Fallback: no astronomy data available, estimate from the local hour.
    h = now_min // 60
    if h < 7 or h >= 20:
        return "night"
    if 16 <= h < 20:
        return "sunset"
    if 5 <= h < 7:
        return "dawn"
    return "day"


def fetch_weather_condition():
    """Return a canonical condition string from LOCAL weather + sun position.

    wttr.in geolocates by IP and reports the weather description plus
    sunrise/sunset for your area. We combine the two: precipitation/fog and full
    overcast keep their weather effect; clear or partly-cloudy skies defer to the
    actual sun position so you get sunset / dawn / stars at the right time of
    day (not just when the network fetch fails)."""
    weather_cond = None
    desc = ""
    sunrise_min = sunset_min = None
    try:
        url = "https://wttr.in/?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "Wall-IT-Overlay/3.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        desc = (
            data.get("current_condition", [{}])[0]
            .get("weatherDesc", [{}])[0]
            .get("value", "")
        )
        # wttr.in's current_condition has no reliable 'isdaytime' field, so we
        # derive day/night from the astronomy block instead.
        astro = data.get("weather", [{}])[0].get("astronomy", [{}])
        if astro:
            sunrise_min = _parse_hhmm(astro[0].get("sunrise", ""))
            sunset_min = _parse_hhmm(astro[0].get("sunset", ""))
        for wttr_key, cond in WTTR_CONDITION_MAP.items():
            if wttr_key.lower() in desc.lower() or desc.lower() in wttr_key.lower():
                weather_cond = cond
                break
        if weather_cond is None:
            d = desc.lower()
            if any(w in d for w in ["thunder", "thunderstorm", "lightning"]):
                weather_cond = "storm"
            elif any(w in d for w in ["rain", "drizzle", "shower"]):
                weather_cond = "rain"
            elif any(w in d for w in ["snow", "sleet", "blizzard"]):
                weather_cond = "snow"
            elif any(w in d for w in ["fog", "mist", "haze"]):
                weather_cond = "fog"
            elif "overcast" in d or d == "cloudy":
                weather_cond = "cloudy"
            elif "partly" in d:
                weather_cond = "partly-cloudy"
            elif "clear" in d or "sunny" in d:
                weather_cond = "clear-day"
    except Exception as exc:
        print(f"\u26a0\ufe0f  Weather fetch failed: {exc}")

    lt = time.localtime()
    now_min = lt.tm_hour * 60 + lt.tm_min
    phase = _time_phase(now_min, sunrise_min, sunset_min)

    # Precipitation and fog dominate at any time (you can't see the sun/stars).
    if weather_cond in ("rain", "storm", "snow", "fog"):
        return weather_cond
    # At sunrise / sunset / night, show the warm-sun or stars effect for any sky
    # that isn't fully overcast (the sun/stars are usually visible through
    # partial cloud). Full overcast keeps the cloud effect.
    if phase in ("sunset", "dawn", "night"):
        if weather_cond == "cloudy":
            return "cloudy"
        if weather_cond == "partly-cloudy":
            # Preserve the mixed-sky condition so resolve_effects() can layer
            # the sun/stars effect with a translucent cloud pass on top.
            return f"partly-cloudy-{phase}"
        if phase == "night":
            return "clear-night"
        if phase == "sunset":
            return "sunset"
        return "dawn"
    # Daytime: use the reported weather (clear-day -> sun, partly-cloudy/cloudy
    # -> clouds).
    if weather_cond == "partly-cloudy":
        return "partly-cloudy-day"
    return weather_cond or "clear-day"


def resolve_effects(force=None):
    """Map a condition string onto a list of (effect_name, params_dict) layers.

    Mixed-sky conditions return two layers composited in order: the opaque-base
    effect (sun or stars) first, then a translucent cloud pass on top, each
    with a ``strength`` key (0.0-1.0) that scales shader intensity/opacity.
    All other conditions return a single-element list (unchanged behaviour).
    """
    cond = (force or os.environ.get("WALLIT_FORCE_WEATHER") or fetch_weather_condition())
    cond = cond.strip().lower().replace(" ", "-").replace("_", "-")

    _DAY_SUN  = (1.0, 0.95, 0.70)
    _DAWN_SUN = (1.0, 0.80, 0.55)
    _DUSK_SUN = (1.0, 0.62, 0.32)

    # ── Multi-layer blended conditions ────────────────────────────────────────
    if cond == "partly-cloudy-day":
        return [
            ("sun",   {"sun_color": _DAY_SUN,  "strength": 0.65}),
            ("cloud", {"alternative": 0.0,       "strength": 0.45}),
        ]
    if cond == "partly-cloudy-night":
        return [
            ("stars", {"strength": 0.75}),
            ("cloud", {"alternative": 0.0, "strength": 0.30}),
        ]
    if cond == "partly-cloudy-dawn":
        return [
            ("sun",   {"sun_color": _DAWN_SUN, "strength": 0.65}),
            ("cloud", {"alternative": 0.0,      "strength": 0.35}),
        ]
    if cond == "partly-cloudy-sunset":
        return [
            ("sun",   {"sun_color": _DUSK_SUN, "strength": 0.65}),
            ("cloud", {"alternative": 0.0,      "strength": 0.35}),
        ]

    # ── Single-effect conditions (unchanged behaviour) ────────────────────────
    storm    = {"storm", "thunder", "thunderstorm", "lightning"}
    rain     = {"rain", "drizzle", "shower", "showers"}
    snow     = {"snow", "sleet", "blizzard", "hail"}
    fog      = {"fog", "mist", "haze"}
    cloud    = {"cloud", "clouds", "cloudy", "overcast", "partly-cloudy",
                "partly-cloudy-day", "partly-cloudy-night", "wind", "windy"}
    sun_day  = {"sun", "sunny", "clear", "clear-day", "day", "noon",
                "morning", "afternoon"}
    sun_warm = {"sunset", "sunset-transition", "dusk", "dawn", "sunrise"}
    night    = {"night", "clear-night", "stars", "starry"}

    if cond in storm:
        return [("storm", {})]
    if cond in rain:
        return [("rain", {})]
    if cond in snow:
        return [("snow", {})]
    if cond in fog:
        return [("cloud", {"alternative": 1.0})]
    if cond in cloud:
        return [("cloud", {"alternative": 0.0})]
    if cond in night:
        return [("stars", {})]
    if cond in sun_warm:
        warm = _DUSK_SUN if cond in {"sunset", "sunset-transition", "dusk"} else _DAWN_SUN
        return [("sun", {"sun_color": warm})]
    if cond in sun_day:
        return [("sun", {"sun_color": _DAY_SUN})]
    # Direct effect names also accepted (rain/storm/snow/cloud/fog/sun/stars)
    if cond in {"storm", "rain", "snow", "cloud", "sun", "stars"}:
        return [("cloud", {}) if cond == "cloud" else (cond, {})]
    if cond == "fog":
        return [("cloud", {"alternative": 1.0})]
    return [("sun", {"sun_color": _DAY_SUN})]


# ── Shaders ──────────────────────────────────────────────────────────────────
VERTEX_SHADER = """
#version 330 core
out vec2 v_uv;
void main() {
    // Fullscreen triangle from gl_VertexID, uv origin top-left (Qt-style).
    float x = (gl_VertexID == 1) ? 3.0 : -1.0;
    float y = (gl_VertexID == 2) ? 3.0 : -1.0;
    gl_Position = vec4(x, y, 0.0, 1.0);
    v_uv = vec2((x + 1.0) * 0.5, (1.0 - y) * 0.5);
}
"""

FRAG_RAIN = """
#version 330 core
in vec2 v_uv;
out vec4 fragColor;
uniform float u_time;
uniform vec2 u_resolution;
uniform sampler2D u_wallpaper;
uniform float u_strength;

vec3 hash3(vec2 p) {
    vec3 q = vec3(dot(p, vec2(127.1, 311.7)),
                  dot(p, vec2(269.5, 183.3)),
                  dot(p, vec2(419.2, 371.9)));
    return fract(sin(q) * 43758.5453);
}

float noise(vec2 x, float iTime) {
    vec2 p = floor(x);
    vec2 f = fract(x);
    float va = 0.0;
    for (int j = -2; j <= 2; j++) {
        for (int i = -2; i <= 2; i++) {
            vec2 g = vec2(float(i), float(j));
            vec3 o = hash3(p + g);
            vec2 r = g - f + o.xy;
            float d = sqrt(dot(r, r));
            float ripple = max(mix(smoothstep(0.99, 0.999, max(cos(d - iTime * 2.0 + (o.x + o.y) * 5.0), 0.0)), 0.0, d), 0.0);
            va += ripple;
        }
    }
    return va;
}

void main() {
    vec2 uv = v_uv;
    float iTime = u_time * 0.7;
    float aspect = u_resolution.x / u_resolution.y;
    vec2 uvAspect = vec2(uv.x * aspect, uv.y);
    float freq = 6.0;

    float f = noise(freq * uvAspect, iTime);
    vec2 e = vec2(0.5) / u_resolution;
    vec2 eAspect = vec2(e.x * aspect, e.y);
    float cx = noise(freq * (uvAspect + eAspect), iTime);
    float cy = noise(freq * (uvAspect + eAspect.yx), iTime);
    vec2 n = vec2(cx - f, cy - f);
    vec2 distortion = vec2(n.x / aspect, n.y) * u_strength;

    vec4 col = texture(u_wallpaper, uv + distortion);
    fragColor = vec4(col.rgb, 1.0);
}
"""

FRAG_SNOW = """
#version 330 core
in vec2 v_uv;
out vec4 fragColor;
uniform float u_time;
uniform vec2 u_resolution;
uniform float u_strength;

void main() {
    float aspect = u_resolution.x / u_resolution.y;
    vec2 uv = v_uv;
    uv.x *= aspect;
    uv.y = 1.0 - uv.y;
    float iTime = u_time * 0.45;
    float snow = 0.0;

    for (int k = 0; k < 6; k++) {
        for (int i = 0; i < 12; i++) {
            float cellSize = 2.0 + (float(i) * 3.0);
            float downSpeed = 0.3 + (sin(iTime * 0.4 + float(k + i * 20)) + 1.0) * 0.00008;
            vec2 uvAnim = uv + vec2(
                0.01 * sin((iTime + float(k * 6185)) * 0.6 + float(i)) * (5.0 / float(i + 1)),
                downSpeed * (iTime + float(k * 1352)) * (1.0 / float(i + 1))
            );
            vec2 uvStep = (ceil((uvAnim) * cellSize - vec2(0.5, 0.5)) / cellSize);
            float x = fract(sin(dot(uvStep.xy, vec2(12.9898 + float(k) * 12.0, 78.233 + float(k) * 315.156))) * 43758.5453 + float(k) * 12.0) - 0.5;
            float y = fract(sin(dot(uvStep.xy, vec2(62.2364 + float(k) * 23.0, 94.674 + float(k) * 95.0))) * 62159.8432 + float(k) * 12.0) - 0.5;
            float randomMagnitude1 = sin(iTime * 2.5) * 0.7 / cellSize;
            float randomMagnitude2 = cos(iTime * 1.65) * 0.7 / cellSize;
            float d = 5.0 * distance((uvStep.xy + vec2(x * sin(y), y) * randomMagnitude1 + vec2(y, x) * randomMagnitude2), uvAnim.xy);
            float omiVal = fract(sin(dot(uvStep.xy, vec2(32.4691, 94.615))) * 31572.1684);
            if (omiVal < 0.03) {
                float newd = (x + 1.0) * 0.4 * clamp(1.9 - d * (15.0 + (x * 6.3)) * (cellSize / 1.4), 0.0, 1.0);
                snow += newd;
            }
        }
    }

    float snowAlpha = clamp(snow * 2.0, 0.0, 1.0) * u_strength;
    vec3 snowColor = vec3(1.0);
    fragColor = vec4(snowColor * snowAlpha, snowAlpha);
}
"""

FRAG_CLOUD = """
#version 330 core
in vec2 v_uv;
out vec4 fragColor;
uniform float u_time;
uniform vec2 u_resolution;
uniform float u_alternative;
uniform float u_strength;

float hash(vec2 p) {
    p = fract(p * vec2(234.34, 435.345));
    p += dot(p, p + 34.23);
    return fract(p.x * p.y);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float turbulence(vec2 p, float iTime) {
    float t = 0.0;
    float scale = 1.0;
    for (int i = 0; i < 5; i++) {
        t += abs(noise(p * scale + iTime * 0.1 * scale)) / scale;
        scale *= 2.0;
    }
    return t;
}

void main() {
    vec2 uv = v_uv;
    float timeSpeed, layerScale1, layerScale2, layerScale3;
    float flowSpeed1, flowSpeed2, densityMin, densityMax, baseOpacity, pulseAmount;

    if (u_alternative > 0.5) {
        timeSpeed = 0.3;
        layerScale1 = 1.0; layerScale2 = 2.5; layerScale3 = 2.0;
        flowSpeed1 = 0.00; flowSpeed2 = 0.02;
        densityMin = 0.1; densityMax = 0.9;
        baseOpacity = 0.75; pulseAmount = 0.05;
    } else {
        timeSpeed = 0.8;
        layerScale1 = 2.0; layerScale2 = 4.0; layerScale3 = 6.0;
        flowSpeed1 = 0.03; flowSpeed2 = 0.04;
        densityMin = 0.35; densityMax = 0.75;
        baseOpacity = 0.4; pulseAmount = 0.15;
    }

    float iTime = u_time * timeSpeed;
    vec2 flow1 = vec2(iTime * flowSpeed1, iTime * flowSpeed1 * 0.7);
    vec2 flow2 = vec2(-iTime * flowSpeed2, iTime * flowSpeed2 * 0.8);

    float fog1 = noise(uv * layerScale1 + flow1);
    float fog2 = noise(uv * layerScale2 + flow2);
    float fog3 = turbulence(uv * layerScale3, iTime);

    float fogPattern = fog1 * 0.5 + fog2 * 0.3 + fog3 * 0.2;
    float fogDensity = smoothstep(densityMin, densityMax, fogPattern);
    float pulse = sin(iTime * 0.4) * pulseAmount + (1.0 - pulseAmount);
    fogDensity *= pulse;

    vec3 hazeColor = vec3(0.88, 0.90, 0.93);
    float hazeOpacity = fogDensity * baseOpacity * u_strength;
    fragColor = vec4(hazeColor * hazeOpacity, hazeOpacity);
}
"""

FRAG_SUN = """
#version 330 core
in vec2 v_uv;
out vec4 fragColor;
uniform float u_time;
uniform vec2 u_resolution;
uniform sampler2D u_wallpaper;
uniform vec3 u_sunColor;
uniform float u_strength;

float hash(vec2 p) {
    p = fract(p * vec2(234.34, 435.345));
    p += dot(p, p + 34.23);
    return fract(p.x * p.y);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float sunRays(vec2 uv, vec2 sunPos, float iTime) {
    vec2 toSun = uv - sunPos;
    float angle = atan(toSun.y, toSun.x);
    float dist = length(toSun);
    float rayCount = 7.0;
    float rays = sin(angle * rayCount + sin(iTime * 0.25)) * 0.5 + 0.5;
    rays = pow(rays, 3.0);
    float falloff = 1.0 - smoothstep(0.0, 1.2, dist);
    return rays * falloff * 0.15;
}

float atmosphericShimmer(vec2 uv, float iTime) {
    float n1 = noise(uv * 5.0 + vec2(iTime * 0.1, iTime * 0.05));
    float n2 = noise(uv * 8.0 - vec2(iTime * 0.08, iTime * 0.12));
    float n3 = noise(uv * 12.0 + vec2(iTime * 0.15, -iTime * 0.1));
    return (n1 * 0.5 + n2 * 0.3 + n3 * 0.2) * 0.15;
}

float sunCore(vec2 uv, vec2 sunPos, float iTime) {
    vec2 toSun = uv - sunPos;
    float dist = length(toSun);
    float mainFlare = exp(-dist * 15.0) * 2.0;
    float flares = 0.0;
    for (int i = 1; i <= 3; i++) {
        vec2 flarePos = sunPos + toSun * float(i) * 0.3;
        float flareDist = length(uv - flarePos);
        float flareSize = 0.02 + float(i) * 0.01;
        flares += smoothstep(flareSize * 2.0, flareSize * 0.5, flareDist) * (0.3 / float(i));
    }
    float pulse = sin(iTime) * 0.1 + 0.9;
    return (mainFlare + flares) * pulse;
}

void main() {
    vec2 uv = v_uv;
    float iTime = u_time * 0.8;
    vec4 col = texture(u_wallpaper, uv);

    vec2 sunPos = vec2(0.85, 0.2);
    float aspect = u_resolution.x / u_resolution.y;
    vec2 uvAspect = vec2(uv.x * aspect, uv.y);
    vec2 sunPosAspect = vec2(sunPos.x * aspect, sunPos.y);

    float rays = sunRays(uvAspect, sunPosAspect, iTime);
    float shimmerEffect = atmosphericShimmer(uv, iTime);
    float flare = sunCore(uvAspect, sunPosAspect, iTime);

    vec3 sunColor = u_sunColor;
    vec3 shimmerColor = vec3(1.0, 0.98, 0.85);

    vec3 resultRGB = col.rgb;
    vec3 raysContribution = sunColor * rays * u_strength;
    float raysAlpha = rays * 0.4 * u_strength;
    resultRGB = raysContribution + resultRGB * (1.0 - raysAlpha);

    vec3 shimmerContribution = shimmerColor * shimmerEffect * u_strength;
    float shimmerAlpha = shimmerEffect * 0.1 * u_strength;
    resultRGB = shimmerContribution + resultRGB * (1.0 - shimmerAlpha);

    vec3 flareContribution = sunColor * flare * u_strength;
    float flareAlpha = clamp(flare, 0.0, 1.0) * 0.6 * u_strength;
    resultRGB = flareContribution + resultRGB * (1.0 - flareAlpha);

    resultRGB = mix(resultRGB, resultRGB * vec3(1.08, 1.04, 0.98), 0.15 * u_strength);
    fragColor = vec4(resultRGB, 1.0);
}
"""

FRAG_STARS = """
#version 330 core
in vec2 v_uv;
out vec4 fragColor;
uniform float u_time;
uniform vec2 u_resolution;
uniform float u_strength;

float hash(vec2 p) {
    p = fract(p * vec2(234.34, 435.345));
    p += dot(p, p + 34.23);
    return fract(p.x * p.y);
}

vec2 hash2(vec2 p) {
    p = fract(p * vec2(234.34, 435.345));
    p += dot(p, p + 34.23);
    return fract(vec2(p.x * p.y, p.y * p.x));
}

float stars(vec2 uv, float density, float iTime) {
    vec2 gridUV = uv * density;
    vec2 gridID = floor(gridUV);
    vec2 gridPos = fract(gridUV);
    float starField = 0.0;
    for (int y = -1; y <= 1; y++) {
        for (int x = -1; x <= 1; x++) {
            vec2 offset = vec2(float(x), float(y));
            vec2 cellID = gridID + offset;
            vec2 starPos = hash2(cellID);
            float starChance = hash(cellID + vec2(12.345, 67.890));
            if (starChance > 0.85) {
                vec2 toStar = (offset + starPos - gridPos);
                float dist = length(toStar) * density;  // 0 at star centre
                float brightness = hash(cellID + vec2(23.456, 78.901)) * 0.6 + 0.4;
                float twinkleSpeed = hash(cellID + vec2(34.567, 89.012)) * 3.0 + 2.0;
                float twinklePhase = iTime * twinkleSpeed + hash(cellID) * 6.28;
                float twinkle = pow(sin(twinklePhase) * 0.5 + 0.5, 3.0);
                float tw = 0.25 + twinkle * 0.75;
                // Glowing point: bright core that fades smoothly to zero instead of a
                // flat-filled disk (flat disks read as circles / snowballs).
                float core = exp(-dist * dist * 2.5);
                float halo = exp(-dist * 1.2) * 0.3;
                float star = (core + halo) * brightness * tw;
                // Diffraction spikes for the brighter stars -> the classic four-pointed
                // star. Extended beyond the core (and tapered along the ray) so the
                // shape reads as a star, not a circle.
                if (brightness > 0.6) {
                    float spikeAmt = smoothstep(0.6, 0.95, brightness);
                    vec2 a = abs(toStar) * density;
                    float spike = max(exp(-a.x * 2.0), exp(-a.y * 2.0));
                    spike *= exp(-dist * 0.8);
                    star += spike * 0.6 * spikeAmt * tw;
                }
                starField += star;
            }
        }
    }
    return starField;
}

void main() {
    vec2 uv = v_uv;
    float iTime = u_time * 0.1;
    float aspect = u_resolution.x / u_resolution.y;
    vec2 uvAspect = vec2(uv.x * aspect, uv.y);

    float stars1 = stars(uvAspect, 40.0, iTime);
    float stars2 = stars(uvAspect + vec2(0.5, 0.3), 25.0, iTime * 1.3);
    float stars3 = stars(uvAspect + vec2(0.25, 0.7), 15.0, iTime * 0.9);

    vec3 starColor1 = vec3(0.85, 0.9, 1.0);
    vec3 starColor2 = vec3(0.95, 0.97, 1.0);
    vec3 starColor3 = vec3(1.0, 0.98, 0.95);

    vec3 starsRGB = starColor1 * stars1 * 0.6 + starColor2 * stars2 * 0.8 + starColor3 * stars3 * 1.0;
    float starsAlpha = clamp(stars1 * 0.6 + stars2 * 0.8 + stars3, 0.0, 1.0) * u_strength;
    fragColor = vec4(min(starsRGB * u_strength, vec3(1.0)), starsAlpha);
}
"""

FRAG_STORM = """
#version 330 core
in vec2 v_uv;
out vec4 fragColor;
uniform float u_time;
uniform vec2 u_resolution;
uniform sampler2D u_wallpaper;
uniform float u_strength;

vec3 hash3(vec2 p) {
    vec3 q = vec3(dot(p, vec2(127.1, 311.7)),
                  dot(p, vec2(269.5, 183.3)),
                  dot(p, vec2(419.2, 371.9)));
    return fract(sin(q) * 43758.5453);
}

float rippleNoise(vec2 x, float iTime) {
    vec2 p = floor(x);
    vec2 f = fract(x);
    float va = 0.0;
    for (int j = -2; j <= 2; j++) {
        for (int i = -2; i <= 2; i++) {
            vec2 g = vec2(float(i), float(j));
            vec3 o = hash3(p + g);
            vec2 r = g - f + o.xy;
            float d = sqrt(dot(r, r));
            float ripple = max(mix(smoothstep(0.99, 0.999,
                max(cos(d - iTime * 2.0 + (o.x + o.y) * 5.0), 0.0)), 0.0, d), 0.0);
            va += ripple;
        }
    }
    return va;
}

float hash1(float n) {
    return fract(sin(n) * 43758.5453);
}

// Returns 0-1 lightning intensity from 2 independent randomised flash events.
float lightning(float iTime) {
    float flash = 0.0;
    for (int i = 0; i < 2; i++) {
        float fi = float(i);
        float period = 18.0 + hash1(fi * 13.71) * 12.0;  // 18-30 s cycle per bolt
        float offset = hash1(fi *  7.31) * period;
        float t = mod(iTime + offset, period);
        // Primary flash (~0.15 s)
        flash += smoothstep(0.0, 0.05, t) * (1.0 - smoothstep(0.05, 0.20, t));
        // Secondary (double) flash ~0.30 s later at half intensity
        float t2 = t - 0.30;
        if (t2 > 0.0)
            flash += smoothstep(0.0, 0.04, t2) * (1.0 - smoothstep(0.04, 0.14, t2)) * 0.55;
    }
    return clamp(flash, 0.0, 1.0);
}

void main() {
    vec2 uv = v_uv;
    float iTime = u_time * 0.9;  // slightly faster than rain
    float aspect = u_resolution.x / u_resolution.y;
    vec2 uvAspect = vec2(uv.x * aspect, uv.y);
    float freq = 8.0;  // denser ripple grid than plain rain (6.0)

    float f = rippleNoise(freq * uvAspect, iTime);
    vec2 e = vec2(0.5) / u_resolution;
    vec2 eAspect = vec2(e.x * aspect, e.y);
    float cx = rippleNoise(freq * (uvAspect + eAspect),    iTime);
    float cy = rippleNoise(freq * (uvAspect + eAspect.yx), iTime);
    vec2 n = vec2(cx - f, cy - f);
    // 1.6x heavier distortion than plain rain, modulated by u_strength
    vec2 distortion = vec2(n.x / aspect, n.y) * 1.6 * u_strength;

    vec4 col = texture(u_wallpaper, uv + distortion);

    // Heavy storm-cloud darkening — deep blue-grey overlay
    vec3 stormGrey = vec3(0.11, 0.13, 0.17);
    col.rgb = mix(col.rgb, stormGrey, 0.55);

    // Lightning flash — subtle cool-grey bloom; kept dim intentionally to
    // avoid harsh brightness spikes that can cause discomfort or trigger
    // photosensitivity. Reads as distant sheet lightning rather than a
    // direct strike.
    float flash = lightning(iTime);
    col.rgb = mix(col.rgb, vec3(0.78, 0.82, 0.90), flash * 0.35);

    fragColor = vec4(col.rgb, 1.0);
}
"""

FRAGMENTS = {
    "rain": FRAG_RAIN,
    "storm": FRAG_STORM,
    "snow": FRAG_SNOW,
    "cloud": FRAG_CLOUD,
    "sun": FRAG_SUN,
    "stars": FRAG_STARS,
}
# Effects that read the wallpaper as a texture and render opaque.
NEEDS_WALLPAPER = {"rain", "storm", "sun"}


def load_wallpaper_rgba():
    """Return (width, height, rgba_bytes) for the current wallpaper, or None."""
    path = None
    if CURRENT_WALLPAPER_LINK.exists():
        try:
            path = CURRENT_WALLPAPER_LINK.resolve()
        except Exception:
            path = None
    if (path is None or not path.exists()) and WALLPAPER_DIR.exists():
        for f in sorted(WALLPAPER_DIR.iterdir()):
            if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                path = f
                break
    if path is None or not path.exists():
        return None
    try:
        img = Image.open(path).convert("RGBA")
        w, h = img.size
        scale = min(1.0, MAX_TEXTURE_SIDE / float(max(w, h)))
        if scale < 1.0:
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
        return img.width, img.height, img.tobytes()
    except Exception as exc:
        print(f"\u26a0\ufe0f  Could not load wallpaper texture: {exc}")
        return None


def wallpaper_signature():
    """Cheap fingerprint of the current wallpaper for change detection."""
    try:
        if CURRENT_WALLPAPER_LINK.is_symlink() or CURRENT_WALLPAPER_LINK.exists():
            target = CURRENT_WALLPAPER_LINK.resolve()
            return (str(target), target.stat().st_mtime)
    except Exception:
        pass
    return None


class GLView:
    """Owns a GtkGLArea + its per-context moderngl resources for one monitor."""

    def __init__(self, app):
        self.app = app
        self.ctx = None
        self.programs = {}
        self.vaos = {}
        self.texture = None
        self.tex_gen = -1

        self.area = Gtk.GLArea()
        self.area.set_has_depth_buffer(False)
        self.area.set_has_stencil_buffer(False)
        try:
            self.area.set_allowed_apis(Gdk.GLAPI.GL)  # force desktop GL
        except Exception:
            pass
        self.area.connect("realize", self.on_realize)
        self.area.connect("render", self.on_render)
        self.area.connect("unrealize", self.on_unrealize)

    # ── GL lifecycle ─────────────────────────────────────────────────────────
    def on_realize(self, area):
        area.make_current()
        if area.get_error() is not None:
            print(f"\u274c GLArea error: {area.get_error()}")
            return
        try:
            self.ctx = moderngl.create_context(require=330)
        except Exception as exc:
            print(f"\u274c Failed to create GL context: {exc}")
            self.app.fail()
            return
        for name, frag in FRAGMENTS.items():
            try:
                prog = self.ctx.program(vertex_shader=VERTEX_SHADER, fragment_shader=frag)
                self.programs[name] = prog
                self.vaos[name] = self.ctx.vertex_array(prog, [])
            except Exception as exc:
                print(f"\u274c Shader compile failed for '{name}': {exc}")
                self.app.fail()
                return
        self._upload_texture()

    def on_unrealize(self, area):
        for vao in self.vaos.values():
            try:
                vao.release()
            except Exception:
                pass
        for prog in self.programs.values():
            try:
                prog.release()
            except Exception:
                pass
        if self.texture is not None:
            try:
                self.texture.release()
            except Exception:
                pass
        self.vaos.clear()
        self.programs.clear()
        self.texture = None
        self.ctx = None

    def _upload_texture(self):
        if self.ctx is None:
            return
        if self.texture is not None:
            try:
                self.texture.release()
            except Exception:
                pass
            self.texture = None
        wp = self.app.wallpaper
        if wp is None:
            # 1x1 neutral grey fallback so samplers still work.
            self.texture = self.ctx.texture((1, 1), 4, bytes((90, 90, 95, 255)))
        else:
            w, h, data = wp
            self.texture = self.ctx.texture((w, h), 4, data)
        self.texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.texture.repeat_x = False
        self.texture.repeat_y = False
        self.tex_gen = self.app.wallpaper_gen

    # ── Per-frame render ─────────────────────────────────────────────────────
    def on_render(self, area, gl_context):
        if self.ctx is None:
            return True

        if self.tex_gen != self.app.wallpaper_gen:
            self._upload_texture()

        scale = area.get_scale_factor() or 1
        w = max(1, area.get_width() * scale)
        h = max(1, area.get_height() * scale)

        fbo = self.ctx.detect_framebuffer()
        fbo.use()
        self.ctx.viewport = (0, 0, w, h)
        self.ctx.clear(0.0, 0.0, 0.0, 0.0)

        self.ctx.enable(moderngl.BLEND)
        # Premultiplied-alpha "over" blending (shaders output premultiplied rgb).
        self.ctx.blend_func = (moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA)

        t = self.app.elapsed()
        for effect, params in self.app.effects:
            prog = self.programs.get(effect)
            vao = self.vaos.get(effect)
            if prog is None or vao is None:
                continue
            self._set(prog, "u_time", t)
            self._set(prog, "u_resolution", (float(w), float(h)))
            self._set(prog, "u_alternative", float(params.get("alternative", 0.0)))
            self._set(prog, "u_sunColor", tuple(params.get("sun_color", (1.0, 0.95, 0.7))))
            self._set(prog, "u_strength", float(params.get("strength", 1.0)))
            if effect in NEEDS_WALLPAPER and self.texture is not None:
                self.texture.use(0)
                self._set(prog, "u_wallpaper", 0)
            vao.render(mode=moderngl.TRIANGLES, vertices=3)
        return True

    @staticmethod
    def _set(prog, name, value):
        try:
            prog[name].value = value
        except KeyError:
            pass
        except Exception:
            pass


class WeatherOverlay:
    """Top-level controller: windows (one per monitor), timers, lifecycle."""

    def __init__(self, force=None):
        self.force = force
        self.effects = resolve_effects(force)
        self.wallpaper = load_wallpaper_rgba()
        self.wallpaper_gen = 0
        self._wp_sig = wallpaper_signature()
        self.windows = []
        self.views = []
        self._start = time.monotonic()
        self._stopping = False
        self.app = Gtk.Application(application_id="dev.wallit.WeatherOverlay")
        self.app.connect("activate", self.on_activate)

    # ── time base shared by all monitors ─────────────────────────────────────
    def elapsed(self):
        return time.monotonic() - self._start

    # ── startup ──────────────────────────────────────────────────────────────
    def on_activate(self, app):
        print(f"\U0001f3ac Weather overlay v3 (GPU): effects={self.effects}")
        display = Gdk.Display.get_default()
        if display is None:
            print("\u274c No display available")
            app.quit()
            return

        # Make GTK window backgrounds transparent so the wallpaper shows through.
        css = Gtk.CssProvider()
        css.load_from_data(b"window, .background { background: transparent; }")
        Gtk.StyleContext.add_provider_for_display(
            display, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        monitors = display.get_monitors()
        n = monitors.get_n_items()
        if n == 0:
            self._make_window(None)
        else:
            for i in range(n):
                self._make_window(monitors.get_item(i))

        # Lifecycle timers.
        GLib.timeout_add(150, self._check_stop)
        GLib.timeout_add_seconds(5, self._check_wallpaper)
        GLib.timeout_add_seconds(900, self._refresh_weather)
        for sig in (signal.SIGINT, signal.SIGTERM):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, self._on_signal)

    def _make_window(self, monitor):
        try:
            win = Gtk.ApplicationWindow(application=self.app)
            Gtk4LayerShell.init_for_window(win)
            # Use the BOTTOM layer (not BACKGROUND). swww renders the wallpaper on
            # the BACKGROUND layer; wlr-layer-shell orders the layers bottom-to-top
            # as Background -> Bottom -> (toplevel windows) -> Top -> Overlay. Putting
            # the overlay on BOTTOM guarantees it composites *above* the wallpaper but
            # *below* normal application windows. Using BACKGROUND (the wallpaper's own
            # layer) let the wallpaper surface stack over/clobber the overlay, so the
            # animation appeared as a stray separate surface instead of on the wallpaper.
            Gtk4LayerShell.set_layer(win, Gtk4LayerShell.Layer.BOTTOM)
            if monitor is not None:
                Gtk4LayerShell.set_monitor(win, monitor)
            for edge in (Gtk4LayerShell.Edge.TOP, Gtk4LayerShell.Edge.BOTTOM,
                         Gtk4LayerShell.Edge.LEFT, Gtk4LayerShell.Edge.RIGHT):
                Gtk4LayerShell.set_anchor(win, edge, True)
            Gtk4LayerShell.set_exclusive_zone(win, -1)
            Gtk4LayerShell.set_namespace(win, "wall-it-weather")
            try:
                Gtk4LayerShell.set_keyboard_mode(win, Gtk4LayerShell.KeyboardMode.NONE)
            except Exception:
                pass

            view = GLView(self)
            win.set_child(view.area)
            win.connect("map", self._on_map)
            win.present()

            # Continuous, vsync-aligned redraw.
            win.add_tick_callback(lambda widget, clock: self._tick(view))

            self.windows.append(win)
            self.views.append(view)
        except Exception as exc:
            import traceback
            print(f"\u274c Failed to create overlay window: {exc}")
            traceback.print_exc()
            self.fail()

    def _on_map(self, win):
        # Empty input region => fully click-through.
        if not HAVE_CAIRO:
            return
        surface = win.get_surface()
        if surface is not None:
            try:
                surface.set_input_region(cairo.Region())
            except Exception:
                pass

    def _tick(self, view):
        view.area.queue_render()
        return GLib.SOURCE_CONTINUE

    # ── timers ───────────────────────────────────────────────────────────────
    def _check_stop(self):
        if STOP_FILE.exists():
            print("\U0001f3ac Stop file found - exiting")
            self.quit()
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _check_wallpaper(self):
        sig = wallpaper_signature()
        if sig != self._wp_sig:
            self._wp_sig = sig
            new_wp = load_wallpaper_rgba()
            if new_wp is not None:
                self.wallpaper = new_wp
                self.wallpaper_gen += 1
                print("\U0001f5bc\ufe0f  Wallpaper changed - reloading texture")
        return GLib.SOURCE_CONTINUE

    def _refresh_weather(self):
        if self.force or os.environ.get("WALLIT_FORCE_WEATHER"):
            return GLib.SOURCE_CONTINUE
        effects = resolve_effects()
        if effects != self.effects:
            print(f"\U0001f3ac Weather changed: {self.effects} -> {effects}")
            self.effects = effects
        return GLib.SOURCE_CONTINUE

    def _on_signal(self):
        print("\U0001f3ac Signal received - exiting")
        self.quit()
        return GLib.SOURCE_REMOVE

    # ── shutdown ─────────────────────────────────────────────────────────────
    def fail(self):
        if not self._stopping:
            print("\u274c GPU initialisation failed - exiting")
            self.quit()

    def quit(self):
        if self._stopping:
            return
        self._stopping = True
        for win in self.windows:
            try:
                win.destroy()
            except Exception:
                pass
        self.app.quit()

    def run(self):
        return self.app.run(None)


def main():
    parser = argparse.ArgumentParser(description="Wall-IT GPU weather overlay")
    parser.add_argument("--force", help="Force a condition/effect (rain, storm, snow, cloud, fog, sun, clear-day, sunset, dawn, stars, night, partly-cloudy-day, partly-cloudy-night, partly-cloudy-dawn, partly-cloudy-sunset)")
    args, _ = parser.parse_known_args()

    # Clear any stale stop file from a previous run.
    try:
        STOP_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    overlay = WeatherOverlay(force=args.force)
    return overlay.run()


if __name__ == "__main__":
    sys.exit(main())
