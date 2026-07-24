#!/usr/bin/env python3
"""Lightweight state-driven Pikachu renderer for the talking-robot LCD."""

import math

from PIL import Image, ImageDraw


MOOD_BACKGROUNDS = {
    "neutral": "#ccebe5",
    "happy": "#aee8cf",
    "excited": "#8edbec",
    "thinking": "#d4ceec",
    "sad": "#b9cfe3",
    "angry": "#efae99",
    "sleepy": "#aaa9d0",
    "surprised": "#f8cc6d",
    "love": "#efb5ca",
}
MOOD_HALOS = {
    "neutral": "#ecfaf4",
    "happy": "#fff7bd",
    "excited": "#e7fbff",
    "thinking": "#f3efff",
    "sad": "#dfeaf3",
    "angry": "#ffd8c9",
    "sleepy": "#d8d7ef",
    "surprised": "#fff2b9",
    "love": "#ffe5ed",
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
EAR_POSES = {
    "neutral": ((78, 11), (145, 52), (402, 11), (335, 52)),
    "happy": ((74, 14), (146, 50), (406, 14), (334, 50)),
    "excited": ((54, 18), (136, 54), (426, 18), (344, 54)),
    "thinking": ((76, 11), (145, 54), (434, 35), (356, 59)),
    "sad": ((38, 58), (118, 64), (442, 58), (362, 64)),
    "angry": ((60, 18), (135, 53), (420, 18), (345, 53)),
    "sleepy": ((52, 24), (132, 58), (428, 24), (348, 58)),
    "surprised": ((56, 15), (134, 50), (424, 15), (346, 50)),
    "love": ((72, 13), (142, 51), (408, 13), (338, 51)),
}


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


def _leaf(draw, x, y, size, fill, facing=1):
    draw.ellipse((x - size, y - size // 2, x + size, y + size // 2), fill=fill)
    draw.line((x - size * facing, y + size // 2, x + size * facing, y - size // 2), fill="#ffffff", width=2)


def _flower(draw, x, y, size, petals, center):
    petal_radius = max(3, size // 2)
    for dx, dy in ((-size, 0), (size, 0), (0, -size), (0, size)):
        draw.ellipse(
            (
                x + dx - petal_radius,
                y + dy - petal_radius,
                x + dx + petal_radius,
                y + dy + petal_radius,
            ),
            fill=petals,
        )
    draw.ellipse((x - petal_radius, y - petal_radius, x + petal_radius, y + petal_radius), fill=center)


def _lightbulb(draw, x, y, size, glow):
    draw.ellipse((x - size, y - size, x + size, y + size), fill=glow, outline="#9a6a24", width=3)
    draw.rounded_rectangle(
        (x - size // 2, y + size - 2, x + size // 2, y + size + 12),
        radius=4,
        fill="#6d5a78",
    )
    draw.line((x - size // 2, y + size + 5, x + size // 2, y + size + 5), fill="#f5db78", width=2)
    for angle in range(0, 360, 45):
        radians = math.radians(angle)
        inner = size + 7
        outer = size + 16
        draw.line(
            (
                x + int(math.cos(radians) * inner),
                y + int(math.sin(radians) * inner),
                x + int(math.cos(radians) * outer),
                y + int(math.sin(radians) * outer),
            ),
            fill="#f1af3d",
            width=3,
        )


def _focus_oval(draw, mood, pulse, outline_width=3):
    halo = MOOD_HALOS[mood]
    accent = MOOD_ACCENTS[mood]
    draw.ellipse((43 - pulse, -12 - pulse, 437 + pulse, 302 + pulse), fill=halo)
    draw.ellipse((57 - pulse, 2 - pulse, 423 + pulse, 288 + pulse), outline=accent, width=outline_width)


def _background_details(draw, mood, tick, width, height):
    phase = tick / 7.0
    pulse = int((math.sin(phase * 0.7) + 1) * 3)
    accent = MOOD_ACCENTS[mood]

    if mood == "happy":
        sun_pulse = 4 + int((math.sin(phase * 1.4) + 1) * 2)
        draw.ellipse((-28 - sun_pulse, -31 - sun_pulse, 104 + sun_pulse, 101 + sun_pulse), fill="#ffe375")
        for angle in range(0, 100, 20):
            radians = math.radians(angle)
            draw.line(
                (
                    38 + int(math.cos(radians) * 76),
                    36 + int(math.sin(radians) * 76),
                    38 + int(math.cos(radians) * 99),
                    36 + int(math.sin(radians) * 99),
                ),
                fill="#f6b83d",
                width=5,
            )
        draw.ellipse((0, 249, 260, 372), fill="#65c99d")
        draw.ellipse((196, 254, 510, 380), fill="#4ebda7")
        _focus_oval(draw, mood, pulse, outline_width=4)
        colors = ("#ffffff", "#26a98d", "#f46f9c")
        points = ((51, 91), (426, 42), (57, 159), (421, 144), (95, 236), (394, 226))
        for index, (x, y) in enumerate(points):
            sparkle = 2 + int((math.sin(phase + index * 1.3) + 1) * 2)
            _spark(draw, x, y, 7 + sparkle, colors[index % len(colors)], width=3)
        for index, (x, y) in enumerate(((34, 267), (82, 281), (400, 273), (451, 260))):
            _flower(
                draw,
                x,
                y + int(math.sin(phase + index) * 2),
                5,
                ("#ffffff", "#f883a9")[index % 2],
                "#f5bd38",
            )
    elif mood == "excited":
        center = (240, 145)
        burst_colors = ("#c3f4ef", "#f7dd75", "#f5a4c2", "#d6f6ff")
        edge_points = (
            (0, 0),
            (110, 0),
            (190, 0),
            (286, 0),
            (394, 0),
            (480, 0),
            (480, 88),
            (480, 195),
            (480, 320),
            (360, 320),
            (250, 320),
            (135, 320),
            (0, 320),
            (0, 220),
            (0, 110),
        )
        for index in range(len(edge_points) - 1):
            draw.polygon(
                (center, edge_points[index], edge_points[index + 1]),
                fill=burst_colors[index % len(burst_colors)],
            )
        draw.ellipse((67 - pulse, 3 - pulse, 413 + pulse, 288 + pulse), fill=MOOD_HALOS[mood], outline=accent, width=4)
        action_pulse = int((math.sin(phase * 1.8) + 1) * 3)
        colors = ("#ffffff", "#168fbd", "#f06a9b", "#f3a12f")
        for index, (x, y) in enumerate(((42, 45), (438, 50), (52, 145), (428, 158), (82, 238), (399, 232))):
            _spark(draw, x, y, 10 + action_pulse + index % 3, colors[index % len(colors)], width=4)
        for index, y in enumerate((84, 117, 196)):
            length = 23 + (index % 2) * 8
            draw.line((18, y, 18 + length, y - 8), fill="#258eb3", width=4)
            draw.line((462, y, 462 - length, y - 8), fill="#e36a8f", width=4)
    elif mood == "thinking":
        draw.arc((10, -30, 470, 292), 186, 357, fill="#9b8cc9", width=3)
        draw.arc((27, -8, 453, 300), 8, 178, fill="#6ba3ae", width=3)
        _focus_oval(draw, mood, pulse)
        bulb_bob = int(math.sin(phase * 1.5) * 4)
        _lightbulb(draw, 416, 49 + bulb_bob, 18, "#ffe37c")
        orbit = ((54, 64, 9), (410, 130, 7), (428, 191, 11), (65, 190, 6))
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
        for x, y, radius in ((365, 83, 5), (383, 70, 8)):
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="#fff7c2", outline="#9a79a2", width=2)
    elif mood == "sad":
        draw.rectangle((0, 0, width, 86), fill="#8eaac4")
        draw.ellipse((21, 170, 459, 344), fill="#dce8f1", outline="#678eb3", width=3)
        draw.ellipse((125, 272, 355, 315), fill="#8db7cc")
        _cloud(draw, 10, 20, "#d8e4ed", "#647f9a")
        _cloud(draw, 74, 4, "#cedce8", "#647f9a")
        _cloud(draw, 369, 28, "#d8e4ed", "#647f9a")
        _cloud(draw, 411, 5, "#cedce8", "#647f9a")
        offset = tick % 22
        for x, y in ((30, 75), (89, 102), (429, 92), (57, 164), (410, 181), (451, 142)):
            rain_y = 67 + ((y + offset * 4) % (height - 105))
            draw.line((x, rain_y, x - 6, rain_y + 14), fill="#6f96bb", width=3)
    elif mood == "angry":
        center = (240, 150)
        burst = (
            ((0, 0), (104, 0)),
            ((180, 0), (248, 0)),
            ((344, 0), (480, 0)),
            ((480, 75), (480, 160)),
            ((480, 240), (480, 320)),
            ((324, 320), (232, 320)),
            ((135, 320), (0, 320)),
            ((0, 210), (0, 111)),
        )
        for index, edge in enumerate(burst):
            draw.polygon((center, edge[0], edge[1]), fill=("#f9d1b5", "#dc7666")[index % 2])
        draw.ellipse(
            (58 - pulse, 2 - pulse, 422 + pulse, 288 + pulse),
            fill=MOOD_HALOS[mood],
            outline="#bd4c3b",
            width=4,
        )
        for index, (x, y) in enumerate(((44, 62), (436, 68), (54, 170), (425, 184))):
            size = 11 + index % 2 * 4
            draw.line((x - size, y - 8, x + size, y + 8), fill=accent, width=5)
            draw.line((x - size, y + 8, x + size, y - 8), fill=accent, width=5)
        draw.line((16, 116, 53, 108, 29, 92), fill="#dc745b", width=5, joint="curve")
        draw.line((464, 116, 427, 108, 451, 92), fill="#dc745b", width=5, joint="curve")
    elif mood == "sleepy":
        draw.rectangle((0, 0, width, 100), fill="#7778aa")
        draw.ellipse((-40, 220, 274, 380), fill="#888fbd")
        draw.ellipse((180, 205, 540, 382), fill="#737fad")
        draw.ellipse(
            (58 - pulse, 2 - pulse, 422 + pulse, 292 + pulse),
            fill=MOOD_HALOS[mood],
            outline="#655d94",
            width=3,
        )
        draw.ellipse((8, 8, 83, 83), fill="#fff0a8")
        draw.ellipse((30, -1, 92, 69), fill="#7778aa")
        for index, (x, y) in enumerate(((405, 28), (446, 91), (44, 140), (89, 52), (386, 132))):
            star_size = 4 + int((math.sin(phase + index) + 1) * 2)
            _spark(draw, x, y, star_size, ("#ffffff", "#f8dfa0")[index % 2], width=2)
        float_cycle = 56
        z_colors = ("#8179aa", "#655d94", "#504879")
        for index, offset in enumerate((0, 14, 28, 42)):
            progress = ((tick + offset) % float_cycle) / float_cycle
            x = 398 + int(progress * 31) + int(math.sin((tick + offset) / 5.0) * 4)
            y = 164 - int(progress * 126)
            size = 9 + int(progress * 10)
            _z_mark(draw, x, y, size, z_colors[min(2, int(progress * 3))])
    elif mood == "surprised":
        ring_pulse = int((math.sin(phase * 2.2) + 1) * 5)
        draw.ellipse(
            (20 - ring_pulse, -54 - ring_pulse, 460 + ring_pulse, 338 + ring_pulse),
            outline="#fff0b0",
            width=15,
        )
        draw.ellipse(
            (46 + ring_pulse, -12 + ring_pulse, 434 - ring_pulse, 306 - ring_pulse),
            fill=MOOD_HALOS[mood],
            outline="#cf8a27",
            width=4,
        )
        ray_color = "#b87618"
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
            draw.ellipse((x - 3 - ring_pulse // 3, y - 3, x + 3 + ring_pulse // 3, y + 3), fill="#fff7cb")
        draw.arc((23, 82, 69, 166), 255, 105, fill="#d59428", width=4)
        draw.arc((411, 82, 457, 166), 75, 285, fill="#d59428", width=4)
        for x in (34, 446):
            draw.line((x, 225, x, 251), fill="#a95f21", width=5)
            draw.ellipse((x - 3, 258, x + 3, 264), fill="#a95f21")
    elif mood == "love":
        draw.arc((-50, 34, 530, 356), 190, 350, fill="#ffffff", width=10)
        draw.arc((-31, 48, 511, 339), 10, 170, fill="#d95c8b", width=4)
        _focus_oval(draw, mood, pulse)
        bob = int(math.sin(phase) * 4)
        for x, y, size in ((50, 54, 12), (428, 48, 14), (62, 164, 9), (414, 169, 10)):
            _heart(draw, x, y + bob, size, "#dd668f")
        draw.arc((20, 88, 80, 154), 210, 500, fill="#ffffff", width=3)
        draw.arc((400, 88, 460, 154), 40, 330, fill="#ffffff", width=3)
    else:
        draw.ellipse((-30, 253, 280, 372), fill="#91d2ad")
        draw.ellipse((198, 247, 520, 376), fill="#72c9b3")
        _focus_oval(draw, mood, pulse)
        breeze = int(math.sin(phase) * 5)
        draw.arc((3 + breeze, 65, 126 + breeze, 132), 202, 342, fill="#ffffff", width=3)
        draw.arc((356 - breeze, 86, 477 - breeze, 158), 198, 337, fill="#ffffff", width=3)
        for index, (x, y, facing) in enumerate(((34, 53, 1), (439, 60, -1), (55, 194, -1), (420, 208, 1))):
            _leaf(draw, x + int(math.sin(phase + index) * 5), y, 7, ("#4ba78e", "#e6aa51")[index % 2], facing)
        for index, (x, y) in enumerate(((42, 42), (438, 48), (54, 150), (426, 172), (82, 230), (398, 228))):
            radius = 4 + (index + tick // 8) % 3
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=accent)

    shadow_color = {
        "happy": "#79a977",
        "excited": "#7aa5a6",
        "thinking": "#9c8fa8",
        "sad": "#7896a6",
        "angry": "#a36d5f",
        "sleepy": "#656987",
        "surprised": "#ba8c49",
        "love": "#aa7283",
    }.get(mood, "#799c8c")
    draw.ellipse((142, 274, 338, 312), fill=shadow_color)


def _draw_tail(draw, mood, tick, bob, talking):
    tail_fill = "#edbf2f" if mood != "angry" else "#e9a62d"
    if mood == "excited":
        wag_size, wag_speed = 16, 1.8
    elif mood in {"sleepy", "sad"}:
        wag_size, wag_speed = 2, 10.0
    elif mood == "angry":
        wag_size, wag_speed = 3, 7.0
    elif talking:
        wag_size, wag_speed = 10, 2.2
    elif mood in {"happy", "love"}:
        wag_size, wag_speed = 8, 4.2
    else:
        wag_size, wag_speed = 5, 5.5
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


def _interpolate_point(start, end, fraction):
    return (
        int(round(start[0] + (end[0] - start[0]) * fraction)),
        int(round(start[1] + (end[1] - start[1]) * fraction)),
    )


def _draw_single_ear(draw, outer_base, tip, inner_turn, inner_base):
    shape = (outer_base, tip, inner_turn, inner_base)
    draw.polygon(shape, fill=YELLOW)
    draw.line(shape + (outer_base,), fill=INK, width=6, joint="curve")

    outer_cap = _interpolate_point(tip, outer_base, 0.34)
    inner_cap = _interpolate_point(tip, inner_turn, 0.46)
    draw.polygon((tip, outer_cap, inner_cap), fill=INK)
    draw.line((outer_cap, inner_cap), fill=INK, width=3)


def _draw_ears(draw, mood, tick, bob, listening):
    # Each pose uses the same broad Pikachu silhouette while changing attitude.
    left_tip, left_turn, right_tip, right_turn = EAR_POSES[mood]

    if mood == "excited":
        twitch_amount, twitch_speed = 10, 1.9
    elif mood == "surprised":
        twitch_amount, twitch_speed = 7, 2.4
    elif listening:
        twitch_amount, twitch_speed = 7, 2.3
    elif mood in {"sad", "sleepy"}:
        twitch_amount, twitch_speed = 2, 8.0
    else:
        twitch_amount, twitch_speed = 4, 6.5

    twitch = int(math.sin(tick / twitch_speed) * twitch_amount)
    listen_lift = 7 if listening and mood not in {"sad", "sleepy"} else 0
    droop = int((math.sin(tick / 11.0) + 1) * 2) if mood == "sad" else 0

    left_tip = (left_tip[0] + twitch, left_tip[1] + bob - listen_lift + droop)
    left_turn = (left_turn[0] + twitch // 2, left_turn[1] + bob + droop // 2)
    right_tip = (right_tip[0] - twitch, right_tip[1] + bob - listen_lift + droop)
    right_turn = (right_turn[0] - twitch // 2, right_turn[1] + bob + droop // 2)

    base_spread = 4 if mood in {"excited", "surprised", "angry"} else 0
    left_outer = (140 - base_spread, 105 + bob)
    left_inner = (214, 84 + bob)
    right_outer = (340 + base_spread, 105 + bob)
    right_inner = (266, 84 + bob)

    _draw_single_ear(draw, left_outer, left_tip, left_turn, left_inner)
    _draw_single_ear(draw, right_outer, right_tip, right_turn, right_inner)


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


def _draw_expression_accents(draw, mood, tick, bob, talking):
    if mood == "happy":
        joy_lift = int((math.sin(tick / 5.0) + 1) * 2)
        draw.arc((107, 132 + bob - joy_lift, 140, 165 + bob), 205, 315, fill="#c88922", width=4)
        draw.arc((340, 132 + bob - joy_lift, 373, 165 + bob), 225, 335, fill="#c88922", width=4)
        draw.ellipse((112, 168 + bob, 125, 176 + bob), fill="#ff9a83")
        draw.ellipse((355, 168 + bob, 368, 176 + bob), fill="#ff9a83")
    elif mood == "thinking":
        tap = int(math.sin(tick / 3.5) * 3)
        draw.ellipse((288 + tap, 190 + bob, 348 + tap, 257 + bob), fill=YELLOW, outline=INK, width=5)
        draw.arc((301 + tap, 202 + bob, 326 + tap, 231 + bob), 210, 335, fill="#a87528", width=3)
        draw.arc((316 + tap, 198 + bob, 341 + tap, 228 + bob), 210, 335, fill="#a87528", width=3)
    elif mood == "sad":
        draw.arc((113, 203 + bob, 156, 229 + bob), 20, 160, fill="#bd7d2f", width=3)
        draw.arc((324, 203 + bob, 367, 229 + bob), 20, 160, fill="#bd7d2f", width=3)
    elif mood == "angry":
        stress = 2 if tick % 8 < 4 else 0
        x, y = 363 + stress, 75 + bob
        draw.line((x, y + 14, x + 15, y, x + 15, y + 12, x + 28, y - 2), fill="#b33d31", width=4, joint="curve")
    elif mood == "sleepy" and not talking:
        bubble = 8 + int((math.sin(tick / 5.0) + 1) * 3)
        draw.ellipse(
            (255, 182 + bob - bubble, 255 + bubble * 2, 182 + bob + bubble),
            fill="#dff6f5",
            outline="#718aaa",
            width=3,
        )
        draw.ellipse((254, 183 + bob, 261, 190 + bob), fill="#dff6f5")
    elif mood == "surprised":
        shake = int(math.sin(tick * 1.7) * 3)
        draw.line((92 + shake, 211 + bob, 76 + shake, 224 + bob), fill="#c78324", width=4)
        draw.line((388 - shake, 211 + bob, 404 - shake, 224 + bob), fill="#c78324", width=4)
    elif mood == "love":
        for x in (119, 351):
            draw.line((x, 179 + bob, x + 10, 174 + bob), fill="#f995a8", width=3)
            draw.line((x + 2, 188 + bob, x + 13, 183 + bob), fill="#f995a8", width=3)


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
    elif mood == "love":
        cuddle = int((math.sin(tick / 5.0) + 1) * 2)
        paws = (
            (112 + cuddle, 217 + bob, 171 + cuddle, 278 + bob),
            (309 - cuddle, 217 + bob, 368 - cuddle, 278 + bob),
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
    elif mood == "sad":
        bob = 2 + int((math.sin(tick / 12.0) + 1) * 1.5)
    elif mood == "angry":
        bob = int(math.sin(tick * 1.6))
    elif mood == "love":
        bob = -1 - int((math.sin(tick / 6.0) + 1) * 1.5)
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
    cheek_fill = {
        "sad": "#d95752",
        "sleepy": "#df574c",
        "angry": "#f04636",
        "love": "#f15258",
    }.get(mood, CHEEK)
    draw.ellipse(
        (
            left_cheek[0] - cheek_pulse,
            left_cheek[1] - cheek_pulse,
            left_cheek[2] + cheek_pulse,
            left_cheek[3] + cheek_pulse,
        ),
        fill=cheek_fill,
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
        fill=cheek_fill,
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
    _draw_expression_accents(draw, mood, tick, bob, talking)
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
