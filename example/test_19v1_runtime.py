#!/usr/bin/env python3
import importlib.util
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import ImageChops

from lcd_pikachu_renderer import VALID_MOODS, render_pikachu


MODULE_PATH = Path(__file__).with_name("19v1.local_voice_chatbot_bilingual_thinking.py")
SPEC = importlib.util.spec_from_file_location("voice_chatbot_19v1", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
VOICE_CHATBOT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VOICE_CHATBOT)


class FastDummyChat:
    display_name = "dummy"

    def __init__(self) -> None:
        self.cancelled = threading.Event()

    def prompt(self, _text):
        index = 0
        while not self.cancelled.is_set():
            yield str(index)
            index += 1

    def cancel_current(self) -> None:
        self.cancelled.set()


class FakeCTranslateWhisper:
    is_multilingual = True

    def __init__(self, probabilities):
        self.probabilities = probabilities

    def detect_language(self, _encoder_output):
        return [self.probabilities]


class FakeWhisperModel:
    def __init__(self, language_model):
        self.model = language_model
        self.kwargs = None

    def transcribe(self, _audio, **kwargs):
        self.kwargs = kwargs
        if kwargs.get("multilingual"):
            self.model.detect_language(None)
        info = SimpleNamespace(language=kwargs.get("language"), language_probability=1.0)
        return iter((SimpleNamespace(text=" 你好，皮卡丘。"),)), info


class RuntimeTests(unittest.TestCase):
    def test_pcm16_rms_matches_reference(self):
        generator = np.random.default_rng(19)
        samples = generator.integers(-32768, 32767, size=4096, dtype=np.int16)
        expected = int(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
        self.assertLessEqual(abs(VOICE_CHATBOT.pcm16_rms(samples.tobytes()) - expected), 1)

    def test_prefetch_queue_is_bounded_and_cancellable(self):
        chat = FastDummyChat()
        response = VOICE_CHATBOT.PrefetchedChatResponse(chat, "hello")
        response.start()
        deadline = time.monotonic() + 2.0
        while response.items.qsize() < VOICE_CHATBOT.CHAT_PREFETCH_QUEUE_SIZE:
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.005)

        self.assertEqual(response.items.qsize(), VOICE_CHATBOT.CHAT_PREFETCH_QUEUE_SIZE)
        response.cancel()
        self.assertFalse(response.thread.is_alive())

    def test_shared_encoder_selects_allowed_language_and_hotwords(self):
        raw_model = FakeCTranslateWhisper(
            [
                ("<|ja|>", 0.44),
                ("<|zh|>", 0.41),
                ("<|en|>", 0.08),
            ]
        )
        limiter = VOICE_CHATBOT._AllowedLanguageModelProxy(raw_model, ("en", "zh"))
        fake_model = FakeWhisperModel(limiter)
        stt = VOICE_CHATBOT.WhisperSTT.__new__(VOICE_CHATBOT.WhisperSTT)
        stt.model = fake_model
        stt.model_lock = threading.Lock()
        stt.language_limiter = limiter
        stt.language = None
        stt.last_language = None
        stt.last_language_probability = None
        stt.listen_count = 0
        stt.beam_size = 2
        stt.vad_filter = False
        stt.supports_without_timestamps = True
        stt.hotwords = "Pikachu 皮卡丘"

        text, mode, probability = stt._transcribe_local("unused.wav")

        self.assertEqual(text, "你好，皮卡丘。")
        self.assertEqual(mode, "shared-encoder-auto")
        self.assertEqual(stt.last_language, "zh")
        self.assertAlmostEqual(probability, 0.41)
        self.assertTrue(fake_model.kwargs["multilingual"])
        self.assertEqual(fake_model.kwargs["language"], "en")
        self.assertEqual(fake_model.kwargs["hotwords"], "Pikachu 皮卡丘")

    def test_shared_encoder_rejects_confident_unsupported_language(self):
        raw_model = FakeCTranslateWhisper(
            [
                ("<|es|>", 0.82),
                ("<|en|>", 0.07),
                ("<|zh|>", 0.03),
            ]
        )
        limiter = VOICE_CHATBOT._AllowedLanguageModelProxy(raw_model, ("en", "zh"))

        with self.assertRaises(VOICE_CHATBOT._RejectedTranscriptionLanguage):
            limiter.detect_language(None)

        self.assertTrue(limiter.last_detection["rejected"])
        self.assertEqual(limiter.last_detection["selected"], "en")

    def test_terminate_process_reaps_child(self):
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            start_new_session=True,
        )
        VOICE_CHATBOT.terminate_process(proc, timeout=0.5, process_group=True)
        self.assertIsNotNone(proc.poll())

    def test_all_moods_and_activity_states_render(self):
        for mood in VALID_MOODS:
            with render_pikachu((320, 240), mood, tick=17) as frame:
                self.assertEqual(frame.size, (320, 240))

        with render_pikachu((320, 240), "happy", tick=24) as idle:
            with render_pikachu((320, 240), "happy", tick=24, talking=True) as talking:
                self.assertIsNotNone(ImageChops.difference(idle, talking).getbbox())
            with render_pikachu((320, 240), "happy", tick=24, listening=True) as listening:
                self.assertIsNotNone(ImageChops.difference(idle, listening).getbbox())


if __name__ == "__main__":
    unittest.main()
