#!/usr/bin/env python3
import importlib.util
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import ImageChops

from lcd_pikachu_renderer import EAR_POSES, VALID_MOODS, render_pikachu


MODULE_PATH = Path(__file__).with_name("19v2.local_voice_chatbot_interrupt_followup.py")
SPEC = importlib.util.spec_from_file_location("voice_chatbot_19v2", MODULE_PATH)
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


class FakeWakeListener:
    def __init__(self, text="hey robot"):
        self.text = text
        self.listen_calls = 0
        self.stop_calls = 0

    def listen(self, **_kwargs):
        self.listen_calls += 1
        return self.text

    def stop(self):
        self.stop_calls += 1


class FakeFollowupSTT:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def listen(self, **kwargs):
        self.calls.append(kwargs)
        return self.text


class FakeTTS:
    def __init__(self):
        self.interrupt_calls = 0
        self.interrupt_restarts = []
        self.say_calls = []

    def interrupt(self, restart=True):
        self.interrupt_calls += 1
        self.interrupt_restarts.append(restart)

    def say(self, text, **kwargs):
        self.say_calls.append((text, kwargs))


class FakeLCD:
    def __init__(self):
        self.updates = []

    def send_display(self, **kwargs):
        self.updates.append(kwargs)


class FakeOllamaResponse:
    def __init__(self):
        self.closed = False

    def raise_for_status(self):
        return None

    def iter_lines(self, decode_unicode=True):
        del decode_unicode
        yield '{"message":{"content":"partial answer"},"done":false}'

    def close(self):
        self.closed = True


class FakeOllamaSession:
    def __init__(self, response):
        self.response = response
        self.last_kwargs = None

    def post(self, *_args, **_kwargs):
        self.last_kwargs = _kwargs
        return self.response


class FakeWritableStdin:
    def __init__(self):
        self.lines = []

    def write(self, line):
        self.lines.append(line)

    def flush(self):
        pass


class FakeRunningProcess:
    def __init__(self):
        self.stdin = FakeWritableStdin()

    def poll(self):
        return None


