#!/usr/bin/env python3
"""Lightweight state-driven Pikachu renderer for the talking-robot LCD."""

import math

from PIL import Image, ImageDraw


MOOD_BACKGROUNDS = {
    "neutral": "#cfeae5",
    "happy": "#afe6cb",
    "excited": "#9bdfee",
    "thinking": "#d2caed",
    "sad": "#bfd3e7",
    "angry": "#edb7a7",
    "sleepy": "#bebdda",
    "surprised": "#f7cf78",
    "love": "#edb8cc",
}
MOOD_HALOS = {
    "neutral": "#e9f7f2",
    "happy": "#e9fff1",
    "excited": "#e5faff",
    "thinking": "#eeeaff",
    "sad": "#e4eef7",
    "angry": "#ffe0d3",
    "sleepy": "#deddf0",
    "surprised": "#fff0bd",
    "love": "#ffe4ee",
}
MOOD_ACCENTS = {
    "neutral": "#5caa9b",
    "happy": "#2ea98d",
    "excited": "#168fb9",
    "thinking": "#6a58a8",
    "sad": "#678eb3",
    "angry": "#bd4c3b",
    "sleepy": "#655d94",
    "surprised": "#bb7618",
    "love": "#d55482",
}
VALID_MOODS = tuple(MOOD_BACKGROUNDS)
INK = "#2b211d"
YELLOW = "#ffd83d"
YELLOW_LIGHT = "#ffe86b"
CHEEK = "#ed4b3f"
BROWN = "#8d552f"


