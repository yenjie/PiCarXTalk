import argparse
import json
import queue
import random
import sys
import threading
import tkinter as tk
from dataclasses import dataclass


WIDTH = 480
HEIGHT = 320
BACKGROUND = "#ffe8a8"
FACE = "#fff6cf"
LINE = "#3b2b25"
BLUSH = "#ff9aa8"


@dataclass(frozen=True)
class Expression:
    name: str
    eye: str
    mouth: str
    brow: str = "none"
    blush: bool = False
    accessory: str = "none"


@dataclass(frozen=True)
class FaceCollection:
    name: str
    background: str
    face: str
    line: str
    cheek: str
    label: str


COLLECTIONS = {
    "1": FaceCollection("stack", BACKGROUND, FACE, LINE, BLUSH, "1 stack"),
    "2": FaceCollection("electric", "#fff2a0", "#ffd52e", "#2b211d", "#f04438", "2 pika"),
    "3": FaceCollection("wastebot", "#20272a", "#c79235", "#221a16", "#76d5ff", "3 wall-e"),
}


EXPRESSIONS = {
    "neutral": Expression("neutral", "oval", "small_smile"),
    "happy": Expression("happy", "closed", "tiny", blush=True),
    "excited": Expression("excited", "sparkle", "open_smile", blush=True, accessory="stars"),
    "thinking": Expression("thinking", "side", "flat", brow="raised"),
    "sad": Expression("sad", "oval", "sad", brow="sad", blush=False),
    "angry": Expression("angry", "oval", "flat", brow="angry"),
    "sleepy": Expression("sleepy", "happy", "smile", blush=True),
    "surprised": Expression("surprised", "round", "open_o", blush=True),
    "love": Expression("love", "heart", "smile", blush=True),
}

LLM_EMOTION_MAP = {
    "joy": "happy",
    "happy": "happy",
    "excited": "excited",
    "curious": "thinking",
    "thinking": "thinking",
    "confused": "thinking",
    "sad": "sad",
    "angry": "angry",
    "sleepy": "sleepy",
    "surprised": "surprised",
    "love": "love",
    "neutral": "neutral",
}


