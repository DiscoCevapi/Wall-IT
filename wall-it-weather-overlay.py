#!/usr/bin/env python3
"""
Wall-IT Weather Overlay v2
Renders animated weather particles directly onto wallpaper using PIL.
Professional-grade effects with antialiasing, fade transitions, and smooth 30 FPS.
"""

import os
import sys
import math
import random as _rand
import json
import time as _time
import urllib.request
import signal
from pathlib import Path
from collections import deque
import colorsys

PIL_AVAILABLE = False
try:
    from PIL import Image, ImageDraw, ImageFilter, ImageChops
    PIL_AVAILABLE = True
except ImportError:
    print("❌ PIL/Pillow required. Install: paru -S python-pillow")
    sys.exit(1)

# ─── Weather data ───
WTTTR_CONDITION_MAP = {
    'Clear': 'clear-day', 'Sunny': 'clear-day', 'Partly cloudy': 'partly-cloudy-day',
    'Cloudy': 'cloudy', 'Overcast': 'cloudy', 'Mist': 'fog', 'Fog': 'fog',
    'Freezing fog': 'fog', 'Patchy rain possible': 'rain', 'Light drizzle': 'rain',
    'Patchy light drizzle': 'rain', 'Light rain': 'rain', 'Moderate rain': 'rain',
    'Heavy rain': 'rain', 'Torrential rain': 'rain', 'Light rain shower': 'rain',
    'Moderate rain shower': 'rain', 'Heavy rain shower': 'rain',
    'Patchy snow possible': 'snow', 'Light snow': 'snow', 'Moderate snow': 'snow',
    'Heavy snow': 'snow', 'Light snow shower': 'snow', 'Moderate snow shower': 'snow',
    'Heavy snow shower': 'snow', 'Light sleet': 'snow', 'Moderate sleet': 'snow',
    'Thundery outbreaks possible': 'rain', 'Patchy light rain with thunder': 'rain',
    'Moderate or heavy rain with thunder': 'rain', 'Blowing snow': 'snow',
    'Blizzard': 'snow', 'Hail': 'snow',
}

WEATHER_ANIM_MAP = {
    'rain': 'rain', 'snow': 'snow', 'sleet': 'snow', 'fog': 'fog',
    'wind': 'wind', 'cloudy': 'cloudy', 'partly-cloudy-day': 'partly_cloudy',
    'partly-cloudy-night': 'partly_cloudy_night', 'clear-night': 'night', 'clear-day': 'sunny',
}

# ─── Visual tuning profiles ───
DEFAULT_VISUAL_PROFILE = {
    'count_mult': 1.0,
    'opacity_mult': 1.0,
    'speed_mult': 1.0,
    'blur_radius': 0.0,
    'tint_strength': 0.0,
    'ambient_dim': 0.0,
}

VISUAL_PROFILES = {
    'rain':               {'count_mult': 0.70, 'opacity_mult': 0.78, 'speed_mult': 0.92, 'blur_radius': 0.40, 'tint_strength': 0.16, 'ambient_dim': 0.08},
    'snow':               {'count_mult': 0.78, 'opacity_mult': 0.85, 'speed_mult': 0.90, 'blur_radius': 0.50, 'tint_strength': 0.10, 'ambient_dim': 0.03},
    'fog':                {'count_mult': 0.75, 'opacity_mult': 0.75, 'speed_mult': 0.80, 'blur_radius': 1.10, 'tint_strength': 0.18, 'ambient_dim': 0.06},
    'cloudy':             {'count_mult': 0.85, 'opacity_mult': 0.80, 'speed_mult': 0.90, 'blur_radius': 0.85, 'tint_strength': 0.08, 'ambient_dim': 0.03},
    'partly_cloudy':      {'count_mult': 0.82, 'opacity_mult': 0.84, 'speed_mult': 0.90, 'blur_radius': 0.55, 'tint_strength': 0.05, 'ambient_dim': 0.02},
    'partly_cloudy_night':{'count_mult': 0.80, 'opacity_mult': 0.85, 'speed_mult': 0.90, 'blur_radius': 0.55, 'tint_strength': 0.08, 'ambient_dim': 0.04},
    'sunny':              {'count_mult': 0.70, 'opacity_mult': 0.72, 'speed_mult': 0.85, 'blur_radius': 0.35, 'tint_strength': 0.04, 'ambient_dim': 0.00},
    'clear-day':          {'count_mult': 0.70, 'opacity_mult': 0.72, 'speed_mult': 0.85, 'blur_radius': 0.35, 'tint_strength': 0.04, 'ambient_dim': 0.00},
    'night':              {'count_mult': 0.68, 'opacity_mult': 0.72, 'speed_mult': 0.86, 'blur_radius': 0.20, 'tint_strength': 0.06, 'ambient_dim': 0.03},
    'clear-night':        {'count_mult': 0.68, 'opacity_mult': 0.72, 'speed_mult': 0.86, 'blur_radius': 0.20, 'tint_strength': 0.06, 'ambient_dim': 0.03},
    'sunset':             {'count_mult': 0.74, 'opacity_mult': 0.80, 'speed_mult': 0.90, 'blur_radius': 0.50, 'tint_strength': 0.10, 'ambient_dim': 0.03},
    'sunset_transition':  {'count_mult': 0.74, 'opacity_mult': 0.80, 'speed_mult': 0.90, 'blur_radius': 0.50, 'tint_strength': 0.10, 'ambient_dim': 0.03},
    'dawn':               {'count_mult': 0.74, 'opacity_mult': 0.82, 'speed_mult': 0.90, 'blur_radius': 0.48, 'tint_strength': 0.09, 'ambient_dim': 0.02},
    'wind':               {'count_mult': 0.70, 'opacity_mult': 0.72, 'speed_mult': 0.92, 'blur_radius': 0.20, 'tint_strength': 0.04, 'ambient_dim': 0.01},
}