def _heart(draw, x, y, size, fill, outline=None, width=1):
    draw.ellipse((x - size, y - size, x, y), fill=fill, outline=outline, width=width)
    draw.ellipse((x, y - size, x + size, y), fill=fill, outline=outline, width=width)
    draw.polygon(
        ((x - size, y - size // 3), (x + size, y - size // 3), (x, y + size)),
        fill=fill,
        outline=outline,
    )


def _spark(draw, x, y, size, fill, width=4):
    draw.line((x - size, y, x + size, y), fill=fill, width=width)
    draw.line((x, y - size, x, y + size), fill=fill, width=width)
    diagonal = int(size * 0.62)
    draw.line((x - diagonal, y - diagonal, x + diagonal, y + diagonal), fill=fill, width=max(2, width - 1))
    draw.line((x + diagonal, y - diagonal, x - diagonal, y + diagonal), fill=fill, width=max(2, width - 1))


def _z_mark(draw, x, y, size, fill):
    points = ((x, y), (x + size, y), (x, y + size), (x + size, y + size))
    draw.line(points, fill=fill, width=max(3, size // 5), joint="curve")


def _cloud(draw, x, y, fill, outline):
    draw.ellipse((x, y + 8, x + 34, y + 34), fill=fill, outline=outline, width=2)
    draw.ellipse((x + 20, y, x + 60, y + 34), fill=fill, outline=outline, width=2)
    draw.ellipse((x + 46, y + 9, x + 76, y + 34), fill=fill, outline=outline, width=2)
    draw.rounded_rectangle((x + 8, y + 18, x + 69, y + 38), radius=9, fill=fill)


def _background_details(draw, mood, tick, width, height):
    phase = tick / 7.0
    pulse = int((math.sin(phase * 0.7) + 1) * 3)
    halo = MOOD_HALOS[mood]
    accent = MOOD_ACCENTS[mood]
    draw.ellipse((47 - pulse, -8 - pulse, 433 + pulse, 298 + pulse), fill=halo)
    draw.ellipse((57 - pulse, 2 - pulse, 423 + pulse, 288 + pulse), outline=accent, width=3)
    draw.ellipse((142, 274, 338, 312), fill="#b8a68f")

    if mood == "happy":
        colors = ("#ffffff", "#2ba98f", "#f47fa5")
        points = ((48, 48), (423, 47), (62, 138), (418, 151), (93, 226), (388, 224))
        for index, (x, y) in enumerate(points):
            pulse = 2 + int((math.sin(phase + index * 1.3) + 1) * 2)
            _spark(draw, x, y, 7 + pulse, colors[index % len(colors)], width=3)
    elif mood == "excited":
        pulse = int((math.sin(phase * 1.8) + 1) * 3)
        colors = ("#ffffff", "#168fbd", "#f06a9b", "#f3a12f")
        for index, (x, y) in enumerate(((42, 45), (438, 50), (52, 145), (428, 158), (82, 238), (399, 232))):
            _spark(draw, x, y, 10 + pulse + index % 3, colors[index % len(colors)], width=4)
        for index, y in enumerate((84, 117, 196)):
            length = 23 + (index % 2) * 8
            draw.line((18, y, 18 + length, y - 8), fill="#258eb3", width=4)
            draw.line((462, y, 462 - length, y - 8), fill="#e36a8f", width=4)
    elif mood == "thinking":
        orbit = ((54, 64, 9), (414, 42, 7), (428, 142, 11), (65, 190, 6))
        colors = ("#6754a6", "#d88b35", "#478a9b", "#cf6e9f")
        for index, (x, y, radius) in enumerate(orbit):
            offset_x = int(math.sin(phase + index * 1.7) * 7)
            offset_y = int(math.cos(phase * 0.8 + index) * 6)
            draw.ellipse(
                (x - radius + offset_x, y - radius + offset_y, x + radius + offset_x, y + radius + offset_y),
                fill=colors[index],
                outline="#ffffff",
                width=2,
            )
    elif mood == "sad":
        _cloud(draw, 18, 24, "#dce9f3", "#718da9")
        _cloud(draw, 385, 39, "#dce9f3", "#718da9")
        offset = tick % 22
        for x, y in ((42, 75), (430, 92), (65, 165), (410, 184)):
            rain_y = (y + offset * 4) % (height - 60)
            draw.line((x, rain_y, x - 6, rain_y + 14), fill="#6f96bb", width=3)
    elif mood == "angry":
        for index, (x, y) in enumerate(((44, 62), (436, 68), (54, 170), (425, 184))):
            size = 11 + index % 2 * 4
            draw.line((x - size, y - 8, x + size, y + 8), fill=accent, width=5)
            draw.line((x - size, y + 8, x + size, y - 8), fill=accent, width=5)
        draw.line((16, 116, 53, 108, 29, 92), fill="#dc745b", width=5, joint="curve")
        draw.line((464, 116, 427, 108, 451, 92), fill="#dc745b", width=5, joint="curve")
    elif mood == "sleepy":
        draw.arc((18, 20, 78, 80), 65, 295, fill="#fff3bd", width=9)
        for x, y in ((408, 35), (435, 102), (52, 144)):
            _spark(draw, x, y, 5, "#ffffff", width=2)
        float_cycle = 56
        z_colors = ("#8179aa", "#71699d", "#625a91")
        for index, offset in enumerate((0, 14, 28, 42)):
            progress = ((tick + offset) % float_cycle) / float_cycle
            x = 398 + int(progress * 31) + int(math.sin((tick + offset) / 5.0) * 4)
            y = 164 - int(progress * 126)
            size = 9 + int(progress * 10)
            _z_mark(draw, x, y, size, z_colors[min(2, int(progress * 3))])
    elif mood == "surprised":
        ray_color = "#b87618"
        pulse = int((math.sin(phase * 2.2) + 1) * 4)
        rays = (
            (40, 45, 18, 20),
            (440, 45, -18, 20),
            (27, 120, 25, 0),
            (453, 120, -25, 0),
            (48, 202, 20, -15),
            (432, 202, -20, -15),
        )
        for x, y, dx, dy in rays:
            draw.line((x, y, x + dx, y + dy), fill=ray_color, width=5)
            draw.ellipse((x - 3 - pulse // 3, y - 3, x + 3 + pulse // 3, y + 3), fill="#fff7cb")
        draw.arc((23, 82, 69, 166), 255, 105, fill="#d59428", width=4)
        draw.arc((411, 82, 457, 166), 75, 285, fill="#d59428", width=4)
    elif mood == "love":
        bob = int(math.sin(phase) * 4)
        for x, y, size in ((50, 54, 12), (428, 48, 14), (62, 164, 9), (414, 169, 10)):
            _heart(draw, x, y + bob, size, "#dd668f")
        draw.arc((20, 88, 80, 154), 210, 500, fill="#ffffff", width=3)
        draw.arc((400, 88, 460, 154), 40, 330, fill="#ffffff", width=3)
    else:
        for index, (x, y) in enumerate(((42, 42), (438, 48), (54, 150), (426, 172), (82, 230), (398, 228))):
            radius = 4 + (index + tick // 8) % 3
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=accent)


def _draw_tail(draw, mood, tick, bob, talking):
    tail_fill = "#edbf2f" if mood != "angry" else "#e9a62d"
    wag_size = 16 if mood == "excited" else 10 if talking else 5
    wag_speed = 1.8 if mood == "excited" else 2.2 if talking else 5.5
    wag = int(math.sin(tick / wag_speed) * wag_size)
    points = (
        (350, 205 + bob),
        (432 + wag, 147 + bob),
        (405 + wag, 206 + bob),
        (455 + wag, 205 + bob),
        (371, 291 + bob),
        (398, 232 + bob),
        (350, 250 + bob),
    )
    draw.polygon(
        points,
        fill=tail_fill,
        outline=INK,
    )
    draw.line(points[:4], fill=INK, width=5, joint="curve")
    draw.line((391 + wag, 217 + bob, 417 + wag, 193 + bob), fill="#ffe45c", width=4)
    draw.polygon(
        ((350, 224 + bob), (374, 237 + bob), (363, 266 + bob), (350, 251 + bob)),
        fill=BROWN,
        outline=INK,
    )


def _draw_ears(draw, mood, tick, bob, listening):
    twitch_amount = 10 if mood == "excited" else 6 if mood == "surprised" else 7 if listening else 3
    twitch_speed = 1.9 if mood == "excited" else 2.3 if listening else 6.5
    twitch = int(math.sin(tick / twitch_speed) * twitch_amount)
    if mood == "sleepy":
        left = (
            (164, 99 + bob),
            (70 + twitch, 12 + bob),
            (150 + twitch // 2, 52 + bob),
            (205, 79 + bob),
        )
        right = (
            (316, 99 + bob),
            (410 - twitch, 12 + bob),
            (330 - twitch // 2, 52 + bob),
            (275, 79 + bob),
        )
        left_tip = (
            (70 + twitch, 12 + bob),
            (91 + twitch, 24 + bob),
            (113 + twitch // 2, 30 + bob),
        )
        right_tip = (
            (410 - twitch, 12 + bob),
            (389 - twitch, 24 + bob),
            (367 - twitch // 2, 30 + bob),
        )
    elif mood == "happy":
        listen_lift = 7 if listening else 0
        left = (
            (160, 103 + bob),
            (99 + twitch, 14 + bob - listen_lift),
            (158 + twitch // 2, 49 + bob),
            (205, 79 + bob),
        )
        right = (
            (320, 103 + bob),
            (381 - twitch, 14 + bob - listen_lift),
            (322 - twitch // 2, 49 + bob),
            (275, 79 + bob),
        )
        left_tip = (
            (99 + twitch, 14 + bob - listen_lift),
            (117 + twitch, 29 + bob),
            (139 + twitch // 2, 35 + bob),
        )
        right_tip = (
            (381 - twitch, 14 + bob - listen_lift),
            (363 - twitch, 29 + bob),
            (341 - twitch // 2, 35 + bob),
        )
    else:
        listen_lift = 7 if listening else 0
        left_top_x, ear_top_y = {
            "neutral": (99, 14),
            "excited": (90, 18),
            "thinking": (104, 14),
            "sad": (82, 14),
            "angry": (108, 14),
            "surprised": (74, 16),
            "love": (94, 14),
        }.get(mood, (99, 14))
        right_top_x = 480 - left_top_x
        left = (
            (160, 103 + bob),
            (left_top_x + twitch, ear_top_y + bob - listen_lift),
            (left_top_x + 59 + twitch // 2, ear_top_y + 48 + bob),
            (205, 79 + bob),
        )
        right = (
            (320, 103 + bob),
            (right_top_x - twitch, ear_top_y + bob - listen_lift),
            (right_top_x - 59 - twitch // 2, ear_top_y + 48 + bob),
            (275, 79 + bob),
        )
        left_tip = (
            (left_top_x + twitch, ear_top_y + bob - listen_lift),
            (left_top_x + 18 + twitch, ear_top_y + 28 + bob),
            (left_top_x + 40 + twitch // 2, ear_top_y + 34 + bob),
        )
        right_tip = (
            (right_top_x - twitch, ear_top_y + bob - listen_lift),
            (right_top_x - 18 - twitch, ear_top_y + 28 + bob),
            (right_top_x - 40 - twitch // 2, ear_top_y + 34 + bob),
        )
    draw.polygon(left, fill=YELLOW, outline=INK)
    draw.line(left + (left[0],), fill=INK, width=6, joint="curve")
    draw.polygon(right, fill=YELLOW, outline=INK)
    draw.line(right + (right[0],), fill=INK, width=6, joint="curve")
    draw.polygon(left_tip, fill=INK)
    draw.polygon(right_tip, fill=INK)


def _normal_eye(draw, x, y, look=0, wide=False):
    radius_x = 28 if wide else 24
    radius_y = 34 if wide else 30
    draw.ellipse((x - radius_x, y - radius_y, x + radius_x, y + radius_y), fill=INK)
    draw.ellipse((x - 14 + look, y + 3, x + 15 + look, y + 25), fill="#6f493b")
    draw.ellipse((x - 10 + look, y - 18, x + 5 + look, y - 3), fill="#ffffff")
    draw.ellipse((x - 5 + look, y - 13, x + 1 + look, y - 7), fill="#dff8ff")
    draw.ellipse((x + 8 + look, y + 10, x + 14 + look, y + 16), fill="#8b5e45")


def _surprised_eye(draw, x, y):
    draw.ellipse((x - 34, y - 43, x + 34, y + 43), fill="#fffdf2", outline=INK, width=6)
    draw.ellipse((x - 15, y - 21, x + 15, y + 21), fill=INK)
    draw.ellipse((x - 8, y - 15, x + 2, y - 5), fill="#ffffff")
    draw.ellipse((x + 5, y + 8, x + 10, y + 13), fill="#9b6a4d")


def _draw_eyes(draw, mood, tick, bob, listening):
    left_x, right_x, y = 170, 310, 126 + bob
    blink = tick > 8 and tick % 73 in {55, 56}
    if blink and mood not in {"angry", "sleepy", "love", "happy", "excited", "surprised"}:
        curve = 4
        draw.arc((136, y - curve, 204, y + 28), 195, 345, fill=INK, width=8)
        draw.arc((276, y - curve, 344, y + 28), 195, 345, fill=INK, width=8)
        return
    listening_look = int(math.sin(tick / 7.0) * 6) if listening else 0
    if mood == "happy":
        eye_lift = int((math.sin(tick / 5.0) + 1) * 2)
        draw.arc((137, y - 24 - eye_lift, 203, y + 23), 195, 345, fill=INK, width=9)
        draw.arc((277, y - 24 - eye_lift, 343, y + 23), 195, 345, fill=INK, width=9)
    elif mood == "excited":
        _normal_eye(draw, left_x, y, wide=True)
        _normal_eye(draw, right_x, y, wide=True)
        eye_pulse = 14 + int((math.sin(tick / 2.0) + 1) * 2)
        _spark(draw, left_x, y, eye_pulse, "#fff6a0", width=5)
        _spark(draw, right_x, y, eye_pulse, "#fff6a0", width=5)
        _spark(draw, left_x, y, max(7, eye_pulse - 6), "#ffffff", width=3)
        _spark(draw, right_x, y, max(7, eye_pulse - 6), "#ffffff", width=3)
        draw.arc((130, y - 42, 210, y + 42), 110, 250, fill="#24a6ca", width=4)
        draw.arc((270, y - 42, 350, y + 42), 290, 70, fill="#e7719d", width=4)
    elif mood == "thinking":
        look = int(math.sin(tick / 10.0) * 5) - 7
        _normal_eye(draw, left_x, y, look=look)
        _normal_eye(draw, right_x, y, look=look)
        draw.line((140, 83 + bob, 195, 77 + bob), fill=INK, width=6)
        draw.line((282, 80 + bob, 336, 88 + bob), fill=INK, width=5)
    elif mood == "sad":
        _normal_eye(draw, left_x, y)
        _normal_eye(draw, right_x, y)
        draw.line((139, 88 + bob, 197, 76 + bob), fill=INK, width=6)
        draw.line((283, 76 + bob, 341, 88 + bob), fill=INK, width=6)
        draw.polygon(((145, 151 + bob), (135, 174 + bob), (154, 174 + bob)), fill="#61bdea")
        draw.polygon(((335, 151 + bob), (326, 174 + bob), (345, 174 + bob)), fill="#61bdea")
    elif mood == "angry":
        draw.polygon(((137, 103 + bob), (201, 115 + bob), (194, 151 + bob), (143, 143 + bob)), fill=INK)
        draw.polygon(((343, 103 + bob), (279, 115 + bob), (286, 151 + bob), (337, 143 + bob)), fill=INK)
        draw.ellipse((158, 114 + bob, 171, 127 + bob), fill="#ffffff")
        draw.ellipse((309, 114 + bob, 322, 127 + bob), fill="#ffffff")
        draw.line((132, 80 + bob, 202, 105 + bob), fill=INK, width=8)
        draw.line((278, 105 + bob, 348, 80 + bob), fill=INK, width=8)
    elif mood == "sleepy":
        draw.arc((134, 103 + bob, 202, 151 + bob), 15, 165, fill=INK, width=8)
        draw.arc((278, 103 + bob, 346, 151 + bob), 15, 165, fill=INK, width=8)
    elif mood == "surprised":
        _surprised_eye(draw, left_x, y)
        _surprised_eye(draw, right_x, y)
        brow_lift = int((math.sin(tick / 3.0) + 1) * 2)
        draw.arc((127, 58 + bob - brow_lift, 211, 91 + bob - brow_lift), 190, 350, fill=INK, width=6)
        draw.arc((269, 58 + bob - brow_lift, 353, 91 + bob - brow_lift), 190, 350, fill=INK, width=6)
    elif mood == "love":
        _heart(draw, left_x, y, 24, "#cf3e6e", outline=INK, width=2)
        _heart(draw, right_x, y, 24, "#cf3e6e", outline=INK, width=2)
    else:
        _normal_eye(draw, left_x, y, look=listening_look)
        _normal_eye(draw, right_x, y, look=listening_look)


def _draw_mouth(draw, mood, tick, bob, talking):
    y = 174 + bob
    draw.polygon(((236, 155 + bob), (244, 155 + bob), (240, 162 + bob)), fill=INK)
    if talking and mood != "sleepy":
        pulse = int((math.sin(tick * 1.35) + 1) * 9)
        if mood == "excited":
            left, right, open_height = 196, 284, 52 + pulse
        elif mood == "happy":
            left, right, open_height = 201, 279, 38 + pulse
        elif mood == "surprised":
            left, right, open_height = 211, 269, 55 + pulse // 2
        else:
            left, right, open_height = 213, 267, 30 + pulse
        draw.ellipse((left, y + 1, right, y + open_height), fill="#542823", outline=INK, width=5)
        tongue_top = y + max(18, open_height - 11)
        tongue_width = 44 if mood == "excited" else 36
        draw.arc(
            (240 - tongue_width // 2, tongue_top - 6, 240 + tongue_width // 2, tongue_top + 14),
            180,
            360,
            fill="#ef7487",
            width=8,
        )
        return
    if mood == "happy":
        draw.arc((204, y - 13, 240, y + 23), 5, 155, fill=INK, width=6)
        draw.arc((240, y - 13, 276, y + 23), 25, 175, fill=INK, width=6)
        draw.ellipse((215, y + 8, 265, y + 45), fill="#68322e", outline=INK, width=4)
        draw.arc((224, y + 27, 256, y + 47), 180, 360, fill="#ef7889", width=8)
    elif mood == "love":
        draw.arc((193, y - 14, 240, y + 35), 5, 155, fill=INK, width=6)
        draw.arc((240, y - 14, 287, y + 35), 25, 175, fill=INK, width=6)
        draw.arc((211, y + 1, 269, y + 54), 0, 180, fill="#ce4c5d", width=5)
    elif mood == "excited":
        mouth_bounce = int((math.sin(tick / 2.0) + 1) * 3)
        draw.ellipse((196, y - 10, 284, y + 64 + mouth_bounce), fill="#542823", outline=INK, width=5)
        draw.arc((210, y + 35, 270, y + 68 + mouth_bounce), 180, 360, fill="#ef7487", width=12)
    elif mood == "thinking":
        draw.line((218, y + 20, 257, y + 16, 268, y + 22), fill=INK, width=6, joint="curve")
    elif mood == "sad":
        draw.arc((207, y + 12, 273, y + 58), 195, 345, fill=INK, width=7)
    elif mood == "angry":
        draw.line((211, y + 28, 269, y + 22), fill=INK, width=7)
    elif mood == "sleepy":
        draw.ellipse((229, y + 12, 251, y + 29), fill="#684139", outline=INK, width=3)
    elif mood == "surprised":
        gasp = int((math.sin(tick / 2.8) + 1) * 3)
        draw.ellipse((210, y - 3, 270, y + 61 + gasp), fill="#542823", outline=INK, width=6)
        draw.ellipse((226, y + 38 + gasp, 254, y + 54 + gasp), fill="#d96979")
    else:
        draw.arc((211, y - 1, 240, y + 31), 5, 155, fill=INK, width=5)
        draw.arc((240, y - 1, 269, y + 31), 25, 175, fill=INK, width=5)


def _draw_raised_paws(draw, mood, tick, bob):
    if mood == "excited":
        wave = int(math.sin(tick / 1.8) * 7)
        paws = (
            (72, 202 + bob + wave, 140, 282 + bob + wave),
            (340, 202 + bob - wave, 408, 282 + bob - wave),
        )
    elif mood == "surprised":
        tremble = int(math.sin(tick * 1.7) * 2)
        paws = (
            (91 + tremble, 207 + bob, 153 + tremble, 278 + bob),
            (327 - tremble, 207 + bob, 389 - tremble, 278 + bob),
        )
    else:
        return

    for left, top, right, bottom in paws:
        draw.ellipse((left, top, right, bottom), fill=YELLOW, outline=INK, width=5)
        center_x = (left + right) // 2
        draw.arc((center_x - 22, top + 13, center_x + 2, top + 42), 205, 330, fill="#b48727", width=3)
        draw.arc((center_x - 2, top + 13, center_x + 22, top + 42), 210, 335, fill="#b48727", width=3)


def render_pikachu(
    size=(480, 320),
    expression="neutral",
    tick=0,
    *,
    talking=False,
    listening=False,
):
    """Render one animated Pikachu mood frame at the requested logical size."""
    mood = str(expression or "neutral").strip().lower()
    if mood not in VALID_MOODS:
        mood = "neutral"

    width, height = 480, 320
    image = Image.new("RGB", (width, height), MOOD_BACKGROUNDS[mood])
    draw = ImageDraw.Draw(image)
    _background_details(draw, mood, tick, width, height)

    bob = int(round(math.sin(tick / 8.0) * 1.5))
    if mood == "excited":
        bob = -3 - int(abs(math.sin(tick / 2.5)) * 8)
    elif mood == "happy":
        bob = -1 - int((math.sin(tick / 5.0) + 1) * 1.5)
    elif mood == "surprised":
        bob = int(math.sin(tick * 1.7) * 2)
    elif mood == "sleepy":
        bob = int((math.sin(tick / 8.0) + 1) * 2)
    elif talking:
        bob += int(round(math.sin(tick / 2.7) * 2))

    _draw_tail(draw, mood, tick, bob, talking)
    body_breathe = int((math.sin(tick / 9.0) + 1) * 2)
    draw.ellipse(
        (137 - body_breathe, 218 + bob, 343 + body_breathe, 357 + bob),
        fill="#f4c72f",
        outline=INK,
        width=6,
    )
    draw.ellipse((166, 252 + bob, 314, 355 + bob), fill=YELLOW_LIGHT)
    draw.ellipse((100, 278 + bob, 187, 330 + bob), fill=YELLOW, outline=INK, width=5)
    draw.ellipse((293, 278 + bob, 380, 330 + bob), fill=YELLOW, outline=INK, width=5)
    for x in (120, 146, 314, 340):
        draw.arc((x, 291 + bob, x + 24, 319 + bob), 205, 325, fill="#a87528", width=3)
    _draw_ears(draw, mood, tick, bob, listening)
    draw.ellipse((72, 38 + bob, 408, 277 + bob), fill=YELLOW, outline=INK, width=7)

    left_cheek = (96, 159 + bob, 151, 207 + bob)
    right_cheek = (329, 159 + bob, 384, 207 + bob)
    if mood == "excited":
        cheek_pulse = 2 + (2 if tick % 6 < 3 else 0)
    elif mood == "love":
        cheek_pulse = 2 + (1 if tick % 10 < 5 else 0)
    elif mood == "surprised":
        cheek_pulse = -2
    elif mood == "happy":
        cheek_pulse = 1 if tick % 10 < 5 else 0
    else:
        cheek_pulse = 2 if talking and tick % 6 < 3 else 0
    draw.ellipse(
        (
            left_cheek[0] - cheek_pulse,
            left_cheek[1] - cheek_pulse,
            left_cheek[2] + cheek_pulse,
            left_cheek[3] + cheek_pulse,
        ),
        fill=CHEEK,
        outline=INK,
        width=4,
    )
    draw.ellipse(
        (
            right_cheek[0] - cheek_pulse,
            right_cheek[1] - cheek_pulse,
            right_cheek[2] + cheek_pulse,
            right_cheek[3] + cheek_pulse,
        ),
        fill=CHEEK,
        outline=INK,
        width=4,
    )
    if mood == "excited":
        spark_shift = int(math.sin(tick / 2.0) * 7)
    else:
        spark_shift = int(math.sin(tick / 3.0) * 3) if talking else 0
    if mood == "excited" or talking:
        draw.line(
            (96, 180 + bob, 72 - spark_shift, 168 + bob, 88, 151 + bob),
            fill="#d69713",
            width=4,
        )
        draw.line(
            (384, 180 + bob, 408 + spark_shift, 168 + bob, 392, 151 + bob),
            fill="#d69713",
            width=4,
        )

    _draw_eyes(draw, mood, tick, bob, listening)
    _draw_mouth(draw, mood, tick, bob, talking)
    _draw_raised_paws(draw, mood, tick, bob)

    if size != image.size:
        image = image.resize(size, Image.Resampling.LANCZOS)
    return image


if __name__ == "__main__":
    cell_width, cell_height = 240, 160
    sheet = Image.new("RGB", (cell_width * 3, cell_height * 3), "white")
    for index, mood in enumerate(VALID_MOODS):
        frame = render_pikachu((cell_width, cell_height), mood, tick=9)
        sheet.paste(frame, ((index % 3) * cell_width, (index // 3) * cell_height))
    sheet.save("/tmp/19k_pikachu_moods.png")