class StackChanFace(tk.Canvas):
    def __init__(self, root, initial_collection="1"):
        super().__init__(
            root,
            width=WIDTH,
            height=HEIGHT,
            bg=BACKGROUND,
            highlightthickness=0,
        )
        self.pack(fill=tk.BOTH, expand=True)
        self.collection_id = self.normalize_collection(initial_collection)
        self.expression_name = "neutral"
        self.blink = False
        self.look_offset = 0
        self.messages = queue.Queue()
        root.bind("1", lambda event: self.set_collection("1"))
        root.bind("2", lambda event: self.set_collection("2"))
        root.bind("3", lambda event: self.set_collection("3"))
        self.after(120, self._animate)
        self.after(900, self._maybe_blink)
        self.after(2200, self.random_expression)
        self.after(80, self._drain_messages)
        self.draw()

    @staticmethod
    def normalize_collection(collection_id):
        requested = str(collection_id).strip().lower()
        aliases = {
            "option 1": "1",
            "collection 1": "1",
            "stack": "1",
            "stackchan": "1",
            "stack-chan": "1",
            "option 2": "2",
            "collection 2": "2",
            "electric": "2",
            "pika": "2",
            "picachu": "2",
            "pikachu": "2",
            "option 3": "3",
            "collection 3": "3",
            "boxbot": "3",
            "wastebot": "3",
            "robot": "3",
            "walle": "3",
            "wall-e": "3",
            "wall e": "3",
        }
        normalized = aliases.get(requested, requested)
        if normalized not in COLLECTIONS:
            return "1"
        return normalized

    def set_collection(self, collection_id):
        self.collection_id = self.normalize_collection(collection_id)
        self.draw()

    def set_expression(self, name):
        normalized = LLM_EMOTION_MAP.get(str(name).strip().lower(), "neutral")
        self.expression_name = normalized
        self.look_offset = random.choice([-8, -4, 0, 4, 8])
        self.draw()

    def random_expression(self):
        self.set_expression(random.choice(list(EXPRESSIONS)))
        self.after(random.randint(1800, 4200), self.random_expression)

    def _animate(self):
        self.look_offset = max(-10, min(10, self.look_offset + random.choice([-1, 0, 1])))
        self.draw()
        self.after(120, self._animate)

    def _maybe_blink(self):
        self.blink = True
        self.draw()
        self.after(120, self._end_blink)
        self.after(random.randint(2400, 5200), self._maybe_blink)

    def _end_blink(self):
        self.blink = False
        self.draw()

    def _drain_messages(self):
        while True:
            try:
                message = self.messages.get_nowait()
            except queue.Empty:
                break
            collection = message.get("collection")
            expression = message.get("expression")
            if collection:
                self.set_collection(collection)
            if expression:
                self.set_expression(expression)
        self.after(80, self._drain_messages)

    def draw(self):
        expression = EXPRESSIONS[self.expression_name]
        collection = COLLECTIONS[self.collection_id]
        self.delete("all")
        if self.collection_id == "3":
            self._draw_boxbot_body(collection)
            self._draw_boxbot_face(expression, collection)
        elif self.collection_id == "2":
            self._draw_electric_body(collection)
            self._draw_accessory(expression)
            self._draw_blush(expression, collection)
            self._draw_eyes(expression)
            self._draw_brows(expression)
            self._draw_electric_nose()
            self._draw_mouth(expression)
        else:
            self._draw_stack_body(collection)
            self._draw_accessory(expression)
            self._draw_blush(expression, collection)
            self._draw_eyes(expression)
            self._draw_brows(expression)
            self._draw_mouth(expression)
        self.create_text(
            240,
            300,
            text=f"{collection.label} / {expression.name}",
            fill="#7b5b46",
            font=("Arial", 14, "bold"),
        )

    def _draw_stack_body(self, collection):
        self.create_rectangle(0, 0, WIDTH, HEIGHT, fill=collection.background, outline="")
        self.create_oval(80, 18, 400, 338, fill=collection.face, outline=collection.line, width=6)
        self.create_oval(122, 244, 168, 294, fill="#f6d878", outline=collection.line, width=4)
        self.create_oval(312, 244, 358, 294, fill="#f6d878", outline=collection.line, width=4)

    def _draw_electric_body(self, collection):
        self.create_rectangle(0, 0, WIDTH, HEIGHT, fill=collection.background, outline="")
        self.create_polygon(
            330,
            214,
            430,
            142,
            394,
            214,
            452,
            214,
            358,
            304,
            390,
            238,
            338,
            260,
            fill="#f0c12f",
            outline=collection.line,
            width=4,
        )
        self.create_polygon(
            120,
            134,
            88,
            -30,
            218,
            78,
            fill=collection.face,
            outline=collection.line,
            width=5,
        )
        self.create_polygon(90, -28, 118, 72, 158, 50, fill="#2b211d", outline="")
        self.create_polygon(
            360,
            134,
            392,
            -30,
            262,
            78,
            fill=collection.face,
            outline=collection.line,
            width=5,
        )
        self.create_polygon(390, -28, 362, 72, 322, 50, fill="#2b211d", outline="")
        self.create_oval(96, 150, 384, 346, fill=collection.face, outline=collection.line, width=6)
        self.create_oval(70, 44, 410, 258, fill=collection.face, outline=collection.line, width=6)
        self.create_oval(102, 66, 378, 242, fill="#ffdc38", outline="")
        self.create_polygon(100, 188, 160, 206, 100, 228, fill="#8b5b22", outline="")
        self.create_polygon(380, 188, 320, 206, 380, 228, fill="#8b5b22", outline="")
        self.create_polygon(114, 218, 158, 246, 102, 268, fill=collection.face, outline=collection.line, width=4)
        self.create_polygon(366, 218, 322, 246, 378, 268, fill=collection.face, outline=collection.line, width=4)
        self.create_line(130, 240, 116, 254, fill=collection.line, width=3, capstyle=tk.ROUND)
        self.create_line(350, 240, 364, 254, fill=collection.line, width=3, capstyle=tk.ROUND)
        self.create_oval(130, 270, 206, 320, fill="#f5c82b", outline=collection.line, width=4)
        self.create_oval(274, 270, 350, 320, fill="#f5c82b", outline=collection.line, width=4)

    def _draw_boxbot_body(self, collection):
        self.create_rectangle(0, 0, WIDTH, HEIGHT, fill=collection.background, outline="")
        self.create_polygon(70, 240, 176, 220, 198, 294, 92, 314, fill="#151311", outline=collection.line, width=5)
        self.create_polygon(304, 220, 410, 240, 388, 314, 282, 294, fill="#151311", outline=collection.line, width=5)
        for x1, y1, x2, y2 in [(86, 250, 182, 232), (92, 274, 190, 256), (300, 232, 396, 250), (290, 256, 388, 274)]:
            self.create_line(x1, y1, x2, y2, fill="#3f3931", width=5)
        for x, y in [(90, 250), (122, 242), (128, 272), (326, 242), (358, 250), (320, 272)]:
            self.create_oval(x, y, x + 30, y + 30, fill="#625d54", outline="#0d0c0b", width=2)
        for x, y in [(102, 260), (140, 252), (338, 252), (350, 264)]:
            self.create_rectangle(x, y, x + 18, y + 8, fill="#2b2722", outline="")

        self.create_polygon(146, 166, 334, 166, 320, 286, 160, 286, fill="#744817", outline=collection.line, width=6)
        self.create_polygon(160, 182, 320, 182, 306, 276, 174, 276, fill="#c79235", outline="#e5ba62", width=3)
        self.create_rectangle(172, 194, 214, 222, fill="#55462e", outline=collection.line, width=2)
        self.create_rectangle(224, 196, 288, 214, fill="#6b5738", outline=collection.line, width=2)
        self.create_rectangle(178, 232, 204, 260, fill="#2d2923", outline=collection.line, width=2)
        self.create_rectangle(228, 232, 300, 254, fill="#40382d", outline=collection.line, width=2)
        self.create_rectangle(232, 238, 296, 248, fill="#211e1b", outline="")
        self.create_oval(292, 194, 314, 216, fill="#d3422f", outline=collection.line, width=2)
        self.create_oval(296, 198, 306, 208, fill="#ff8f7a", outline="")
        self.create_line(160, 182, 306, 276, fill="#e1a241", width=2)
        self.create_line(320, 182, 174, 276, fill="#5a3414", width=2)
        self.create_line(160, 224, 314, 224, fill="#8a5b20", width=3)
        self.create_line(214, 182, 210, 276, fill="#8a5b20", width=3)
        self.create_text(240, 264, text="WALL-E", fill="#3b2814", font=("Arial", 11, "bold"))

        self.create_line(148, 184, 106, 226, fill="#6b6255", width=8, capstyle=tk.ROUND)
        self.create_line(332, 184, 374, 226, fill="#6b6255", width=8, capstyle=tk.ROUND)
        self.create_line(106, 226, 84, 260, fill="#6b6255", width=7, capstyle=tk.ROUND)
        self.create_line(374, 226, 396, 260, fill="#6b6255", width=7, capstyle=tk.ROUND)
        self.create_line(78, 260, 108, 252, fill="#9b917d", width=5, capstyle=tk.ROUND)
        self.create_line(78, 260, 106, 274, fill="#9b917d", width=5, capstyle=tk.ROUND)
        self.create_line(402, 260, 372, 252, fill="#9b917d", width=5, capstyle=tk.ROUND)
        self.create_line(402, 260, 374, 274, fill="#9b917d", width=5, capstyle=tk.ROUND)

        self.create_rectangle(210, 140, 270, 178, fill="#756f63", outline=collection.line, width=4)
        self.create_line(222, 142, 200, 106, fill="#6f6656", width=8, capstyle=tk.ROUND)
        self.create_line(258, 142, 280, 106, fill="#6f6656", width=8, capstyle=tk.ROUND)
        self.create_rectangle(188, 96, 292, 118, fill="#6f6656", outline=collection.line, width=3)
        self.create_rectangle(144, 158, 336, 174, fill="#5a3f1a", outline="")

    def _draw_boxbot_face(self, expression, collection):
        left_x = 168 + self.look_offset
        right_x = 312 + self.look_offset
        y = 70
        if expression.brow == "angry":
            self.create_polygon(96, 28, 232, 42, 228, 58, 96, 46, fill=collection.line, outline="")
            self.create_polygon(248, 42, 384, 28, 384, 46, 252, 58, fill=collection.line, outline="")
        elif expression.brow == "sad":
            self.create_polygon(96, 52, 232, 32, 230, 50, 96, 70, fill=collection.line, outline="")
            self.create_polygon(248, 32, 384, 52, 384, 70, 250, 50, fill=collection.line, outline="")
        elif expression.brow == "raised":
            self.create_rectangle(100, 26, 232, 38, fill=collection.line, outline="")
            self.create_rectangle(248, 20, 380, 32, fill=collection.line, outline="")

        self.create_rectangle(210, 60, 270, 86, fill="#6f6656", outline=collection.line, width=3)
        self.create_oval(232, 66, 248, 82, fill="#4f4a43", outline=collection.line, width=2)
        self._boxbot_eye(left_x, y, expression, left=True)
        self._boxbot_eye(right_x, y, expression, left=False)
        self._boxbot_mouth(expression, collection)
        if expression.accessory == "stars":
            self.create_text(92, 58, text="*", fill="#ffe16a", font=("Arial", 26, "bold"))
            self.create_text(388, 58, text="*", fill="#ffe16a", font=("Arial", 26, "bold"))

    def _boxbot_eye(self, x, y, expression, left):
        if left:
            outer = (x - 88, y - 34, x - 58, y - 70, x + 66, y - 58, x + 84, y - 18, x + 58, y + 60, x - 74, y + 50)
            inner = (x - 74, y - 28, x - 52, y - 56, x + 52, y - 46, x + 68, y - 16, x + 48, y + 46, x - 62, y + 40)
            shade = "#5d574e"
        else:
            outer = (x - 84, y - 18, x - 66, y - 58, x + 58, y - 70, x + 88, y - 34, x + 74, y + 50, x - 58, y + 60)
            inner = (x - 68, y - 16, x - 52, y - 46, x + 52, y - 56, x + 74, y - 28, x + 62, y + 40, x - 48, y + 46)
            shade = "#7a7469"
        self.create_polygon(*outer, fill="#706b61", outline=LINE, width=5)
        self.create_polygon(*inner, fill=shade, outline="")
        self.create_oval(x - 54, y - 40, x + 54, y + 40, fill="#14191b", outline="#d8d5c7", width=5)
        self.create_oval(x - 38, y - 28, x + 38, y + 28, fill="#0b0e10", outline="#5a6b71", width=3)
        if self.blink or expression.eye == "closed":
            self.create_line(x - 30, y, x + 30, y, fill="#8fe7ff", width=6, capstyle=tk.ROUND)
            return
        if expression.eye == "heart":
            self._heart(x, y + 2, 16, "#ff6f8e")
        elif expression.eye == "happy":
            self.create_arc(x - 25, y - 2, x + 25, y + 32, start=200, extent=140, style=tk.ARC, outline="#8fe7ff", width=6)
        elif expression.eye == "round":
            self.create_oval(x - 18, y - 18, x + 18, y + 18, fill="#8fe7ff", outline="")
            self.create_oval(x - 7, y - 9, x + 5, y + 3, fill="#ffffff", outline="")
        elif expression.eye == "sparkle":
            self.create_oval(x - 20, y - 20, x + 20, y + 20, fill="#8fe7ff", outline="")
            self.create_text(x, y - 1, text="+", fill="#ffffff", font=("Arial", 16, "bold"))
        elif expression.eye == "side":
            offset = -10 if left else 10
            self.create_oval(x - 14 + offset, y - 14, x + 14 + offset, y + 14, fill="#8fe7ff", outline="")
        else:
            self.create_oval(x - 18, y - 18, x + 18, y + 18, fill="#8fe7ff", outline="")
            self.create_oval(x - 8, y - 10, x + 6, y + 4, fill="#ffffff", outline="")

    def _boxbot_mouth(self, expression, collection):
        self.create_rectangle(206, 244, 274, 264, fill="#2d2a24", outline=collection.line, width=3)
        if expression.mouth == "open_smile":
            self.create_rectangle(216, 248, 264, 260, fill="#8fe7ff", outline="")
            self.create_rectangle(228, 254, 252, 260, fill="#ff8798", outline="")
        elif expression.mouth == "open_o":
            self.create_oval(226, 246, 254, 264, fill="#8fe7ff", outline="")
        elif expression.mouth == "sad":
            self.create_arc(216, 250, 264, 274, start=25, extent=130, style=tk.ARC, outline="#8fe7ff", width=4)
        elif expression.mouth == "flat":
            self.create_line(216, 254, 264, 254, fill="#8fe7ff", width=4, capstyle=tk.ROUND)
        elif expression.mouth == "tiny":
            self.create_rectangle(232, 250, 248, 258, fill="#8fe7ff", outline="")
        else:
            self.create_arc(216, 238, 264, 264, start=205, extent=130, style=tk.ARC, outline="#8fe7ff", width=4)

    def _draw_accessory(self, expression):
        if expression.accessory == "heart":
            self._heart(240, 58, 22, "#f35b7f")
        elif expression.accessory == "stars":
            self.create_text(112, 78, text="*", fill="#ffbd3e", font=("Arial", 28, "bold"))
            self.create_text(366, 84, text="*", fill="#ffbd3e", font=("Arial", 24, "bold"))

    def _draw_blush(self, expression, collection):
        if self.collection_id == "2":
            self.create_oval(86, 150, 184, 248, fill=collection.cheek, outline=collection.line, width=4)
            self.create_oval(296, 150, 394, 248, fill=collection.cheek, outline=collection.line, width=4)
            self.create_oval(116, 172, 142, 194, fill="#ff776c", outline="")
            self.create_oval(326, 172, 352, 194, fill="#ff776c", outline="")
            self.create_line(88, 196, 56, 178, 88, 168, fill="#f7c400", width=4, capstyle=tk.ROUND)
            self.create_line(392, 196, 424, 178, 392, 168, fill="#f7c400", width=4, capstyle=tk.ROUND)
            return
        if not expression.blush:
            return
        self.create_oval(120, 176, 178, 206, fill=collection.cheek, outline="")
        self.create_oval(302, 176, 360, 206, fill=collection.cheek, outline="")

    def _draw_eyes(self, expression):
        left_x = 170 + self.look_offset
        right_x = 310 + self.look_offset
        y = 142
        if self.collection_id == "2":
            self._draw_pika_eyes(expression)
            return
        if self.blink or expression.eye == "closed":
            self._arc_eye(left_x, y, flipped=False)
            self._arc_eye(right_x, y, flipped=False)
            return
        if expression.eye == "happy":
            self._arc_eye(left_x, y + 8, flipped=True)
            self._arc_eye(right_x, y + 8, flipped=True)
        elif expression.eye == "sparkle":
            self._round_eye(left_x, y, 24)
            self._round_eye(right_x, y, 24)
            self.create_text(left_x - 7, y - 6, text="+", fill="#ffffff", font=("Arial", 16, "bold"))
            self.create_text(right_x - 7, y - 6, text="+", fill="#ffffff", font=("Arial", 16, "bold"))
        elif expression.eye == "side":
            self._round_eye(left_x, y, 22, pupil_offset=-8)
            self._round_eye(right_x, y, 22, pupil_offset=-8)
        elif expression.eye == "round":
            self._round_eye(left_x, y, 28)
            self._round_eye(right_x, y, 28)
        elif expression.eye == "heart":
            self._heart(left_x, y, 18, "#2b1e1a")
            self._heart(right_x, y, 18, "#2b1e1a")
        else:
            self._oval_eye(left_x, y)
            self._oval_eye(right_x, y)

    def _draw_pika_eyes(self, expression):
        left_x = 162 + self.look_offset
        right_x = 318 + self.look_offset
        y = 110
        if self.blink or expression.eye == "closed":
            self.create_arc(left_x - 28, y - 4, left_x + 28, y + 34, start=200, extent=140, style=tk.ARC, outline=LINE, width=6)
            self.create_arc(right_x - 28, y - 4, right_x + 28, y + 34, start=200, extent=140, style=tk.ARC, outline=LINE, width=6)
            return
        if expression.eye == "heart":
            self._heart(left_x, y, 20, "#2b1e1a")
            self._heart(right_x, y, 20, "#2b1e1a")
        elif expression.eye == "happy":
            self.create_arc(left_x - 30, y - 4, left_x + 30, y + 38, start=200, extent=140, style=tk.ARC, outline=LINE, width=7)
            self.create_arc(right_x - 30, y - 4, right_x + 30, y + 38, start=200, extent=140, style=tk.ARC, outline=LINE, width=7)
        elif expression.eye == "round":
            self._pika_eye(left_x, y, 28)
            self._pika_eye(right_x, y, 28)
        elif expression.eye == "sparkle":
            self._pika_eye(left_x, y, 27)
            self._pika_eye(right_x, y, 27)
            self.create_text(left_x - 7, y - 8, text="+", fill="#ffffff", font=("Arial", 16, "bold"))
            self.create_text(right_x - 7, y - 8, text="+", fill="#ffffff", font=("Arial", 16, "bold"))
        elif expression.eye == "side":
            self._pika_eye(left_x - 8, y, 25)
            self._pika_eye(right_x - 8, y, 25)
        else:
            self._pika_eye(left_x, y, 26)
            self._pika_eye(right_x, y, 26)

    def _pika_eye(self, x, y, radius):
        self.create_oval(x - radius, y - radius, x + radius, y + radius, fill="#2b1e1a", outline="")
        self.create_oval(x - 10, y - 14, x + 4, y, fill="#ffffff", outline="")

    def _heart(self, x, y, size, fill):
        self.create_oval(x - size, y - size, x, y, fill=fill, outline="")
        self.create_oval(x, y - size, x + size, y, fill=fill, outline="")
        self.create_polygon(
            x - size,
            y - size // 3,
            x + size,
            y - size // 3,
            x,
            y + size,
            fill=fill,
            outline="",
        )

    def _oval_eye(self, x, y):
        self.create_oval(x - 25, y - 34, x + 25, y + 34, fill="#2b1e1a", outline="")
        self.create_oval(x - 11, y - 23, x + 4, y - 8, fill="#ffffff", outline="")

    def _round_eye(self, x, y, radius, pupil_offset=0):
        self.create_oval(x - radius, y - radius, x + radius, y + radius, fill="#2b1e1a", outline="")
        self.create_oval(
            x - 10 + pupil_offset,
            y - 12,
            x + 4 + pupil_offset,
            y + 2,
            fill="#ffffff",
            outline="",
        )

    def _arc_eye(self, x, y, flipped):
        start = 200 if flipped else 20
        self.create_arc(
            x - 30,
            y - 22,
            x + 30,
            y + 26,
            start=start,
            extent=140,
            style=tk.ARC,
            outline=LINE,
            width=6,
        )

    def _draw_brows(self, expression):
        if expression.brow == "angry":
            self.create_line(132, 94, 202, 120, fill=LINE, width=6, capstyle=tk.ROUND)
            self.create_line(278, 120, 348, 94, fill=LINE, width=6, capstyle=tk.ROUND)
        elif expression.brow == "sad":
            self.create_line(132, 116, 202, 94, fill=LINE, width=6, capstyle=tk.ROUND)
            self.create_line(278, 94, 348, 116, fill=LINE, width=6, capstyle=tk.ROUND)
        elif expression.brow == "raised":
            self.create_line(136, 96, 202, 90, fill=LINE, width=5, capstyle=tk.ROUND)
            self.create_line(278, 90, 344, 96, fill=LINE, width=5, capstyle=tk.ROUND)

    def _draw_electric_nose(self):
        self.create_oval(233, 138, 247, 150, fill="#2b211d", outline="")

    def _draw_mouth(self, expression):
        if self.collection_id == "2":
            self._draw_electric_mouth(expression)
            return
        if expression.mouth == "smile":
            self.create_arc(190, 176, 290, 246, start=200, extent=140, style=tk.ARC, outline=LINE, width=7)
        elif expression.mouth == "open_smile":
            self.create_arc(188, 168, 292, 250, start=200, extent=140, style=tk.CHORD, fill="#442018", outline=LINE, width=5)
            self.create_arc(210, 204, 270, 250, start=0, extent=180, style=tk.CHORD, fill="#ff8798", outline="")
        elif expression.mouth == "small_smile":
            self.create_arc(206, 182, 274, 226, start=205, extent=130, style=tk.ARC, outline=LINE, width=6)
        elif expression.mouth == "sad":
            self.create_arc(202, 202, 278, 254, start=25, extent=130, style=tk.ARC, outline=LINE, width=6)
        elif expression.mouth == "flat":
            self.create_line(204, 216, 276, 216, fill=LINE, width=6, capstyle=tk.ROUND)
        elif expression.mouth == "tiny":
            self.create_oval(232, 210, 248, 222, fill=LINE, outline="")
        elif expression.mouth == "open_o":
            self.create_oval(216, 190, 264, 244, fill="#442018", outline=LINE, width=5)

    def _draw_electric_mouth(self, expression):
        if expression.mouth in {"tiny", "small_smile"}:
            self.create_line(240, 150, 240, 166, fill=LINE, width=4, capstyle=tk.ROUND)
            self.create_arc(212, 158, 242, 196, start=205, extent=130, style=tk.ARC, outline=LINE, width=5)
            self.create_arc(238, 158, 268, 196, start=205, extent=130, style=tk.ARC, outline=LINE, width=5)
        elif expression.mouth == "smile":
            self.create_line(240, 150, 240, 166, fill=LINE, width=4, capstyle=tk.ROUND)
            self.create_arc(202, 160, 242, 212, start=205, extent=130, style=tk.ARC, outline=LINE, width=6)
            self.create_arc(238, 160, 278, 212, start=205, extent=130, style=tk.ARC, outline=LINE, width=6)
        elif expression.mouth == "open_smile":
            self.create_line(240, 150, 240, 166, fill=LINE, width=4, capstyle=tk.ROUND)
            self.create_arc(202, 164, 278, 234, start=200, extent=140, style=tk.CHORD, fill="#442018", outline=LINE, width=5)
            self.create_arc(220, 200, 260, 234, start=0, extent=180, style=tk.CHORD, fill="#ff8798", outline="")
        elif expression.mouth == "sad":
            self.create_line(240, 150, 240, 166, fill=LINE, width=4, capstyle=tk.ROUND)
            self.create_arc(212, 180, 268, 222, start=25, extent=130, style=tk.ARC, outline=LINE, width=6)
        elif expression.mouth == "flat":
            self.create_line(212, 190, 268, 190, fill=LINE, width=6, capstyle=tk.ROUND)
        elif expression.mouth == "open_o":
            self.create_oval(220, 174, 260, 218, fill="#442018", outline=LINE, width=5)