def get_visual_profile(anim_type):
    p = dict(DEFAULT_VISUAL_PROFILE)
    p.update(VISUAL_PROFILES.get(anim_type, {}))
    return p


def analyze_wallpaper_style(wallpaper_path):
    """Sample wallpaper to derive brightness/saturation/warmth cues."""
    try:
        img = Image.open(wallpaper_path).convert('RGB').resize((96, 96), Image.BILINEAR)
        px = list(img.getdata())
        if not px:
            raise ValueError("empty image")
        n = len(px)
        avg_r = sum(p[0] for p in px) / n
        avg_g = sum(p[1] for p in px) / n
        avg_b = sum(p[2] for p in px) / n

        brightness = (0.2126 * avg_r + 0.7152 * avg_g + 0.0722 * avg_b) / 255.0
        _, sat, _ = colorsys.rgb_to_hsv(avg_r / 255.0, avg_g / 255.0, avg_b / 255.0)
        warmth = (avg_r - avg_b) / 255.0  # negative = cool, positive = warm

        return {
            'brightness': max(0.0, min(1.0, brightness)),
            'saturation': max(0.0, min(1.0, sat)),
            'warmth': max(-1.0, min(1.0, warmth)),
            'avg_rgb': (int(avg_r), int(avg_g), int(avg_b)),
        }
    except Exception:
        return {
            'brightness': 0.5,
            'saturation': 0.5,
            'warmth': 0.0,
            'avg_rgb': (128, 128, 128),
        }


def build_scene_context(anim_type, wallpaper_metrics):
    """Merge weather profile + wallpaper metrics into final scene controls."""
    profile = get_visual_profile(anim_type)
    b = wallpaper_metrics['brightness']
    s = wallpaper_metrics['saturation']
    w = wallpaper_metrics['warmth']

    # Dark wallpapers: reduce particle alpha/intensity
    alpha_scale = 0.78 + 0.55 * b
    # Highly saturated wallpapers: reduce overlay competition
    alpha_scale *= (1.05 - 0.28 * s)
    alpha_scale *= profile['opacity_mult']
    alpha_scale = max(0.45, min(1.15, alpha_scale))

    # Count / speed
    count_scale = max(0.55, min(1.10, profile['count_mult'] * (0.92 + 0.16 * b)))
    speed_scale = max(0.70, min(1.15, profile['speed_mult'] * (0.9 + 0.2 * b)))

    # Color tint compensation
    cool_bias = max(0.0, -w)
    warm_bias = max(0.0, w)

    tint_strength = profile['tint_strength']
    rain_tint = (
        int(150 + 25 * warm_bias),
        int(185 + 18 * warm_bias),
        int(228 + 20 * cool_bias),
    )
    fog_tint = (
        int(205 + 16 * warm_bias),
        int(215 + 10 * warm_bias),
        int(228 + 18 * cool_bias),
    )
    snow_tint = (
        int(236 + 8 * warm_bias),
        int(245 + 6 * warm_bias),
        int(252 + 10 * cool_bias),
    )

    return {
        'anim_type': anim_type,
        'alpha_scale': alpha_scale,
        'count_scale': count_scale,
        'speed_scale': speed_scale,
        'blur_radius': profile['blur_radius'],
        'ambient_dim': profile['ambient_dim'],
        'tint_strength': tint_strength,
        'rain_tint': rain_tint,
        'fog_tint': fog_tint,
        'snow_tint': snow_tint,
    }


def resolve_animation_type():
    """Resolve animation type from weather or time fallback."""
    return fetch_weather_condition()


