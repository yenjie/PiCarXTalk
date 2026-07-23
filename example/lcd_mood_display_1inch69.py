#!/usr/bin/env python3
import argparse
import contextlib
import importlib.util
import io
import json
import math
import os
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path

import spidev as SPI
from PIL import Image, ImageDraw, ImageFont

from lcd_pikachu_renderer import render_pikachu

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LCD_PYTHON_DIR = os.getenv(
    "LCD_PYTHON_DIR",
    str(Path.home() / "LCD_Module_RPI_code" / "RaspberryPi" / "python"),
)
sys.path.append(LCD_PYTHON_DIR)
from lib import LCD_1inch69


WINDOW_PATH = os.getenv("PICARX_FACE_WINDOW", str(PROJECT_ROOT / "screen" / "window.py"))
LCD_RST = int(os.getenv("LCD_RST", "6"))
LCD_DC = int(os.getenv("LCD_DC", "4"))
# GPIO18 is used by I2S audio on the robot speaker/HifiBerry DAC.
# Use another GPIO for LCD backlight control, or wire BL to 3.3V.
LCD_BL = int(os.getenv("LCD_BL", "13"))
LCD_BUS = int(os.getenv("LCD_BUS", "0"))
LCD_DEVICE = int(os.getenv("LCD_DEVICE", "0"))
TEXT_FONT_SIZE = int(os.getenv("LCD_TEXT_FONT_SIZE", "16"))
TEXT_MAX_LINES = int(os.getenv("LCD_TEXT_MAX_LINES", "3"))
TEXT_BOX_ALPHA = int(os.getenv("LCD_TEXT_BOX_ALPHA", "150"))
TEXT_BOX_OUTLINE_ALPHA = int(os.getenv("LCD_TEXT_BOX_OUTLINE_ALPHA", "180"))
SUPPRESS_LCD_LIBRARY_STATUS = os.getenv("SUPPRESS_LCD_LIBRARY_STATUS", "1") != "0"