def read_llm_commands(face):
    """Accept plain names or JSON lines like {"collection": 2, "emotion": "happy"}."""
    for line in sys.stdin:
        text = line.strip()
        if not text:
            continue
        message = {"collection": None, "expression": None}
        try:
            payload = json.loads(text)
            message["collection"] = payload.get("collection") or payload.get("option") or payload.get("face")
            message["expression"] = payload.get("emotion") or payload.get("expression") or payload.get("state")
        except json.JSONDecodeError:
            lowered = text.lower()
            if lowered in {"1", "2", "3"} or lowered.startswith("option ") or lowered.startswith("collection "):
                message["collection"] = text
            else:
                message["expression"] = text
        face.messages.put(message)


def parse_args():
    parser = argparse.ArgumentParser(description="Show a 480x320 animated face.")
    parser.add_argument(
        "-o",
        "--option",
        "--collection",
        default="1",
        help="Face collection to use at startup: 1=stack, 2=electric, 3=wastebot.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    root = tk.Tk()
    root.title("Stack-chan Face")
    root.geometry(f"{WIDTH}x{HEIGHT}")
    root.resizable(False, False)

    face = StackChanFace(root, initial_collection=args.option)
    threading.Thread(target=read_llm_commands, args=(face,), daemon=True).start()

    root.mainloop()


if __name__ == "__main__":
    main()