def fetch_weather_condition():
    """Fetch current weather, return animation type string."""
    try:
        url = "https://wttr.in/?format=j1"
        req = urllib.request.Request(url, headers={'User-Agent': 'Wall-IT-Overlay/2.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        desc = data.get('current_condition', [{}])[0].get('weatherDesc', [{}])[0].get('value', '')
        for wttr_key, our_cond in WTTTR_CONDITION_MAP.items():
            if wttr_key.lower() in desc.lower() or desc.lower() in wttr_key.lower():
                return WEATHER_ANIM_MAP.get(our_cond, 'sunny')
        d = desc.lower()
        if any(w in d for w in ['rain','drizzle','shower']): return 'rain'
        if any(w in d for w in ['snow','sleet','blizzard']): return 'snow'
        if any(w in d for w in ['fog','mist','haze']): return 'fog'
        if 'cloud' in d or 'overcast' in d: return 'clouds'
        if 'clear' in d or 'sunny' in d: return 'sunny'
    except Exception as e:
        print(f"⚠️ Weather fetch: {e}")
    hour = _time.localtime().tm_hour
    if hour < 7 or hour >= 20: return 'night'
    if 16 <= hour < 20: return 'sunset'
    return 'sunny'


# ─── Particle System v2 ───

def make_star_particles(count, sw, sh):
    """Stars with varied twinkle, size, and color warmth."""
    particles = []
    for _ in range(count):
        warmth = _rand.uniform(0.7, 1.0)
        depth = _rand.uniform(0.5, 1.0)
        particles.append({
            'x': _rand.uniform(0, sw), 'y': _rand.uniform(0, sh * 0.55),
            'brightness': _rand.uniform(0.4, 1.0),
            'twinkle_speed': _rand.uniform(0.02, 0.15),
            'size': _rand.uniform(1.5, 5.0) * depth,
            'twinkle_phase': _rand.uniform(0, 6.283),
            'warmth': warmth,
            'depth': depth,
            'base_r': int(200 + 55 * warmth),
            'base_g': int(200 + 55 * warmth),
            'base_b': int(180 + 75 * warmth),
            'type': 'star',
        })
    return particles


def make_cloud_particles(count, sw, sh, night=False):
    """Soft, layered clouds with depth parallax and varied opacity."""
    particles = []
    for _ in range(count):
        depth = _rand.uniform(0.3, 1.0)  # 0.3 = far/slow, 1.0 = close/fast
        # Pre-generate layer variation so it's stable per frame
        layer_variations = []
        for li in range(_rand.randint(3, 6)):
            layer_variations.append({
                'scale': 1.0 + li * 0.15,
                'alpha_factor': 0.65 - li * 0.09,
                'y_offset': li * 0.07,
                'bump_variations': [_rand.uniform(0.88, 1.12) for _ in range(5)],
                'y_jitter': [_rand.uniform(-1.5, 1.5) for _ in range(5)],
            })
        particles.append({
            'x': _rand.uniform(0, sw), 'y': _rand.uniform(0, sh * 0.45),
            'size': _rand.uniform(50, 160) * depth,
            'speed_x': _rand.uniform(-0.5, 0.5) * depth,
            'opacity': _rand.uniform((0.08 if night else 0.1), (0.32 if night else 0.4)) * depth,
            'type': 'cloud',
            'layers': layer_variations,
            'depth': depth,
            'night': night,
        })
    return particles


def make_sun_rays(count, sw, sh, is_sunset=False, is_dawn=False):
    """Warm sun rays with gentle pulsing."""
    particles = []
    for _ in range(count):
        if is_sunset:
            hue = _rand.choice([(255, 100, 50), (255, 150, 50), (230, 180, 80)])
        elif is_dawn:
            hue = _rand.choice([(255, 180, 130), (255, 200, 100), (230, 200, 150)])
        else:
            hue = _rand.choice([(255, 230, 170), (255, 235, 180), (255, 240, 190)])
        particles.append({
            'x': _rand.uniform(sw * 0.25, sw * 0.75),
            'y': _rand.uniform(sh * 0.05, sh * 0.4),
            'angle': _rand.uniform(-0.5, 0.5),
            'length': _rand.uniform(60, 200),
            'thickness': _rand.uniform(2.0, 6.5),
            'opacity': _rand.uniform(0.2, 0.5),
            'pulse_speed': _rand.uniform(0.04, 0.10),
            'pulse_phase': _rand.uniform(0, 6.283),
            'ray_type': _rand.choice(['ray', 'glow', 'beam']),
            'hue': hue,
            'type': 'sun_ray',
        })
    return particles


def make_atmosphere_rays(count, sw, sh):
    """Atmospheric scattered light rays."""
    particles = []
    for _ in range(count):
        hue = _rand.choice([(200, 220, 255), (220, 220, 240), (240, 240, 255)])
        particles.append({
            'x': _rand.uniform(0, sw), 'y': _rand.uniform(sh * 0.1, sh * 0.6),
            'angle': _rand.uniform(0, 6.283),
            'length': _rand.uniform(30, 150),
            'thickness': _rand.uniform(1.0, 4.0),
            'opacity': _rand.uniform(0.12, 0.35),
            'pulse_speed': _rand.uniform(0.03, 0.08),
            'pulse_phase': _rand.uniform(0, 6.283),
            'ray_type': _rand.choice(['ray', 'glow', 'atmosphere']),
            'hue': hue,
            'type': 'sun_ray',
        })
    return particles


def make_rain_particles(count, sw, sh):
    """Rain streaks with depth, wind angle, and splash particles."""
    particles = []
    splashes = []
    for _ in range(count):
        depth = _rand.uniform(0.4, 1.0)
        angle = _rand.uniform(-0.12, 0.18)
        particles.append({
            'x': _rand.uniform(0, sw), 'y': _rand.uniform(-300, sh),
            'speed': _rand.uniform(18, 38) * depth,
            'length': _rand.uniform(18, 55) * depth,
            'thickness': _rand.uniform(1.2, 2.8) * depth,
            'angle': angle,
            'alpha': _rand.uniform(0.35, 0.85) * depth,
            'depth': depth,
        })
    # Pre-generate splash positions at bottom
    for _ in range(count // 8):
        splashes.append({
            'x': _rand.uniform(0, sw), 'y': sh - _rand.uniform(5, 40),
            'size': _rand.uniform(1.5, 4.0), 'alpha': _rand.uniform(0.1, 0.35),
            'phase': _rand.uniform(0, 6.283), 'speed': _rand.uniform(0.1, 0.3),
        })
    return particles + splashes


def make_snow_particles(count, sw, sh):
    """Snowflakes with realistic drift and oscillation."""
    particles = []
    for _ in range(count):
        particles.append({
            'x': _rand.uniform(0, sw), 'y': _rand.uniform(-300, sh),
            'speed': _rand.uniform(1.0, 4.5),
            'size': _rand.uniform(3, 11),
            'drift': _rand.uniform(-1.5, 1.5),
            'oscillation': _rand.uniform(0, 6.283),
            'oscillation_speed': _rand.uniform(0.02, 0.08),
            'alpha': _rand.uniform(0.4, 0.9),
        })
    return particles


def make_fog_particles(count, sw, sh):
    """Dense fog with varied drift and size."""
    particles = []
    for _ in range(count):
        particles.append({
            'x': _rand.uniform(-200, sw + 200), 'y': _rand.uniform(0, sh),
            'speed_x': _rand.uniform(-0.6, 0.6),
            'speed_y': _rand.uniform(-0.15, 0.15),
            'size': _rand.uniform(40, 120),
            'opacity': _rand.uniform(0.05, 0.2),
            'drift': _rand.uniform(0, 6.283),
            'drift_speed': _rand.uniform(0.005, 0.02),
        })
    return particles


def make_wind_particles(count, sw, sh):
    """Wind streaks that flow across the screen."""
    particles = []
    for _ in range(count):
        particles.append({
            'x': _rand.uniform(0, sw), 'y': _rand.uniform(0, sh),
            'speed_x': _rand.uniform(2.0, 7.0),
            'speed_y': _rand.uniform(-0.5, 0.5),
            'length': _rand.uniform(20, 60),
            'opacity': _rand.uniform(0.1, 0.35),
            'type': 'wind',
        })
    return particles


def init_particles(anim_type, sw, sh, scene_ctx=None):
    """Initialize particle system based on animation type."""
    scene_ctx = scene_ctx or {}
    count_scale = scene_ctx.get('count_scale', 1.0)

    if anim_type in ('clear-night', 'night'):
        return make_star_particles(max(40, int(140 * count_scale)), sw, sh)
    elif anim_type in ('partly_cloudy', 'partly_cloudy_day', 'partly-cloudy-day'):
        return make_cloud_particles(max(8, int(22 * count_scale)), sw, sh) + make_sun_rays(max(8, int(20 * count_scale)), sw, sh)
    elif anim_type in ('partly_cloudy_night', 'partly-cloudy-night'):
        return make_cloud_particles(max(8, int(18 * count_scale)), sw, sh, night=True) + make_star_particles(max(25, int(80 * count_scale)), sw, sh)
    elif anim_type in ('clear-day', 'sunny', 'noon', 'morning', 'afternoon', 'day'):
        return make_sun_rays(max(10, int(45 * count_scale)), sw, sh)
    elif anim_type in ('cloudy',):
        return make_cloud_particles(max(12, int(30 * count_scale)), sw, sh) + make_atmosphere_rays(max(8, int(20 * count_scale)), sw, sh)
    elif anim_type in ('sunset', 'sunset_transition'):
        return make_sun_rays(max(10, int(35 * count_scale)), sw, sh, is_sunset=True) + make_cloud_particles(max(8, int(13 * count_scale)), sw, sh)
    elif anim_type in ('dawn',):
        return make_sun_rays(max(10, int(35 * count_scale)), sw, sh, is_dawn=True) + make_cloud_particles(max(8, int(10 * count_scale)), sw, sh)
    elif anim_type == 'rain':
        return make_rain_particles(max(140, int(580 * (sw / 1920) * count_scale)), sw, sh)
    elif anim_type == 'snow':
        return make_snow_particles(max(120, int(280 * (sw / 1920) * count_scale)), sw, sh)
    elif anim_type == 'fog':
        return make_fog_particles(max(80, int(220 * (sw / 1920) * count_scale)), sw, sh)
    elif anim_type == 'wind':
        return make_wind_particles(max(50, int(120 * (sw / 1920) * count_scale)), sw, sh)
    return []


def update_particles(particles, anim_type, sw, sh, scene_ctx=None):
    """Update particle positions each frame."""
    scene_ctx = scene_ctx or {}
    speed_scale = scene_ctx.get('speed_scale', 1.0)

    for p in particles:
        pt = p.get('type', '')
        if anim_type == 'rain':
            if 'speed' in p and 'angle' in p:  # Rain drop
                p['y'] += p['speed'] * speed_scale
                p['x'] += p.get('angle', 0) * p['speed'] * 0.3 * speed_scale
                if p['y'] > sh + 100:
                    p['y'] = _rand.uniform(-150, -50)
                    p['x'] = _rand.uniform(0, sw)
            elif 'phase' in p:  # Splash
                p['phase'] += p.get('speed', 0.1) * speed_scale
                p['alpha'] = max(0, p.get('alpha', 0.2) - 0.0065)
                if p['alpha'] <= 0.01:
                    p['alpha'] = _rand.uniform(0.08, 0.28)
                    p['size'] = _rand.uniform(1.2, 3.3)
                    p['x'] = _rand.uniform(0, sw)
                    p['y'] = sh - _rand.uniform(5, 40)
        elif anim_type == 'snow':
            depth = min(1.0, max(0.45, p.get('size', 5) / 11.0))
            p['y'] += p['speed'] * (0.8 + 0.4 * depth) * speed_scale
            p['oscillation'] += p['oscillation_speed'] * speed_scale
            p['x'] += p['drift'] * (0.7 + 0.5 * depth) * speed_scale + math.sin(p['oscillation']) * (0.35 + 0.6 * depth)
            if p['y'] > sh + 80:
                p['y'] = _rand.uniform(-150, -50)
                p['x'] = _rand.uniform(0, sw)
        elif anim_type == 'fog':
            p['x'] += p['speed_x'] * speed_scale
            p['y'] += p['speed_y'] * speed_scale
            if p['x'] > sw + 200: p['x'] = -200
            elif p['x'] < -200: p['x'] = sw + 200
            if p['y'] > sh: p['y'] = 0
            elif p['y'] < 0: p['y'] = sh
            p['drift'] += p['drift_speed'] * speed_scale
        elif pt == 'cloud':
            p['x'] += p.get('speed_x', 0) * speed_scale
            margin = p['size'] * 2
            if p['x'] > sw + margin: p['x'] = -margin
            elif p['x'] < -margin: p['x'] = sw + margin
        elif pt == 'wind':
            p['x'] += p['speed_x'] * speed_scale
            p['y'] += p['speed_y'] * speed_scale
            if p['x'] > sw + 50: p['x'] = -50; p['y'] = _rand.uniform(0, sh)
            elif p['x'] < -50: p['x'] = sw + 50; p['y'] = _rand.uniform(0, sh)
            if p['y'] > sh + 20: p['y'] = -20; p['x'] = _rand.uniform(0, sw)
            elif p['y'] < -20: p['y'] = sh + 20; p['x'] = _rand.uniform(0, sw)


def draw_aa_line(draw, x1, y1, x2, y2, fill, width=1):
    """Draw an antialiased line using multiple sub-pixel samples."""
    if width <= 1:
        draw.line([x1, y1, x2, y2], fill=fill, width=1)
        return
    # Draw slightly thicker for smoother appearance
    draw.line([x1, y1, x2, y2], fill=fill, width=width)


def render_frame(img, anim_type, t, particles, sw, sh, fade_alpha=1.0, scene_ctx=None):
    """
    Render weather particles onto a PIL image overlay.
    fade_alpha: 0.0-1.0 for fade transitions.
    """
    scene_ctx = scene_ctx or {}
    alpha_scale = scene_ctx.get('alpha_scale', 1.0)
    tint_strength = scene_ctx.get('tint_strength', 0.0)
    rain_tint = scene_ctx.get('rain_tint', (160, 195, 240))
    fog_tint = scene_ctx.get('fog_tint', (210, 220, 230))
    snow_tint = scene_ctx.get('snow_tint', (245, 255, 255))
    draw = ImageDraw.Draw(img)

    if anim_type in ('clear-night', 'night'):
        for p in particles:
            b = p['brightness'] * (0.3 + 0.7 * abs(math.sin(t * p['twinkle_speed'] + p['twinkle_phase'])))
            sz = p['size'] * (0.8 + b * 0.7)
            a = int(180 * b * fade_alpha * alpha_scale)
            r = min(255, p['base_r'] + int(55 * b))
            g = min(255, p['base_g'] + int(55 * b))
            bv = min(255, p['base_b'] + int(75 * b))
            # Outer glow
            draw.ellipse([p['x']-sz*2.5, p['y']-sz*2.5, p['x']+sz*2.5, p['y']+sz*2.5],
                         fill=(r, g, bv, a // 4))
            # Core
            draw.ellipse([p['x']-sz, p['y']-sz, p['x']+sz, p['y']+sz],
                         fill=(r, g, bv, a))
            if b > 0.5:
                draw.ellipse([p['x']-sz*0.4, p['y']-sz*0.4, p['x']+sz*0.4, p['y']+sz*0.4],
                             fill=(255, 255, 240, a))

    elif anim_type in ('partly_cloudy', 'partly_cloudy_day', 'partly-cloudy-day'):
        for p in particles:
            if p.get('type') == 'cloud':
                for li, layer in enumerate(p.get('layers', [])):
                    layer_scale = layer['scale']
                    layer_alpha = int(110 * p['opacity'] * fade_alpha * layer['alpha_factor'] * alpha_scale)
                    r = int(195 + 60 * (1 - p['opacity']))
                    g = int(210 + 45 * (1 - p['opacity']))
                    b = int(225 + 30 * (1 - p['opacity']))
                    for i in range(5):  # 5 bumps for organic shape
                        ox = (i - 2) * p['size'] * 0.26 * layer_scale
                        oy = li * p['size'] * layer['y_offset'] + layer['y_jitter'][i]
                        sz = p['size'] * 0.44 * layer_scale * layer['bump_variations'][i]
                        draw.ellipse([p['x']+ox-sz, p['y']+oy-sz, p['x']+ox+sz, p['y']+oy+sz],
                                     fill=(r, g, b, layer_alpha))
            elif p.get('type') == 'sun_ray':
                pulse = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(t * p['pulse_speed'] + p['pulse_phase']))
                op = p['opacity'] * pulse * fade_alpha
                cr, cg, cb = p['hue']
                rt = p.get('ray_type')
                ex = p['x'] + math.cos(p['angle']) * p['length'] * pulse
                ey = p['y'] + math.sin(p['angle']) * p['length'] * pulse
                if rt == 'ray':
                    draw.line([p['x'], p['y'], ex, ey],
                              fill=(cr, cg, cb, int(200*op)),
                              width=max(1, int(p['thickness']*1.3)))
                elif rt == 'glow':
                    r = int(30 * pulse)
                    draw.ellipse([p['x']-r, p['y']-r, p['x']+r, p['y']+r],
                                 fill=(cr, cg, cb, int(100*op)))
                elif rt == 'beam':
                    wf = max(1, int(p['thickness']*1.5))
                    x1, y1, x2, y2 = p['x']-wf, p['y'], p['x']+wf, p['y']+int(p['length']*pulse)
                    draw.rectangle([x1, y1, x2, y2],
                                   fill=(cr, cg, cb, int(80*op)))

    elif anim_type in ('partly_cloudy_night', 'partly-cloudy-night'):
        for p in particles:
            if p.get('type') == 'cloud':
                for li, layer in enumerate(p.get('layers', [])):
                    layer_scale = layer['scale']
                    layer_alpha = int(95 * p['opacity'] * fade_alpha * layer['alpha_factor'] * alpha_scale)
                    for i in range(5):
                        ox = (i - 2) * p['size'] * 0.26 * layer_scale
                        oy = li * p['size'] * layer['y_offset'] + layer['y_jitter'][i]
                        sz = p['size'] * 0.4 * layer_scale * layer['bump_variations'][i]
                        draw.ellipse([p['x']+ox-sz, p['y']+oy-sz, p['x']+ox+sz, p['y']+oy+sz],
                                     fill=(55, 70, 95, layer_alpha))
            elif p.get('type') == 'star':
                b = p['brightness'] * (0.3 + 0.7 * abs(math.sin(t * p['twinkle_speed'] + p['twinkle_phase'])))
                sz = p['size'] * b
                a = int(200 * b * fade_alpha * alpha_scale)
                draw.ellipse([p['x']-sz*2, p['y']-sz*2, p['x']+sz*2, p['y']+sz*2],
                             fill=(200, 220, 255, a // 3))
                draw.ellipse([p['x']-sz, p['y']-sz, p['x']+sz, p['y']+sz],
                             fill=(230, 240, 255, a))

    elif anim_type in ('clear-day', 'sunny', 'noon', 'morning', 'afternoon', 'day'):
        it = 1.2 if anim_type in ('clear-day','sunny','day','afternoon') else (1.3 if anim_type=='noon' else 1.0)
        for p in particles:
            if p.get('type') == 'sun_ray':
                pulse = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(t * p['pulse_speed'] + p['pulse_phase']))
                op = p['opacity'] * pulse * it * fade_alpha * alpha_scale
                cr, cg, cb = p['hue']
                rt = p.get('ray_type')
                ex = p['x'] + math.cos(p['angle']) * p['length'] * pulse
                ey = p['y'] + math.sin(p['angle']) * p['length'] * pulse
                if rt == 'ray':
                    draw.line([p['x'], p['y'], ex, ey],
                              fill=(cr, cg, cb, int(180*op)),
                              width=max(1, int(p['thickness']*1.5*it)))
                elif rt == 'glow':
                    r = int(40 * pulse * it)
                    draw.ellipse([p['x']-r, p['y']-r, p['x']+r, p['y']+r],
                                 fill=(cr, cg, cb, int(80*op)))
                elif rt == 'beam':
                    wf = max(1, int(p['thickness']*1.5))
                    x1, y1, x2, y2 = p['x']-wf, p['y'], p['x']+wf, p['y']+int(p['length']*pulse)
                    draw.rectangle([x1, y1, x2, y2],
                                   fill=(cr, cg, cb, int(120*op)))

    elif anim_type in ('cloudy', 'sunset', 'sunset_transition', 'dawn'):
        for p in particles:
            if p.get('type') == 'cloud':
                for li, layer in enumerate(p.get('layers', [])):
                    layer_scale = layer['scale']
                    layer_alpha = int(85 * p['opacity'] * fade_alpha * layer['alpha_factor'] * alpha_scale)
                    # Vary color per layer for depth
                    if anim_type in ('sunset', 'sunset_transition'):
                        lr, lg, lb = 200 + li*8, 160 + li*10, 140 + li*12
                    elif anim_type == 'dawn':
                        lr, lg, lb = 210 + li*6, 185 + li*8, 165 + li*10
                    else:
                        lr, lg, lb = 175 + li*6, 190 + li*5, 210 + li*4
                    for i in range(5):
                        ox = (i - 2) * p['size'] * 0.28 * layer_scale
                        oy = li * p['size'] * layer['y_offset'] + layer['y_jitter'][i]
                        sz = p['size'] * 0.42 * layer_scale * layer['bump_variations'][i]
                        draw.ellipse([p['x']+ox-sz, p['y']+oy-sz, p['x']+ox+sz, p['y']+oy+sz],
                                     fill=(lr, lg, lb, layer_alpha))
            elif p.get('type') == 'sun_ray':
                pulse = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(t * p['pulse_speed'] + p['pulse_phase']))
                op = p['opacity'] * pulse * fade_alpha
                cr, cg, cb = p['hue']
                rt = p.get('ray_type')
                ex = p['x'] + math.cos(p['angle']) * p['length'] * pulse
                ey = p['y'] + math.sin(p['angle']) * p['length'] * pulse
                if rt == 'ray':
                    draw.line([p['x'], p['y'], ex, ey],
                              fill=(cr, cg, cb, int(120*op)),
                              width=max(1, int(p['thickness'])))
                elif rt == 'glow':
                    r = int(35 * pulse)
                    draw.ellipse([p['x']-r, p['y']-r, p['x']+r, p['y']+r],
                                 fill=(cr, cg, cb, int(70*op)))
                elif rt == 'atmosphere':
                    rw, rh = int(25*pulse), int(15*pulse)
                    draw.ellipse([p['x']-rw, p['y']-rh, p['x']+rw, p['y']+rh],
                                 fill=(cr, cg, cb, int(50*op)))

    elif anim_type == 'rain':
        for p in particles:
            if 'speed' in p and 'angle' in p:  # Rain drop
                a = int(180 * p['alpha'] * fade_alpha * alpha_scale)
                angle = p.get('angle', 0)
                dx = p['x'] + math.sin(angle) * p['length']
                dy = p['y'] + math.cos(angle) * p['length']
                rr, rg, rb = rain_tint
                rr = int(rr * (1.0 - 0.25 * tint_strength) + 160 * 0.25 * tint_strength)
                rg = int(rg * (1.0 - 0.25 * tint_strength) + 195 * 0.25 * tint_strength)
                rb = int(rb * (1.0 - 0.25 * tint_strength) + 240 * 0.25 * tint_strength)
                draw.line([p['x'], p['y'], dx, dy],
                          fill=(rr, rg, rb, a),
                          width=max(1, int(p['thickness'])))
            elif 'phase' in p:  # Splash ripple
                if p['alpha'] > 0.01:
                    ripple_r = p['size'] * (1 + math.sin(p['phase']) * 0.5)
                    a = int(110 * p['alpha'] * fade_alpha * alpha_scale)
                    rr, rg, rb = rain_tint
                    draw.ellipse([p['x']-ripple_r, p['y']-ripple_r*0.3,
                                  p['x']+ripple_r, p['y']+ripple_r*0.3],
                                 fill=(min(255, rr + 20), min(255, rg + 18), min(255, rb + 12), a))

    elif anim_type == 'snow':
        for p in particles:
            a = int(175 * p['alpha'] * fade_alpha * alpha_scale)
            xo = math.sin(p['oscillation']) * 3
            xp = p['x'] + xo
            sz = p['size']
            # Outer soft glow
            sr, sg, sb = snow_tint
            draw.ellipse([xp-sz*1.6, p['y']-sz*1.6, xp+sz*1.6, p['y']+sz*1.6],
                         fill=(sr, sg, sb, a // 4))
            # Core
            draw.ellipse([xp-sz, p['y']-sz, xp+sz, p['y']+sz],
                         fill=(sr, sg, sb, a))
            # Highlight
            draw.ellipse([xp-sz*0.35-0.5, p['y']-sz*0.35-0.5, xp+sz*0.35-0.5, p['y']+sz*0.35-0.5],
                         fill=(255, 255, 255, min(255, a + 24)))

    elif anim_type == 'fog':
        for p in particles:
            a = int(130 * p['opacity'] * fade_alpha * alpha_scale)
            sz = p['size']
            fr, fg, fb = fog_tint
            draw.ellipse([p['x']-sz, p['y']-sz, p['x']+sz, p['y']+sz],
                         fill=(fr, fg, fb, a))
            draw.ellipse([p['x']-sz*1.7, p['y']-sz*1.7, p['x']+sz*1.7, p['y']+sz*1.7],
                         fill=(min(255, fr + 16), min(255, fg + 16), min(255, fb + 16), a // 2))

    elif anim_type == 'wind':
        for p in particles:
            if p.get('type') == 'wind':
                a = int(95 * p['opacity'] * fade_alpha * alpha_scale)
                ex = p['x'] + p['length'] * 0.7
                ey = p['y'] + p['speed_y'] * 0.5
                draw.line([p['x'], p['y'], ex, ey],
                          fill=(180, 210, 240, a), width=1)
                # Arrow tips
                draw.line([ex-4, ey-2, ex, ey], fill=(180, 210, 240, a), width=1)
                draw.line([ex-4, ey+2, ex, ey], fill=(180, 210, 240, a), width=1)


# ─── Main Loop ───

def get_wallpaper_setter():
    try:
        script_dir = Path(__file__).parent
        spec = __import__('importlib.util').util.spec_from_file_location(
            "backend_manager", script_dir / "wall-it-backend-manager.py")
        if spec:
            module = __import__('importlib.util').util.module_from_spec(spec)
            spec.loader.exec_module(module)
            bm = module.BackendManager()
            return bm, 'backend'
    except Exception:
        pass
    return None, 'swww'


def set_wallpaper(image_path, setter_type, backend_manager):
    """Set the wallpaper image, suppressing matugen during animation."""
    try:
        if setter_type == 'backend' and backend_manager:
            matugen_file = Path.home() / ".cache" / "wall-it" / "matugen_enabled"
            was_enabled = matugen_file.exists() and matugen_file.read_text().strip().lower() == 'true'
            if was_enabled:
                matugen_file.write_text('false_suppressed')
            return backend_manager.set_wallpaper(image_path, None, 'none', 'crop')
        else:
            import subprocess as sp
            sp.run(['swww', 'img', str(image_path), '--transition-type', 'none'],
                   capture_output=True, timeout=2)
            return True
    except Exception as e:
        print(f"⚠️ Wallpaper set error: {e}")
        return False


def get_screen_size():
    try:
        import subprocess as sp
        try:
            import gi
            gi.require_version('Gdk', '4.0')
            from gi.repository import Gdk
            display = Gdk.Display.get_default()
            m = display.get_primary_monitor() or display.get_monitor(0)
            g = m.get_geometry()
            return g.width, g.height
        except:
            pass
        r = sp.run(['xdpyinfo'], capture_output=True, text=True, timeout=2)
        for line in r.stdout.split('\n'):
            if 'dimensions' in line:
                parts = line.split()[1].split('x')
                return int(parts[0]), int(parts[1])
        r = sp.run(['wlr-randr'], capture_output=True, text=True, timeout=2)
        for line in r.stdout.split('\n'):
            if 'x' in line and '@' in line:
                res = line.strip().split()[0]
                parts = res.split('x')[0].split('@')[0], res.split('x')[1].split('@')[0]
                return int(parts[0]), int(parts[1])
    except:
        pass
    return 1920, 1080


def get_current_wallpaper():
    link = Path.home() / ".current-wallpaper"
    if link.exists() and link.is_symlink():
        target = link.resolve()
        if target.exists():
            return target
    wp_dir = Path.home() / "Pictures" / "Wallpapers"
    if wp_dir.exists():
        for f in sorted(wp_dir.iterdir()):
            if f.suffix.lower() in {'.jpg','.jpeg','.png','.webp'}:
                return f
    return None


def main():
    anim_type = resolve_animation_type()
    print(f"🎬 Weather overlay v2: {anim_type}")

    sw, sh = get_screen_size()
    print(f"📺 Screen: {sw}x{sh}")

    wallpaper_path = get_current_wallpaper()
    if wallpaper_path is None:
        print("❌ No wallpaper found")
        return 1
    print(f"🖼️ Base wallpaper: {wallpaper_path.name}")

    cache_dir = Path.home() / ".cache" / "wall-it" / "weather-frames"
    cache_dir.mkdir(parents=True, exist_ok=True)

    wallpaper_metrics = analyze_wallpaper_style(wallpaper_path)
    scene_ctx = build_scene_context(anim_type, wallpaper_metrics)
    particles = init_particles(anim_type, sw, sh, scene_ctx)
    frame_time = 0
    backend_manager, setter_type = get_wallpaper_setter()

    running = True
    def handle_signal(sig, frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    print(f"🎬 Rendering at 30 FPS... (Ctrl+C to stop)")
    frame_count = 0
    target_frame_time = 1.0 / 30.0  # 30 FPS target

    # Fade in
    fade_frames = 10
    fade_in = True

    while running:
        frame_start = _time.time()

        stop_file = Path.home() / ".cache" / "wall-it" / "weather-ipc" / "stop"
        if stop_file.exists():
            print("🎬 Stop file found")
            break

        try:
            base_img = Image.open(wallpaper_path)

            if base_img.size != (sw, sh):
                base_img = base_img.resize((sw, sh), Image.LANCZOS)

            base_img = base_img.convert('RGBA')
            overlay = Image.new('RGBA', (sw, sh), (0, 0, 0, 0))

            # Fade in at start
            if fade_in and frame_count < fade_frames:
                fade_alpha = min(1.0, (frame_count + 1) / fade_frames)
            else:
                fade_in = False
                fade_alpha = 1.0

            render_frame(overlay, anim_type, frame_time, particles, sw, sh, fade_alpha, scene_ctx)

            blur_radius = scene_ctx.get('blur_radius', 0.0)
            if blur_radius > 0.01:
                overlay = overlay.filter(ImageFilter.GaussianBlur(radius=blur_radius))

            result = Image.alpha_composite(base_img, overlay).convert('RGB')

            frame_path = cache_dir / "current.jpg"
            result.save(frame_path, quality=95)

            set_wallpaper(frame_path, setter_type, backend_manager)

            update_particles(particles, anim_type, sw, sh, scene_ctx)
            frame_time += 1
            frame_count += 1

        except Exception as e:
            print(f"⚠️ Frame error: {e}")
            _time.sleep(0.05)
            continue

        # Maintain 30 FPS
        elapsed = _time.time() - frame_start
        sleep_time = max(0.001, target_frame_time - elapsed)
        _time.sleep(sleep_time)

    # Fade out before restoring
    print(f"🎬 Fading out...")
    for fi in range(fade_frames):
        # Check for stop signal during fade-out
        stop_file = Path.home() / ".cache" / "wall-it" / "weather-ipc" / "stop"
        if stop_file.exists():
            print("🎬 Stop file found during fade-out")
            break
        fade_alpha = 1.0 - (fi / fade_frames)
        try:
            base_img = Image.open(wallpaper_path)
            base_img = base_img.resize((sw, sh), Image.LANCZOS).convert('RGBA')
            overlay = Image.new('RGBA', (sw, sh), (0, 0, 0, 0))
            render_frame(overlay, anim_type, frame_time, particles, sw, sh, fade_alpha, scene_ctx)
            result = Image.alpha_composite(base_img, overlay).convert('RGB')
            frame_path = cache_dir / "current.jpg"
            result.save(frame_path, quality=95)
            set_wallpaper(frame_path, setter_type, backend_manager)
            _time.sleep(0.05)
        except:
            pass

    print(f"🎬 Restoring original wallpaper...")
    set_wallpaper(wallpaper_path, setter_type, backend_manager)
    print(f"🎬 Overlay stopped ({frame_count} frames)")

    # Restore matugen
    matugen_file = Path.home() / ".cache" / "wall-it" / "matugen_enabled"
    if matugen_file.exists() and matugen_file.read_text().strip() == 'false_suppressed':
        matugen_file.write_text('true')
        print("🎨 Restored matugen")

    import shutil
    if cache_dir.exists():
        shutil.rmtree(cache_dir, ignore_errors=True)

    stop_file = Path.home() / ".cache" / "wall-it" / "weather-ipc" / "stop"
    stop_file.parent.mkdir(parents=True, exist_ok=True)
    if running:
        stop_file.unlink(missing_ok=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())