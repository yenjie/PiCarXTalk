#!/usr/bin/env python3
"""Lightweight state-driven Pikachu renderer for the talking-robot LCD."""

import math

from PIL import Image, ImageDraw


MOOD_BACKGROUNDS = {
    "neutral": "#dff3f0",
    "happy": "#aee9cd",
    "excited": "#9de8f7",
    "thinking": "#d9d3f2",
    "sad": "#c9d9ec",
    "angry": "#f2c5b8",
    "sleepy": "#c9c6df",
    "surprised": "#ffda8a",
    "love": "#f2c8d8",
}
VALID_MOODS = tuple(MOOD_BACKGROUNDS)
INK = "#2b211d"
YELLOW = "#ffd83d"
YELLOW_LIGHT = "#ffe86b"
CHEEK = "#ed4b3f"


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


def _background_details(draw, mood, tick, width, height):
    phase = tick / 7.0
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
        for index, (x, y, color) in enumerate(
            ((54, 64, "#6754a6"), (414, 42, "#d88b35"), (428, 142, "#478a9b"))
        ):
            offset = int(math.sin(phase + index * 1.7) * 5)
            draw.rounded_rectangle((x - 8, y - 8 + offset, x + 8, y + 8 + offset), radius=3, fill=color)
    elif mood == "sad":
        offset = tick % 22
        for x, y in ((52, 42), (422, 72), (74, 150), (400, 170)):
            rain_y = (y + offset * 4) % (height - 60)
            draw.line((x, rain_y, x - 6, rain_y + 14), fill="#6f96bb", width=3)
    elif mood == "angry":
        for x, y in ((44, 62), (428, 70), (58, 168), (415, 176)):
            draw.line((x - 10, y - 7, x + 10, y + 7), fill="#bd4c3b", width=4)
            draw.line((x - 10, y + 7, x + 10, y - 7), fill="#bd4c3b", width=4)
    elif mood == "sleepy":
        drift = tick % 30
        for index, (x, y, size) in enumerate(((66, 55, 18), (402, 80, 14), (424, 142, 10))):
            _z_mark(draw, x + drift // 3, y - index * 3, size, "#665d91")
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
        for x, y, size in ((55, 58, 11), (420, 52, 13), (65, 165, 8), (408, 165, 9)):
            _heart(draw, x, y + bob, size, "#dd668f")
    else:
        draw.line((32, 42, 78, 42), fill="#67a89e", width=4)
        draw.line((402, 42, 448, 42), fill="#67a89e", width=4)


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


def _draw_ears(draw, mood, tick, bob, listening):
    twitch_amount = 10 if mood == "excited" else 6 if mood == "surprised" else 7 if listening else 3
    twitch_speed = 1.9 if mood == "excited" else 2.3 if listening else 6.5
    twitch = int(math.sin(tick / twitch_speed) * twitch_amount)
    if mood == "sleepy":
        left = ((164, 98 + bob), (70 + twitch, 45 + bob), (184, 132 + bob))
        right = ((316, 98 + bob), (410 - twitch, 45 + bob), (296, 132 + bob))
        left_tip = ((70 + twitch, 45 + bob), (112 + twitch // 2, 58 + bob), (126, 82 + bob))
        right_tip = ((410 - twitch, 45 + bob), (368 - twitch // 2, 58 + bob), (354, 82 + bob))
    else:
        listen_lift = 7 if listening else 0
        if mood == "surprised":
            left_top_x, right_top_x, ear_top_y = 75, 405, -2
        elif mood == "excited":
            left_top_x, right_top_x, ear_top_y = 98, 382, -24
        elif mood == "happy":
            left_top_x, right_top_x, ear_top_y = 96, 384, 0
        else:
            left_top_x, right_top_x, ear_top_y = 105, 375, -14
        left = (
            (158, 103 + bob),
            (left_top_x + twitch, ear_top_y + bob - listen_lift),
            (208, 77 + bob),
        )
        right = (
            (322, 103 + bob),
            (right_top_x - twitch, ear_top_y + bob - listen_lift),
            (272, 77 + bob),
        )
        left_tip = (
            (left_top_x + twitch, ear_top_y + bob - listen_lift),
            (left_top_x + 25 + twitch // 2, 42 + bob),
            (161, 35 + bob),
        )
        right_tip = (
            (right_top_x - twitch, ear_top_y + bob - listen_lift),
            (right_top_x - 25 - twitch // 2, 42 + bob),
            (319, 35 + bob),
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
        (126 - body_breathe, 222 + bob, 354 + body_breathe, 350 + bob),
        fill="#f4c72f",
        outline=INK,
        width=6,
    )
    draw.ellipse((111, 247 + bob, 177, 316 + bob), fill=YELLOW, outline=INK, width=5)
    draw.ellipse((303, 247 + bob, 369, 316 + bob), fill=YELLOW, outline=INK, width=5)
    draw.arc((119, 267 + bob, 170, 307 + bob), 200, 330, fill="#b48727", width=3)
    draw.arc((310, 267 + bob, 361, 307 + bob), 210, 340, fill="#b48727", width=3)
    _draw_ears(draw, mood, tick, bob, listening)
    draw.ellipse((72, 38 + bob, 408, 277 + bob), fill=YELLOW, outline=INK, width=7)
    if mood != "happy":
        draw.ellipse((99, 62 + bob, 381, 250 + bob), fill=YELLOW_LIGHT)

    if mood == "happy":
        cheek_pulse = 1 if tick % 10 < 5 else 0
        left_cheek = (96, 159 + bob, 151, 207 + bob)
        right_cheek = (329, 159 + bob, 384, 207 + bob)
    elif mood == "excited":
        cheek_pulse = 3 + (2 if tick % 6 < 3 else 0)
        left_cheek = (87, 151 + bob, 158, 211 + bob)
        right_cheek = (322, 151 + bob, 393, 211 + bob)
    elif mood == "surprised":
        cheek_pulse = -4
        left_cheek = (87, 151 + bob, 158, 211 + bob)
        right_cheek = (322, 151 + bob, 393, 211 + bob)
    else:
        cheek_pulse = 2 if talking and tick % 6 < 3 else 0
        left_cheek = (87, 151 + bob, 158, 211 + bob)
        right_cheek = (322, 151 + bob, 393, 211 + bob)
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
    if mood != "happy":
        draw.arc((100, 158 + bob, 143, 183 + bob), 205, 320, fill="#ff8c78", width=4)
        draw.arc((337, 158 + bob, 380, 183 + bob), 220, 335, fill="#ff8c78", width=4)
    if mood == "excited":
        spark_shift = int(math.sin(tick / 2.0) * 7)
    else:
        spark_shift = int(math.sin(tick / 3.0) * 3) if talking else 0
    if mood != "happy":
        draw.line((94, 181 + bob, 70 - spark_shift, 168 + bob, 92, 157 + bob), fill="#f4bf25", width=4)
        draw.line((386, 181 + bob, 410 + spark_shift, 168 + bob, 388, 157 + bob), fill="#f4bf25", width=4)

    if mood != "happy":
        draw.line((217, 56 + bob, 229, 70 + bob, 240, 54 + bob), fill="#d7a72b", width=3)
        draw.line((240, 54 + bob, 252, 70 + bob, 264, 56 + bob), fill="#d7a72b", width=3)

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