class RuntimeTests(unittest.TestCase):
    def test_pcm16_rms_matches_reference(self):
        generator = np.random.default_rng(19)
        samples = generator.integers(-32768, 32767, size=4096, dtype=np.int16)
        expected = int(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
        self.assertLessEqual(abs(VOICE_CHATBOT.pcm16_rms(samples.tobytes()) - expected), 1)

    def test_noise_floor_does_not_quickly_absorb_quiet_speech(self):
        noise_floor = 180.0
        for _ in range(3):
            noise_floor = VOICE_CHATBOT.update_noise_floor(noise_floor, 500)
        self.assertLess(noise_floor, 200)

        falling_floor = VOICE_CHATBOT.update_noise_floor(noise_floor, 100)
        self.assertLess(falling_floor, noise_floor)

    def test_transcript_normalization_preserves_english_and_cleans_chinese(self):
        self.assertEqual(
            VOICE_CHATBOT.normalize_transcript_text("提醒我 明天早上 带雨伞 ？", "zh"),
            "提醒我明天早上帶雨傘？",
        )
        self.assertEqual(
            VOICE_CHATBOT.normalize_transcript_text("Pikachu 在 厨房 里", "zh"),
            "Pikachu 在廚房裡",
        )
        self.assertEqual(
            VOICE_CHATBOT.normalize_transcript_text("What is the weather today ?", "en"),
            "What is the weather today?",
        )

    def test_default_hotwords_cover_common_bilingual_prompt_phrases(self):
        for phrase in ("remind me", "set a timer", "帶雨傘", "請用", "光合作用"):
            self.assertIn(phrase, VOICE_CHATBOT.WHISPER_HOTWORDS)

    def test_vosk_wake_gate_accepts_only_exact_robot_phrases(self):
        self.assertTrue(VOICE_CHATBOT.is_vosk_wake_request("hello robot"))
        self.assertTrue(VOICE_CHATBOT.is_vosk_wake_request("Hey, robot!"))
        for near_match in (
            "hello robert",
            "hey robert",
            "yellow robot",
            "halo robot",
            "hello rabbit",
            "hello",
            "robot",
        ):
            self.assertFalse(
                VOICE_CHATBOT.is_vosk_wake_request(near_match),
                near_match,
            )

        self.assertTrue(
            set(VOICE_CHATBOT.WAKE_VOSK_PHRASES).isdisjoint(
                VOICE_CHATBOT.WAKE_VOSK_REJECT_PHRASES
            )
        )

    def test_important_memory_selection_is_bilingual_and_rejects_secrets(self):
        english = VOICE_CHATBOT.extract_important_memory(
            "Please remember that my name is Yenjie.",
            "en",
        )
        mandarin = VOICE_CHATBOT.extract_important_memory(
            "请记住我喜欢喝茶。",
            "zh",
        )

        self.assertEqual(english["text"], "my name is Yenjie.")
        self.assertEqual(english["topic"], "name")
        self.assertEqual(mandarin["text"], "我喜歡喝茶。")
        self.assertEqual(mandarin["language"], "zh")
        self.assertIsNone(
            VOICE_CHATBOT.extract_important_memory("What is my favorite color?", "en")
        )
        self.assertIsNone(
            VOICE_CHATBOT.extract_important_memory(
                "Remember my API key is secret-123.",
                "en",
            )
        )

    def test_important_memory_persists_deduplicates_and_updates_singleton_facts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "important.json"
            store = VOICE_CHATBOT.ImportantMemoryStore(memory_path, max_items=3)
            first_name = VOICE_CHATBOT.extract_important_memory("My name is Yenjie.", "en")
            new_name = VOICE_CHATBOT.extract_important_memory("My name is Alex.", "en")
            preference = VOICE_CHATBOT.extract_important_memory("I prefer short answers.", "en")

            self.assertTrue(store.remember(first_name))
            self.assertFalse(store.remember(first_name))
            self.assertTrue(store.remember(preference))
            self.assertTrue(store.remember(new_name))
            self.assertEqual(memory_path.stat().st_mode & 0o777, 0o600)

            reloaded = VOICE_CHATBOT.ImportantMemoryStore(memory_path, max_items=3)
            context = reloaded.prompt_context()
            self.assertNotIn("My name is Yenjie.", context)
            self.assertIn("My name is Alex.", context)
            self.assertIn("I prefer short answers.", context)
            self.assertEqual(len(reloaded.memories), 2)

    def test_important_memory_store_remains_bounded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "important.json"
            store = VOICE_CHATBOT.ImportantMemoryStore(memory_path, max_items=3)
            for index in range(8):
                self.assertTrue(
                    store.remember(
                        {
                            "text": f"I like preference {index}.",
                            "language": "en",
                            "topic": "",
                        }
                    )
                )

            self.assertEqual(len(store.memories), 3)
            self.assertNotIn("preference 4", store.prompt_context())
            self.assertIn("preference 7", store.prompt_context())
            self.assertEqual(
                len(VOICE_CHATBOT.ImportantMemoryStore(memory_path, max_items=3).memories),
                3,
            )

    def test_memory_commands_parse_in_english_and_mandarin(self):
        cases = (
            ("What do you remember about me?", "list"),
            ("List my memories.", "list"),
            ("Forget green tea.", "forget"),
            ("Forget everything.", "clear_request"),
            ("Confirm forget everything.", "clear_confirm"),
            ("你記得我什麼？", "list"),
            ("請忘記綠茶。", "forget"),
            ("清除所有记忆。", "clear_request"),
            ("确认忘记全部。", "clear_confirm"),
        )
        for text, expected_action in cases:
            with self.subTest(text=text):
                command = VOICE_CHATBOT.parse_memory_command(text)
                self.assertIsNotNone(command)
                self.assertEqual(command["action"], expected_action)

        self.assertIsNone(VOICE_CHATBOT.parse_memory_command("What is the weather?"))

    def test_memory_forget_and_guarded_clear_persist(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "important.json"
            store = VOICE_CHATBOT.ImportantMemoryStore(memory_path)
            store.remember(
                VOICE_CHATBOT.extract_important_memory("My name is Yenjie.", "en")
            )
            store.remember(
                VOICE_CHATBOT.extract_important_memory("I like green tea.", "en")
            )

            clear_request = VOICE_CHATBOT.execute_memory_command(
                store,
                {"action": "clear_request", "target": ""},
                "en",
            )
            self.assertTrue(clear_request["needs_clear_confirmation"])
            self.assertEqual(len(store.snapshot()), 2)

            unconfirmed = VOICE_CHATBOT.execute_memory_command(
                store,
                {"action": "clear_confirm", "target": ""},
                "en",
            )
            self.assertIn("no pending", str(unconfirmed["text"]).lower())
            self.assertEqual(len(store.snapshot()), 2)

            forgotten = VOICE_CHATBOT.execute_memory_command(
                store,
                {"action": "forget", "target": "green tea"},
                "en",
            )
            self.assertIn("I forgot:", forgotten["text"])
            self.assertEqual(len(store.snapshot()), 1)
            self.assertEqual(store.forget("it"), [])

            reloaded = VOICE_CHATBOT.ImportantMemoryStore(memory_path)
            self.assertEqual([item["text"] for item in reloaded.snapshot()], ["My name is Yenjie."])

            confirmed = VOICE_CHATBOT.execute_memory_command(
                reloaded,
                {"action": "clear_confirm", "target": ""},
                "en",
                clear_confirmed=True,
            )
            self.assertIn("all 1 memories", confirmed["text"])
            self.assertEqual(reloaded.snapshot(), [])
            self.assertEqual(VOICE_CHATBOT.ImportantMemoryStore(memory_path).snapshot(), [])

    def test_memory_retrieval_selects_relevant_bilingual_facts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = VOICE_CHATBOT.ImportantMemoryStore(Path(temp_dir) / "memory.json")
            for text, language in (
                ("My name is Yenjie.", "en"),
                ("I like green tea.", "en"),
                ("I prefer short answers.", "en"),
                ("我住在紐約。", "zh"),
            ):
                store.remember(VOICE_CHATBOT.extract_important_memory(text, language))

            likes = [item["text"] for item in store.relevant_memories("What do I like?")]
            location = [item["text"] for item in store.relevant_memories("我住在哪裡？")]
            unrelated = [
                item["text"]
                for item in store.relevant_memories("How far away is Saturn?")
            ]

            self.assertIn("I like green tea.", likes)
            self.assertNotIn("My name is Yenjie.", likes)
            self.assertIn("我住在紐約。", location)
            self.assertNotIn("I like green tea.", location)
            self.assertEqual(unrelated, ["I prefer short answers."])

    def test_memory_context_is_injected_into_codex_and_ollama(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = VOICE_CHATBOT.ImportantMemoryStore(Path(temp_dir) / "memory.json")
            store.remember(
                VOICE_CHATBOT.extract_important_memory("I like green tea.", "en")
            )
            store.remember(
                VOICE_CHATBOT.extract_important_memory("My name is Yenjie.", "en")
            )

            codex = VOICE_CHATBOT.CodexCLIChat(
                command="codex",
                instructions="base instructions",
                memory_store=store,
            )
            codex_prompt = codex._build_prompt("What do I like?")
            self.assertIn("I like green tea.", codex_prompt)
            self.assertNotIn("My name is Yenjie.", codex_prompt)

            ollama = VOICE_CHATBOT.OllamaStreamChat.__new__(VOICE_CHATBOT.OllamaStreamChat)
            ollama.model = "dummy"
            ollama.url = "http://unused"
            ollama.instructions = "base instructions"
            ollama.memory_store = store
            ollama.messages = [{"role": "system", "content": "base instructions"}]
            ollama.max_messages = 8
            ollama.response_lock = threading.Lock()
            ollama.active_response = None
            response = FakeOllamaResponse()
            ollama.session = FakeOllamaSession(response)

            stream = ollama.prompt("What do I like?")
            self.assertEqual(next(stream), "partial answer")
            system_prompt = ollama.session.last_kwargs["json"]["messages"][0]["content"]
            self.assertIn("I like green tea.", system_prompt)
            self.assertNotIn("My name is Yenjie.", system_prompt)
            stream.close()

    def test_memory_acknowledgement_matches_language_and_preserves_lcd_text(self):
        tts = FakeTTS()
        VOICE_CHATBOT.speak_memory_acknowledgement(tts, "en")
        VOICE_CHATBOT.speak_memory_acknowledgement(tts, "zh")

        self.assertEqual(tts.say_calls[0][0], "Now I remember it.")
        self.assertEqual(tts.say_calls[0][1]["language"], "en")
        self.assertFalse(tts.say_calls[0][1]["show_on_lcd"])
        self.assertEqual(tts.say_calls[1][0], "我記住了。")
        self.assertEqual(tts.say_calls[1][1]["language"], "zh")
        self.assertFalse(tts.say_calls[1][1]["show_on_lcd"])

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
        self.assertEqual(fake_model.kwargs["patience"], VOICE_CHATBOT.WHISPER_PATIENCE)

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

    def test_barge_in_captures_followup_question(self):
        wake_listener = FakeWakeListener()
        stt = FakeFollowupSTT("What is the tallest mountain?")
        tts = FakeTTS()
        lcd = FakeLCD()
        monitor = VOICE_CHATBOT.BargeInMonitor(wake_listener, stt, tts, lcd)

        monitor.start()
        followup = monitor.wait_for_followup()
        monitor.stop()

        self.assertTrue(monitor.interrupted())
        self.assertEqual(followup, "What is the tallest mountain?")
        self.assertEqual(tts.interrupt_calls, 1)
        self.assertEqual(tts.interrupt_restarts, [False])
        self.assertGreaterEqual(wake_listener.stop_calls, 2)
        self.assertEqual(len(stt.calls), 1)
        self.assertTrue(monitor.followup_capture_started.is_set())
        self.assertIsNotNone(monitor.last_handoff_seconds)
        self.assertIsNotNone(monitor.last_followup_seconds)
        self.assertEqual(
            stt.calls[0]["max_wait_seconds"],
            VOICE_CHATBOT.BARGE_IN_FOLLOWUP_START_TIMEOUT_SECONDS,
        )
        self.assertTrue(lcd.updates[-1]["listening_waves"])

    def test_prefetch_iterator_unblocks_on_interruption(self):
        response = VOICE_CHATBOT.PrefetchedChatResponse(FastDummyChat(), "hello")
        response.interrupt_event = threading.Event()
        response.interrupt_event.set()

        started = time.monotonic()
        self.assertEqual(list(response), [])
        self.assertLess(time.monotonic() - started, 0.1)

    def test_repeated_barge_in_cycles_leave_no_listener_thread(self):
        wake_listener = FakeWakeListener()
        monitor = VOICE_CHATBOT.BargeInMonitor(
            wake_listener,
            FakeFollowupSTT("A new question."),
            FakeTTS(),
            FakeLCD(),
        )

        for _ in range(20):
            monitor.start()
            self.assertEqual(monitor.wait_for_followup(), "A new question.")
            monitor.stop()
            self.assertFalse(monitor.thread.is_alive())

    def test_interrupted_ollama_turn_is_removed_from_history(self):
        backend = VOICE_CHATBOT.OllamaStreamChat.__new__(VOICE_CHATBOT.OllamaStreamChat)
        backend.model = "dummy"
        backend.url = "http://unused"
        backend.messages = [{"role": "system", "content": "test"}]
        backend.max_messages = 8
        backend.response_lock = threading.Lock()
        backend.active_response = None
        response = FakeOllamaResponse()
        backend.session = FakeOllamaSession(response)

        stream = backend.prompt("first question")
        self.assertEqual(next(stream), "partial answer")
        stream.close()

        self.assertTrue(response.closed)
        self.assertEqual(backend.messages, [{"role": "system", "content": "test"}])

    def test_suspended_tts_drops_stale_speech_but_accepts_control_messages(self):
        tts = VOICE_CHATBOT.TTSProcess.__new__(VOICE_CHATBOT.TTSProcess)
        tts.proc = FakeRunningProcess()
        tts.closed = False
        tts.suspended = True
        tts.send_lock = threading.Lock()

        self.assertFalse(tts.send({"command": "say", "text": "stale"}))
        self.assertEqual(tts.proc.stdin.lines, [])
        self.assertTrue(tts.send({"command": "sync", "id": "control"}))
        self.assertEqual(len(tts.proc.stdin.lines), 1)

    def test_tts_owned_temp_directory_cleanup(self):
        tts = VOICE_CHATBOT.TTSProcess.__new__(VOICE_CHATBOT.TTSProcess)
        with tempfile.TemporaryDirectory() as temp_dir:
            tts.worker_temp_dir = Path(temp_dir)
            (tts.worker_temp_dir / "interrupted.wav").write_bytes(b"partial")
            nested = tts.worker_temp_dir / "nested"
            nested.mkdir()
            (nested / "partial.mp3").write_bytes(b"partial")

            tts._cleanup_worker_temp_files()

            self.assertEqual(list(tts.worker_temp_dir.iterdir()), [])

    def test_terminate_process_reaps_child(self):
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            start_new_session=True,
        )
        VOICE_CHATBOT.terminate_process(proc, timeout=0.5, process_group=True)
        self.assertIsNotNone(proc.poll())

    def test_all_moods_and_activity_states_render(self):
        self.assertEqual(set(EAR_POSES), set(VALID_MOODS))
        self.assertEqual(len(set(EAR_POSES.values())), len(VALID_MOODS))

        mood_frames = {}
        for size in ((320, 240), (280, 240)):
            for mood in VALID_MOODS:
                with render_pikachu(size, mood, tick=17) as frame:
                    self.assertEqual(frame.size, size)
                    self.assertEqual(frame.mode, "RGB")
                    self.assertIsNotNone(frame.getbbox())
                    if size == (320, 240):
                        mood_frames[mood] = frame.tobytes()

        self.assertEqual(len(set(mood_frames.values())), len(VALID_MOODS))

        with render_pikachu((320, 240), "happy", tick=24) as idle:
            with render_pikachu((320, 240), "happy", tick=24, talking=True) as talking:
                self.assertIsNotNone(ImageChops.difference(idle, talking).getbbox())
            with render_pikachu((320, 240), "happy", tick=24, listening=True) as listening:
                self.assertIsNotNone(ImageChops.difference(idle, listening).getbbox())

        for mood in VALID_MOODS:
            with render_pikachu((280, 240), mood, tick=4) as early:
                with render_pikachu((280, 240), mood, tick=21) as later:
                    self.assertIsNotNone(
                        ImageChops.difference(early, later).getbbox(),
                        f"{mood} should animate between ticks",
                    )


if __name__ == "__main__":
    unittest.main()