def load_window_module():
    spec = importlib.util.spec_from_file_location("picarx_window", WINDOW_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {WINDOW_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def lcd_size(orientation):
    if orientation == "portrait":
        return 240, 280
    return 280, 240


def render_for_lcd(image, size, mode):
    image = image.convert("RGB")
    if mode == "stretch":
        return image.resize(size, Image.Resampling.LANCZOS)

    if mode == "crop":
        source_ratio = image.width / image.height
        target_ratio = size[0] / size[1]
        if source_ratio > target_ratio:
            new_width = int(image.height * target_ratio)
            left = (image.width - new_width) // 2
            image = image.crop((left, 0, left + new_width, image.height))
        else:
            new_height = int(image.width / target_ratio)
            top = (image.height - new_height) // 2
            image = image.crop((0, top, image.width, top + new_height))
        return image.resize(size, Image.Resampling.LANCZOS)

    image.thumbnail(size, Image.Resampling.LANCZOS)
    frame = Image.new("RGB", size, "BLACK")
    x = (size[0] - image.width) // 2
    y = (size[1] - image.height) // 2
    frame.paste(image, (x, y))
    return frame


def close_lcd_display(disp):
    try:
        disp.module_exit()
    finally:
        for attr in ("RST_PIN", "DC_PIN"):
            pin = getattr(disp, attr, None)
            if pin is not None:
                try:
                    pin.close()
                except Exception:
                    pass


def canvas_to_image(canvas, width, height):
    ps = canvas.postscript(
        colormode="color",
        x=0,
        y=0,
        width=width,
        height=height,
        pagewidth=width,
        pageheight=height,
    )
    return Image.open(io.BytesIO(ps.encode("utf-8"))).convert("RGB")


def load_font(paths):
    for path in paths:
        try:
            return ImageFont.truetype(path, TEXT_FONT_SIZE)
        except OSError:
            pass
    return ImageFont.load_default()


def load_text_fonts():
    latin_font = load_font(
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        )
    )
    cjk_font = load_font(
        (
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        )
    )
    return {"latin": latin_font, "cjk": cjk_font}


def is_cjk_char(char):
    return (
        "\u3000" <= char <= "\u303f"  # CJK punctuation
        or "\u3400" <= char <= "\u4dbf"
        or "\u4e00" <= char <= "\u9fff"
        or "\uf900" <= char <= "\ufaff"
        or "\uff00" <= char <= "\uffef"  # Full-width forms such as ？！
    )


def font_for_char(char, fonts):
    return fonts["cjk"] if is_cjk_char(char) else fonts["latin"]


def text_width(draw, text, fonts):
    x = 0
    for char in text:
        bbox = draw.textbbox((0, 0), char, font=font_for_char(char, fonts))
        x += bbox[2] - bbox[0]
    return x


def text_height(text, fonts):
    heights = []
    for char in text or "A":
        bbox = font_for_char(char, fonts).getbbox(char)
        heights.append(bbox[3] - bbox[1])
    return max(heights) if heights else TEXT_FONT_SIZE


def draw_mixed_text(draw, xy, text, fonts, fill):
    x, y = xy
    for char in text:
        font = font_for_char(char, fonts)
        draw.text((x, y), char, fill=fill, font=font)
        bbox = draw.textbbox((0, 0), char, font=font)
        x += bbox[2] - bbox[0]


def wrap_text(draw, text, fonts, max_width):
    compact_text = " ".join(text.split())
    if not compact_text:
        return []
    lines = []
    current = ""
    for char in compact_text:
        candidate = f"{current}{char}" if current else char
        if text_width(draw, candidate, fonts) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = char
    if current:
        lines.append(current)
    return lines[-TEXT_MAX_LINES:]


def draw_response_text(image, text, fonts):
    text = " ".join(str(text or "").split())
    if not text:
        return image

    image = image.convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    margin = 14
    line_gap = 3
    max_width = image.width - margin * 2
    lines = wrap_text(draw, text, fonts, max_width)
    if not lines:
        return image.convert("RGB")

    line_height = max(text_height(line, fonts) for line in lines)
    box_height = margin + len(lines) * line_height + (len(lines) - 1) * line_gap
    top = image.height - box_height - 10
    draw.rounded_rectangle(
        (8, top, image.width - 8, image.height - 8),
        radius=10,
        fill=(255, 248, 218, max(0, min(255, TEXT_BOX_ALPHA))),
        outline=(59, 43, 37, max(0, min(255, TEXT_BOX_OUTLINE_ALPHA))),
        width=2,
    )
    y = top + margin // 2
    for line in lines:
        draw_mixed_text(draw, (margin, y), line, fonts, fill=(43, 33, 29, 255))
        y += line_height + line_gap
    return Image.alpha_composite(image, overlay).convert("RGB")


def draw_sleep_fish(image, font, tick):
    image = image.convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = image.size
    fish = [
        ("><>", 28, 0, 1, (255, 165, 80, 235)),
        ("><((('>", 76, 120, 1, (95, 220, 255, 235)),
        ("<><", 122, 210, -1, (255, 95, 160, 235)),
        ("<'))><", 172, 50, -1, (120, 255, 140, 235)),
        ("><>", height - 96, 280, 1, (210, 150, 255, 235)),
    ]
    swim_width = width + 110
    for text, y, offset, direction, color in fish:
        progress = (tick * 9 + offset) % swim_width
        if direction > 0:
            x = progress - 90
        else:
            x = width - progress + 35
        draw.text((x + 1, y + 1), text, fill=(16, 43, 52, 180), font=font)
        draw.text((x, y), text, fill=color, font=font)
    return Image.alpha_composite(image, overlay).convert("RGB")


def draw_meteor_shower(image, tick):
    image = image.convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = image.size
    meteors = [
        (20, 15, 0, (255, 248, 170, 230)),
        (92, 46, 37, (120, 220, 255, 220)),
        (154, 20, 78, (255, 140, 210, 215)),
        (226, 64, 119, (180, 255, 170, 215)),
    ]
    travel = width + height
    for base_x, base_y, offset, color in meteors:
        progress = (tick * 14 + offset) % travel
        x = (base_x + progress) % (width + 80) - 40
        y = (base_y + progress * 0.42) % (height // 2 + 42) - 18
        tail = 24 + (offset % 3) * 8
        draw.line((x - tail, y - tail // 2, x, y), fill=color, width=3)
        draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 255, 245, 245))
    return Image.alpha_composite(image, overlay).convert("RGB")


def draw_listening_waves(image, tick):
    image = image.convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = image.size
    centers = [
        (42, height // 2 - 12, (95, 220, 255, 225)),
        (width - 42, height // 2 - 12, (255, 180, 95, 220)),
    ]
    pulse = tick % 18
    for cx, cy, color in centers:
        for idx in range(3):
            radius = 14 + idx * 12 + pulse
            alpha = max(60, 220 - idx * 45 - pulse * 7)
            fill = color[:3] + (alpha,)
            if cx < width // 2:
                box = (cx - radius, cy - radius, cx + radius, cy + radius)
                draw.arc(box, start=-55, end=55, fill=fill, width=3)
            else:
                box = (cx - radius, cy - radius, cx + radius, cy + radius)
                draw.arc(box, start=125, end=235, fill=fill, width=3)
    return Image.alpha_composite(image, overlay).convert("RGB")


def draw_idea_icon(image, tick):
    image = image.convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = image.size
    bulbs = [
        (width - 78, 48, 0, 1.0, (255, 235, 96)),
        (58, 66, 13, 0.72, (104, 220, 255)),
        (width // 2 + 8, 35, 27, 0.62, (255, 135, 215)),
        (width - 44, height // 2 - 18, 39, 0.58, (150, 255, 155)),
    ]

    for base_x, base_y, offset, scale, color in bulbs:
        phase = (tick + offset) / 12.0
        cx = int(base_x + math.sin(phase) * 9)
        cy = int(base_y + math.cos(phase * 0.8) * 7)
        bulb_w = int(19 * scale)
        bulb_h = int(24 * scale)
        glow = int((32 + (tick + offset) % 16) * scale)
        alpha = 70 if scale >= 0.8 else 52

        draw.ellipse((cx - glow, cy - glow, cx + glow, cy + glow), fill=color + (alpha,))
        draw.ellipse(
            (cx - bulb_w, cy - bulb_h, cx + bulb_w, cy + int(14 * scale)),
            fill=color + (235,),
            outline=(66, 50, 42, 220),
            width=max(2, int(3 * scale)),
        )
        base_w = int(10 * scale)
        base_top = cy + int(9 * scale)
        draw.rectangle(
            (cx - base_w, base_top, cx + base_w, base_top + int(13 * scale)),
            fill=(104, 82, 64, 235),
            outline=(48, 38, 34, 210),
        )
        ray = int(34 * scale)
        for angle in (-70, -35, 0, 35, 70):
            radians = math.radians(angle - 90)
            x1 = cx + int(math.cos(radians) * (ray - 9))
            y1 = cy + int(math.sin(radians) * (ray - 9))
            x2 = cx + int(math.cos(radians) * ray)
            y2 = cy + int(math.sin(radians) * ray)
            draw.line((x1, y1, x2, y2), fill=color + (210,), width=max(1, int(3 * scale)))
    return Image.alpha_composite(image, overlay).convert("RGB")


def read_display_commands(command_queue):
    for line in sys.stdin:
        raw = line.strip()
        if not raw:
            continue
        command = {
            "collection": None,
            "expression": None,
            "text": None,
            "sleep_fish": None,
            "meteor_shower": None,
            "listening_waves": None,
            "idea_icon": None,
        }
        try:
            payload = json.loads(raw)
            command["collection"] = payload.get("collection") or payload.get("option") or payload.get("face")
            command["expression"] = payload.get("emotion") or payload.get("expression") or payload.get("state")
            if "text" in payload:
                command["text"] = str(payload.get("text") or "")
            if "sleep_fish" in payload:
                command["sleep_fish"] = bool(payload.get("sleep_fish"))
            if "meteor_shower" in payload:
                command["meteor_shower"] = bool(payload.get("meteor_shower"))
            if "listening_waves" in payload:
                command["listening_waves"] = bool(payload.get("listening_waves"))
            if "idea_icon" in payload:
                command["idea_icon"] = bool(payload.get("idea_icon"))
        except json.JSONDecodeError:
            lowered = raw.lower()
            if lowered in {"1", "2", "3"} or lowered.startswith("option ") or lowered.startswith("collection "):
                command["collection"] = raw
            else:
                command["expression"] = raw
        command_queue.put(command)


def parse_args():
    parser = argparse.ArgumentParser(description="Mirror the PiCar-X animated face to the 1.69 LCD.")
    parser.add_argument("--list-faces", action="store_true", help="Print available face collections and expressions.")
    parser.add_argument("-o", "--option", "--collection", default="2", help="Initial face collection: 1, 2, or 3.")
    parser.add_argument(
        "-e",
        "--expression",
        default="neutral",
        help="Initial expression: neutral, happy, excited, thinking, sad, angry, sleepy, surprised, or love.",
    )
    parser.add_argument(
        "--mode",
        choices=("fit", "crop", "stretch"),
        default="fit",
        help="How to map the 480x320 Tk window onto the LCD.",
    )
    parser.add_argument(
        "--orientation",
        choices=("landscape", "portrait"),
        default="landscape",
        help="LCD orientation to use.",
    )
    parser.add_argument("--fps", type=float, default=4.0, help="LCD refresh rate.")
    parser.add_argument("--backlight", type=int, default=100, help="Backlight duty cycle, 0-100.")
    parser.add_argument("--cycle-collections", type=float, default=0, help="Automatically switch face collections every N seconds.")
    parser.add_argument("--hide-window", action="store_true", help="Hide the Tk window on the HDMI desktop.")
    return parser.parse_args()


def main():
    os.environ.setdefault("GPIOZERO_PIN_FACTORY", "lgpio")
    args = parse_args()
    window = load_window_module()
    window.EXPRESSIONS["happy"] = window.Expression("happy", "round", "open_smile", blush=True)
    window.EXPRESSIONS["sleepy"] = window.Expression("sleepy", "closed", "tiny", blush=False)
    window.StackChanFace.random_expression = lambda self: None
    if args.list_faces:
        print("Collections:")
        for key, collection in window.COLLECTIONS.items():
            print(f"  {key}: {collection.name} ({collection.label})")
        print("Expressions:")
        for name in window.EXPRESSIONS:
            print(f"  {name}")
        return

    root = tk.Tk()
    root.title("Stack-chan Face LCD Source")
    root.geometry(f"{window.WIDTH}x{window.HEIGHT}")
    root.resizable(False, False)
    if args.hide_window:
        root.withdraw()

    face = window.StackChanFace(root, initial_collection=args.option)
    face.set_expression(args.expression)
    text_state = {"value": ""}
    sleep_fish_state = {"enabled": False, "tick": 0}
    meteor_shower_state = {"enabled": False, "tick": 0}
    listening_waves_state = {"enabled": False, "tick": 0}
    idea_icon_state = {"enabled": False, "tick": 0}
    animation_state = {"tick": 0}
    command_queue = queue.Queue()
    text_fonts = load_text_fonts()
    threading.Thread(target=read_display_commands, args=(command_queue,), daemon=True).start()

    print("Face commands: type 1, 2, 3, stack, pika, wall-e, or an expression name, then press Enter.", flush=True)
    print('JSON also works, for example: {"collection": "pika", "expression": "happy"}', flush=True)

    disp = LCD_1inch69.LCD_1inch69(
        spi=SPI.SpiDev(LCD_BUS, LCD_DEVICE),
        spi_freq=10000000,
        rst=LCD_RST,
        dc=LCD_DC,
        bl=LCD_BL,
    )
    disp.Init()
    disp.clear()
    disp.bl_DutyCycle(max(0, min(100, args.backlight)))
    print("[LCD_READY]", flush=True)

    interval_ms = max(50, int(1000 / max(args.fps, 0.1)))
    target_size = lcd_size(args.orientation)

    def cycle_collection(index=0):
        if args.cycle_collections <= 0:
            return
        collection_ids = list(window.COLLECTIONS)
        face.set_collection(collection_ids[index % len(collection_ids)])
        root.after(int(args.cycle_collections * 1000), lambda: cycle_collection(index + 1))

    def update_lcd():
        try:
            while True:
                try:
                    command = command_queue.get_nowait()
                except queue.Empty:
                    break
                collection = command.get("collection")
                expression = command.get("expression")
                if collection:
                    face.set_collection(collection)
                    print(f"[LCD_COLLECTION] {collection}", flush=True)
                if expression:
                    face.set_expression(expression)
                    print(f"[LCD_EXPRESSION] {expression}", flush=True)
                if command.get("text") is not None:
                    text_state["value"] = command["text"]
                    print(f"[LCD_TEXT] {text_state['value'][:60]}", flush=True)
                if command.get("sleep_fish") is not None:
                    sleep_fish_state["enabled"] = bool(command["sleep_fish"])
                    state = "on" if sleep_fish_state["enabled"] else "off"
                    print(f"[LCD_SLEEP_FISH] {state}", flush=True)
                if command.get("meteor_shower") is not None:
                    meteor_shower_state["enabled"] = bool(command["meteor_shower"])
                    state = "on" if meteor_shower_state["enabled"] else "off"
                    print(f"[LCD_METEOR_SHOWER] {state}", flush=True)
                if command.get("listening_waves") is not None:
                    listening_waves_state["enabled"] = bool(command["listening_waves"])
                    state = "on" if listening_waves_state["enabled"] else "off"
                    print(f"[LCD_LISTENING_WAVES] {state}", flush=True)
                if command.get("idea_icon") is not None:
                    idea_icon_state["enabled"] = bool(command["idea_icon"])
                    state = "on" if idea_icon_state["enabled"] else "off"
                    print(f"[LCD_IDEA_ICON] {state}", flush=True)

            root.update_idletasks()
            if face.collection_id == "2":
                image = render_pikachu(
                    (window.WIDTH, window.HEIGHT),
                    face.expression_name,
                    animation_state["tick"],
                )
            else:
                image = canvas_to_image(face, window.WIDTH, window.HEIGHT)
            animation_state["tick"] += 1
            if sleep_fish_state["enabled"]:
                image = draw_sleep_fish(image, text_fonts["latin"], sleep_fish_state["tick"])
                sleep_fish_state["tick"] += 1
            if listening_waves_state["enabled"]:
                image = draw_listening_waves(image, listening_waves_state["tick"])
                listening_waves_state["tick"] += 1
            if meteor_shower_state["enabled"]:
                image = draw_meteor_shower(image, meteor_shower_state["tick"])
                meteor_shower_state["tick"] += 1
            if idea_icon_state["enabled"]:
                image = draw_idea_icon(image, idea_icon_state["tick"])
                idea_icon_state["tick"] += 1
            image = draw_response_text(image, text_state["value"], text_fonts)
            frame = render_for_lcd(image, target_size, args.mode)
            if SUPPRESS_LCD_LIBRARY_STATUS:
                with contextlib.redirect_stdout(io.StringIO()):
                    disp.ShowImage(frame)
            else:
                disp.ShowImage(frame)
        except tk.TclError:
            return
        except Exception as e:
            print(f"[LCD_ERROR] update failed: {e}", flush=True)
        root.after(interval_ms, update_lcd)

    try:
        cycle_collection()
        root.after(250, update_lcd)
        root.mainloop()
    finally:
        close_lcd_display(disp)


if __name__ == "__main__":
    main()
