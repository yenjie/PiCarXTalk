#!/usr/bin/env python3
"""PIL renderer for the enhanced Pikachu LCD face used by 19k."""

import math

from PIL import Image, ImageDraw


MOOD_BACKGROUNDS = {
    "neutral": "#dff3f0",
    "happy": "#bfead7",
    "excited": "#bde8f4",
    "thinking": "#d9d3f2",
    "sad": "#c9d9ec",
    "angry": "#f2c5b8",
    "sleepy": "#c9c6df",
    "surprised": "#f2ddae",
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
    if mood in {"happy", "excited"}:
        colors = ("#ffffff", "#4bbca9", "#f29b4b")
        for index, (x, y) in enumerate(((55, 54), (420, 64), (72, 180), (403, 170))):
            pulse = 2 + int((math.sin(phase + index) + 1) * 2)
            _spark(draw, x, y, 7 + pulse, colors[index % len(colors)], width=3)
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
        for x, y in ((50, 50), (427, 58), (62, 172), (413, 178)):
            draw.arc((x - 12, y - 12, x + 12, y + 12), 210, 510, fill="#b18335", width=3)
    elif mood == "love":
        bob = int(math.sin(phase) * 4)
        for x, y, size in ((55, 58, 11), (420, 52, 13), (65, 165, 8), (408, 165, 9)):
            _heart(draw, x, y + bob, size, "#dd668f")
    else:
        draw.line((32, 42, 78, 42), fill="#67a89e", width=4)
        draw.line((402, 42, 448, 42), fill="#67a89e", width=4)


def _draw_tail(draw, mood, bob):
    tail_fill = "#edbf2f" if mood != "angry" else "#e9a62d"
    draw.polygon(
        ((350, 205 + bob), (432, 147 + bob), (405, 206 + bob), (455, 205 + bob),
         (371, 291 + bob), (398, 232 + bob), (350, 250 + bob)),
        fill=tail_fill,
        outline=INK,
    )
    draw.line((350, 205 + bob, 432, 147 + bob, 405, 206 + bob, 455, 205 + bob), fill=INK, width=5)


def _draw_ears(draw, mood, bob):
    if mood == "sleepy":
        left = ((164, 98 + bob), (70, 45 + bob), (184, 132 + bob))
        right = ((316, 98 + bob), (410, 45 + bob), (296, 132 + bob))
        left_tip = ((70, 45 + bob), (112, 58 + bob), (126, 82 + bob))
        right_tip = ((410, 45 + bob), (368, 58 + bob), (354, 82 + bob))
    else:
        left = ((158, 103 + bob), (105, -14 + bob), (208, 77 + bob))
        right = ((322, 103 + bob), (375, -14 + bob), (272, 77 + bob))
        left_tip = ((105, -14 + bob), (130, 42 + bob), (161, 35 + bob))
        right_tip = ((375, -14 + bob), (350, 42 + bob), (319, 35 + bob))
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
    draw.ellipse((x - 10 + look, y - 18, x + 5 + look, y - 3), fill="#ffffff")
    draw.ellipse((x + 8 + look, y + 10, x + 14 + look, y + 16), fill="#8b5e45")


def _draw_eyes(draw, mood, tick, bob):
    left_x, right_x, y = 170, 310, 126 + bob
    if mood == "happy":
        _normal_eye(draw, left_x, y, wide=True)
        _normal_eye(draw, right_x, y, wide=True)
        _spark(draw, left_x + 4, y - 2, 9, "#ffffff", width=3)
        _spark(draw, right_x + 4, y - 2, 9, "#ffffff", width=3)
    elif mood == "excited":
        _normal_eye(draw, left_x, y, wide=True)
        _normal_eye(draw, right_x, y, wide=True)
        _spark(draw, left_x, y, 13, "#ffffff", width=4)
        _spark(draw, right_x, y, 13, "#ffffff", width=4)
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
        draw.arc((134, 103 + bob, 202, 151 + bob), 195, 345, fill=INK, width=8)
        draw.arc((278, 103 + bob, 346, 151 + bob), 195, 345, fill=INK, width=8)
    elif mood == "surprised":
        _normal_eye(draw, left_x, y, wide=True)
        _normal_eye(draw, right_x, y, wide=True)
        draw.arc((132, 72 + bob, 205, 102 + bob), 190, 350, fill=INK, width=5)
        draw.arc((275, 72 + bob, 348, 102 + bob), 190, 350, fill=INK, width=5)
    elif mood == "love":
        _heart(draw, left_x, y, 24, "#cf3e6e", outline=INK, width=2)
        _heart(draw, right_x, y, 24, "#cf3e6e", outline=INK, width=2)
    else:
        _normal_eye(draw, left_x, y)
        _normal_eye(draw, right_x, y)


def _draw_mouth(draw, mood, bob):
    y = 174 + bob
    draw.polygon(((236, 155 + bob), (244, 155 + bob), (240, 162 + bob)), fill=INK)
    if mood in {"happy", "love"}:
        draw.arc((193, y - 14, 240, y + 35), 5, 155, fill=INK, width=6)
        draw.arc((240, y - 14, 287, y + 35), 25, 175, fill=INK, width=6)
        draw.arc((211, y + 1, 269, y + 54), 0, 180, fill="#ce4c5d", width=5)
    elif mood == "excited":
        draw.ellipse((208, y - 5, 272, y + 53), fill="#542823", outline=INK, width=4)
        draw.arc((218, y + 24, 262, y + 54), 180, 360, fill="#ef7487", width=10)
    elif mood == "thinking":
        draw.line((218, y + 20, 257, y + 16, 268, y + 22), fill=INK, width=6, joint="curve")
    elif mood == "sad":
        draw.arc((207, y + 12, 273, y + 58), 195, 345, fill=INK, width=7)
    elif mood == "angry":
        draw.line((211, y + 28, 269, y + 22), fill=INK, width=7)
    elif mood == "sleepy":
        draw.ellipse((229, y + 12, 251, y + 29), fill="#684139", outline=INK, width=3)
    elif mood == "surprised":
        draw.ellipse((219, y + 4, 261, y + 52), fill="#542823", outline=INK, width=5)
    else:
        draw.arc((211, y - 1, 240, y + 31), 5, 155, fill=INK, width=5)
        draw.arc((240, y - 1, 269, y + 31), 25, 175, fill=INK, width=5)


def render_pikachu(size=(480, 320), expression="neutral", tick=0):
    """Render one animated Pikachu mood frame at the requested logical size."""
    mood = str(expression or "neutral").strip().lower()
    if mood not in VALID_MOODS:
        mood = "neutral"

    width, height = 480, 320
    image = Image.new("RGB", (width, height), MOOD_BACKGROUNDS[mood])
    draw = ImageDraw.Draw(image)
    _background_details(draw, mood, tick, width, height)

    bob = 0
    if mood == "excited":
        bob = -2 - int(abs(math.sin(tick / 3.0)) * 4)
    elif mood == "sleepy":
        bob = int((math.sin(tick / 8.0) + 1) * 2)

    _draw_tail(draw, mood, bob)
    draw.ellipse((126, 222 + bob, 354, 350 + bob), fill="#f4c72f", outline=INK, width=6)
    _draw_ears(draw, mood, bob)
    draw.ellipse((72, 38 + bob, 408, 277 + bob), fill=YELLOW, outline=INK, width=7)
    draw.ellipse((99, 62 + bob, 381, 250 + bob), fill=YELLOW_LIGHT)

    draw.ellipse((87, 151 + bob, 158, 211 + bob), fill=CHEEK, outline=INK, width=4)
    draw.ellipse((322, 151 + bob, 393, 211 + bob), fill=CHEEK, outline=INK, width=4)
    draw.line((94, 181 + bob, 70, 168 + bob, 92, 157 + bob), fill="#f4bf25", width=4)
    draw.line((386, 181 + bob, 410, 168 + bob, 388, 157 + bob), fill="#f4bf25", width=4)

    _draw_eyes(draw, mood, tick, bob)
    _draw_mouth(draw, mood, bob)

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
