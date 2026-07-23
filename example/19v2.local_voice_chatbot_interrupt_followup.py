import json
import difflib
import functools
import inspect
import os
import queue
import random
import re
import signal
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave
from collections import deque
from pathlib import Path

import numpy as np
import requests

MIC_ALSA_DEVICE = os.getenv("MIC_ALSA_DEVICE", "plughw:CARD=Device,DEV=0")
MIC_SAMPLE_RATE = int(os.getenv("MIC_SAMPLE_RATE", "16000"))

#    "Use very short sentences. Keep replies brief, usually one to five sentences, unless instructed to elaobrate. If I ask you to elaborate, please try to generate long response "

INSTRUCTIONS = (
    "You are a playful, friendly robot sidekick. Answer directly in the user's language when possible. "
    "Use light humor, curious energy, and kid-friendly wording. "
    "If the user speaks Chinese, you may answer in Traditional Chinese. "
    "If the user speaks English, keep the answer in English. "
    "Prefer a short answer, usually one to three short sentences, unless the user explicitly asks you to elaborate or give details. "
    "Do not include raw URLs such as http:// or https:// in spoken answers. "
    "Do NOT include any hidden thinking, analysis, or tags like <think>."
)
WELCOME = "Hello! How can I help you?"
WAKE_PHRASES = tuple(
    phrase.strip().lower()
    for phrase in os.getenv("WAKE_PHRASES", "hello robot,hey robot,你好機器人,你好机器人,嘿機器人,嘿机器人").split(",")
    if phrase.strip()
)
WAKE_ALIASES = tuple(
    phrase.strip().lower()
    for phrase in os.getenv(
        "WAKE_ALIASES",
        "hello robert,hey robert,hello robots,hey robots,hello robo,hey robo,"
        "hello robit,hey robit,hallo robot,halo robot,the low robot,yellow robot",
    ).split(",")
    if phrase.strip()
)
WAKE_FUZZY_MATCH = os.getenv("WAKE_FUZZY_MATCH", "1") != "0"
WAKE_FUZZY_THRESHOLD = float(os.getenv("WAKE_FUZZY_THRESHOLD", "0.72"))
SLEEP_TIMEOUT_SECONDS = float(os.getenv("SLEEP_TIMEOUT_SECONDS", "180"))
SLEEP_TEXT = os.getenv("SLEEP_TEXT", "Sleeping. Say hello robot, hey robot, or 你好機器人.")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "10m")
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "1024"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "80"))
OLLAMA_NUM_PREDICT_DETAILED = int(os.getenv("OLLAMA_NUM_PREDICT_DETAILED", "180"))
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.6"))
OLLAMA_TOP_P = float(os.getenv("OLLAMA_TOP_P", "0.9"))
OLLAMA_WARMUP = os.getenv("OLLAMA_WARMUP", "1") != "0"
RESPONSE_BACKEND = os.getenv("RESPONSE_BACKEND", "ollama").lower()
CODEX_COMMAND = os.getenv("CODEX_COMMAND", "codex")
CODEX_MODEL = os.getenv("CODEX_MODEL", "gpt-5.3-codex-spark")
CODEX_REASONING_EFFORT = os.getenv("CODEX_REASONING_EFFORT", "low")
CODEX_VERBOSITY = os.getenv("CODEX_VERBOSITY", "low")
CODEX_TIMEOUT_SECONDS = float(os.getenv("CODEX_TIMEOUT_SECONDS", "90"))
CODEX_WEB_SEARCH = os.getenv("CODEX_WEB_SEARCH", "1") != "0"
MAX_MESSAGES = int(os.getenv("OLLAMA_MAX_MESSAGES", "8"))
CODEX_MAX_MESSAGES = int(os.getenv("CODEX_MAX_MESSAGES", "4"))
PLAYBACK_DEVICE = os.getenv("TTS_PLAYBACK_DEVICE", "pulse")
THINKING_SOUND_FILE = Path("/tmp/robot_thinking.wav")
FAST_WAKE_ACK_ENABLED = os.getenv("FAST_WAKE_ACK_ENABLED", "1") != "0"
FAST_WAKE_ACK_FILE = Path(os.getenv("FAST_WAKE_ACK_FILE", "/tmp/19k_fast_wake_ack.wav"))
FAST_WAKE_ACK_VOICE = os.getenv("FAST_WAKE_ACK_VOICE", "en-us")
FAST_WAKE_ACK_SPEED = int(os.getenv("FAST_WAKE_ACK_SPEED", "175"))
THINKING_FILLERS_EN = tuple(
    phrase.strip()
    for phrase in os.getenv(
        "THINKING_FILLERS_EN",
        os.getenv("THINKING_FILLERS", "Hmm.,Got it.,Let me think.,Ok."),
    ).split(",")
    if phrase.strip()
)
THINKING_FILLERS_ZH = tuple(
    phrase.strip()
    for phrase in os.getenv("THINKING_FILLERS_ZH", "嗯。,明白了。,讓我想想。,好。").split(",")
    if phrase.strip()
)
THINKING_FILLER_ENABLED = os.getenv("THINKING_FILLER_ENABLED", "1") != "0"
OLLAMA_THINKING_FILLER_DELAY_SECONDS = float(os.getenv("OLLAMA_THINKING_FILLER_DELAY_SECONDS", "0.9"))
CODEX_THINKING_FILLER_DELAY_SECONDS = float(os.getenv("CODEX_THINKING_FILLER_DELAY_SECONDS", "0.35"))

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "auto").strip().lower()
if WHISPER_LANGUAGE in {"", "auto", "detect"}:
    WHISPER_LANGUAGE = None
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
WHISPER_CPU_THREADS = int(
    os.getenv("WHISPER_CPU_THREADS", str(min(4, max(1, os.cpu_count() or 1))))
)
WHISPER_NUM_WORKERS = max(1, int(os.getenv("WHISPER_NUM_WORKERS", "1")))
WHISPER_BEAM_SIZE = int(os.getenv("WHISPER_BEAM_SIZE", "2"))
WHISPER_VAD_FILTER = os.getenv("WHISPER_VAD_FILTER", "0") != "0"
WHISPER_WITHOUT_TIMESTAMPS = os.getenv("WHISPER_WITHOUT_TIMESTAMPS", "1") != "0"
WHISPER_TEMPERATURE = float(os.getenv("WHISPER_TEMPERATURE", "0"))
WHISPER_BEST_OF = int(os.getenv("WHISPER_BEST_OF", "1"))
WHISPER_SHARED_ENCODER_LANGUAGE_DETECTION = (
    os.getenv("WHISPER_SHARED_ENCODER_LANGUAGE_DETECTION", "1") != "0"
)
WHISPER_HOTWORDS = os.getenv(
    "WHISPER_HOTWORDS",
    (
        "Pikachu PiCar-X Codex Ollama OpenAI Raspberry Pi robot supernova meteor shower "
        "Saturn photosynthesis New York 皮卡丘 派卡車 機器人 超新星 流星雨 土星 光合作用 紐約"
    ),
).strip()
WHISPER_ALLOWED_LANGUAGES = tuple(
    dict.fromkeys(
        "zh" if language.strip().lower() in {"zh", "cmn", "mandarin", "chinese"} else "en"
        for language in os.getenv("WHISPER_ALLOWED_LANGUAGES", "en,zh").split(",")
        if language.strip().lower() in {"en", "english", "zh", "cmn", "mandarin", "chinese"}
    )
)
if not WHISPER_ALLOWED_LANGUAGES:
    WHISPER_ALLOWED_LANGUAGES = ("en", "zh")
WHISPER_LANGUAGE_REJECT_MIN_PROB = float(os.getenv("WHISPER_LANGUAGE_REJECT_MIN_PROB", "0.12"))
WHISPER_LANGUAGE_REJECT_MARGIN = float(os.getenv("WHISPER_LANGUAGE_REJECT_MARGIN", "0.25"))
WHISPER_FAST_LANGUAGE_HINT = os.getenv("WHISPER_FAST_LANGUAGE_HINT", "0") != "0"
WHISPER_LANGUAGE_HINT_MIN_PROB = float(os.getenv("WHISPER_LANGUAGE_HINT_MIN_PROB", "0.65"))
WHISPER_LANGUAGE_AUTO_EVERY = int(os.getenv("WHISPER_LANGUAGE_AUTO_EVERY", "4"))
STT_BACKEND = os.getenv("STT_BACKEND", "local").strip().lower()
if STT_BACKEND in {"api", "cloud", "gpt"}:
    STT_BACKEND = "openai"
if "--stt-openai" in sys.argv or "--stt-gpt" in sys.argv:
    STT_BACKEND = "openai"
elif "--stt-local" in sys.argv:
    STT_BACKEND = "local"
OPENAI_TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-transcribe")
OPENAI_TRANSCRIBE_URL = os.getenv("OPENAI_TRANSCRIBE_URL", "https://api.openai.com/v1/audio/transcriptions")
OPENAI_TRANSCRIBE_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TRANSCRIBE_TIMEOUT_SECONDS", "30"))
OPENAI_TRANSCRIBE_PROMPT = os.getenv("OPENAI_TRANSCRIBE_PROMPT", "").strip()
VOICE_START_RMS = int(os.getenv("VOICE_START_RMS", "500"))
VOICE_END_RMS = int(os.getenv("VOICE_END_RMS", "250"))
END_SILENCE_SECONDS = float(os.getenv("END_SILENCE_SECONDS", "0.38"))
MAX_RECORD_SECONDS = float(os.getenv("MAX_RECORD_SECONDS", "12.0"))
VOICE_PREROLL_SECONDS = float(os.getenv("VOICE_PREROLL_SECONDS", "0.30"))
VOICE_MIN_RECORD_SECONDS = float(os.getenv("VOICE_MIN_RECORD_SECONDS", "0.30"))
VOICE_DYNAMIC_RMS = os.getenv("VOICE_DYNAMIC_RMS", "1") != "0"
VOICE_NOISE_FLOOR_ALPHA = float(os.getenv("VOICE_NOISE_FLOOR_ALPHA", "0.05"))
VOICE_START_RMS_MULTIPLIER = float(os.getenv("VOICE_START_RMS_MULTIPLIER", "1.8"))
VOICE_END_RMS_MULTIPLIER = float(os.getenv("VOICE_END_RMS_MULTIPLIER", "1.20"))
VOICE_START_HOLD_SECONDS = float(os.getenv("VOICE_START_HOLD_SECONDS", "0.12"))
WAKE_ENGINE = os.getenv("WAKE_ENGINE", "vosk").strip().lower()
if "--wake-vosk" in sys.argv:
    WAKE_ENGINE = "vosk"
elif "--wake-whisper" in sys.argv:
    WAKE_ENGINE = "whisper"
if WAKE_ENGINE in {"vosk", "auto"} and "SLEEP_TEXT" not in os.environ:
    SLEEP_TEXT = "Sleeping. Say hello robot or hey robot."
WAKE_VOSK_MODEL_PATH = Path(
    os.path.expanduser(
        os.getenv(
            "WAKE_VOSK_MODEL_PATH",
            "~/.vosk_models/vosk-model-small-en-us-0.15",
        )
    )
)
WAKE_VOSK_PHRASES = tuple(
    phrase.strip().lower()
    for phrase in os.getenv(
        "WAKE_VOSK_PHRASES",
        "hello robot,hey robot,hello robert,hey robert,yellow robot,halo robot",
    ).split(",")
    if phrase.strip()
)
WAKE_VOSK_REJECT_PHRASES = tuple(
    phrase.strip().lower()
    for phrase in os.getenv(
        "WAKE_VOSK_REJECT_PHRASES",
        "hello rabbit,hey rabbit,hello there,hey there,hello,hey,yellow,robot,robert,rabbit",
    ).split(",")
    if phrase.strip()
)
WAKE_VOSK_BLOCK_MS = int(os.getenv("WAKE_VOSK_BLOCK_MS", "80"))
WAKE_VOSK_PARTIAL_STABILITY_BLOCKS = int(os.getenv("WAKE_VOSK_PARTIAL_STABILITY_BLOCKS", "2"))
WAKE_VOSK_RESTART_SECONDS = float(os.getenv("WAKE_VOSK_RESTART_SECONDS", "0.5"))
WAKE_WHISPER_MODEL = os.getenv("WAKE_WHISPER_MODEL", "base.en")
WAKE_WHISPER_LANGUAGE = os.getenv("WAKE_WHISPER_LANGUAGE", "en").strip().lower()
if WAKE_WHISPER_LANGUAGE in {"", "auto", "detect"}:
    WAKE_WHISPER_LANGUAGE = None
WAKE_WHISPER_BEAM_SIZE = int(os.getenv("WAKE_WHISPER_BEAM_SIZE", "1"))
WAKE_WHISPER_VAD_FILTER = os.getenv("WAKE_WHISPER_VAD_FILTER", "0") != "0"
WAKE_WHISPER_HOTWORDS = os.getenv(
    "WAKE_WHISPER_HOTWORDS",
    "hello robot hey robot hello Robert hey Robert yellow robot halo robot",
).strip()
WAKE_STT_BACKEND = os.getenv("WAKE_STT_BACKEND", "local").strip().lower()
if WAKE_STT_BACKEND in {"api", "cloud", "gpt"}:
    WAKE_STT_BACKEND = "openai"
if "--wake-stt-openai" in sys.argv or "--wake-stt-gpt" in sys.argv:
    WAKE_STT_BACKEND = "openai"
elif "--wake-stt-local" in sys.argv:
    WAKE_STT_BACKEND = "local"
WAKE_OPENAI_TRANSCRIBE_MODEL = os.getenv("WAKE_OPENAI_TRANSCRIBE_MODEL", OPENAI_TRANSCRIBE_MODEL)
WAKE_VOICE_START_RMS = int(os.getenv("WAKE_VOICE_START_RMS", "450"))
WAKE_VOICE_END_RMS = int(os.getenv("WAKE_VOICE_END_RMS", "260"))
WAKE_END_SILENCE_SECONDS = float(os.getenv("WAKE_END_SILENCE_SECONDS", "0.32"))
WAKE_MAX_RECORD_SECONDS = float(os.getenv("WAKE_MAX_RECORD_SECONDS", "2.2"))
WAKE_CONTINUOUS_RECORDING = os.getenv("WAKE_CONTINUOUS_RECORDING", "1") != "0"
WAKE_CONTINUOUS_QUEUE_SIZE = int(os.getenv("WAKE_CONTINUOUS_QUEUE_SIZE", "4"))
WAKE_PREROLL_SECONDS = float(os.getenv("WAKE_PREROLL_SECONDS", "0.35"))
WAKE_MIN_RECORD_SECONDS = float(os.getenv("WAKE_MIN_RECORD_SECONDS", "0.35"))
WAKE_DYNAMIC_RMS = os.getenv("WAKE_DYNAMIC_RMS", "1") != "0"
WAKE_NOISE_FLOOR_ALPHA = float(os.getenv("WAKE_NOISE_FLOOR_ALPHA", "0.05"))
WAKE_START_RMS_MULTIPLIER = float(os.getenv("WAKE_START_RMS_MULTIPLIER", "1.8"))
WAKE_END_RMS_MULTIPLIER = float(os.getenv("WAKE_END_RMS_MULTIPLIER", "1.25"))
WAKE_CANDIDATE_MAX_AGE_SECONDS = float(os.getenv("WAKE_CANDIDATE_MAX_AGE_SECONDS", "8.0"))
WAKE_RECORDER_RESTART_SECONDS = float(os.getenv("WAKE_RECORDER_RESTART_SECONDS", "1.0"))
BARGE_IN_ENABLED = os.getenv("BARGE_IN_ENABLED", "1") != "0"
BARGE_IN_LISTEN_TIMEOUT_SECONDS = float(os.getenv("BARGE_IN_LISTEN_TIMEOUT_SECONDS", "0.35"))
BARGE_IN_FOLLOWUP_ENABLED = os.getenv("BARGE_IN_FOLLOWUP_ENABLED", "1") != "0"
BARGE_IN_FOLLOWUP_START_TIMEOUT_SECONDS = float(
    os.getenv("BARGE_IN_FOLLOWUP_START_TIMEOUT_SECONDS", "5.0")
)
BARGE_IN_FOLLOWUP_TOTAL_TIMEOUT_SECONDS = float(
    os.getenv("BARGE_IN_FOLLOWUP_TOTAL_TIMEOUT_SECONDS", "45.0")
)
BARGE_IN_INTERRUPT_POLL_SECONDS = max(
    0.02,
    float(os.getenv("BARGE_IN_INTERRUPT_POLL_SECONDS", "0.05")),
)
BARGE_IN_PHRASES = tuple(
    phrase.strip().lower()
    for phrase in os.getenv("BARGE_IN_PHRASES", "hello robot,hey robot").split(",")
    if phrase.strip()
)
TTS_MIN_CHARS = int(os.getenv("TTS_MIN_CHARS", "24"))
TTS_EAGER_CHARS = int(os.getenv("TTS_EAGER_CHARS", "72"))
STREAM_LOOP_SLEEP_SECONDS = float(os.getenv("STREAM_LOOP_SLEEP_SECONDS", "0"))
LCD_SCREEN = os.getenv("LCD_SCREEN", "1inch69").strip().lower()
if "--lcd-2inch4" in sys.argv:
    LCD_SCREEN = "2inch4"
elif "--lcd-1inch69" in sys.argv:
    LCD_SCREEN = "1inch69"
elif any(arg.startswith("--lcd-screen=") for arg in sys.argv):
    LCD_SCREEN = next(arg.split("=", 1)[1].strip().lower() for arg in sys.argv if arg.startswith("--lcd-screen="))
LCD_SCRIPT_BY_SCREEN = {
    "1.69": "lcd_mood_display_1inch69.py",
    "1inch69": "lcd_mood_display_1inch69.py",
    "2.4": "lcd_mood_display_2inch4.py",
    "2in4": "lcd_mood_display_2inch4.py",
    "2inch4": "lcd_mood_display_2inch4.py",
}
LCD_SCRIPT_NAME = LCD_SCRIPT_BY_SCREEN.get(LCD_SCREEN, "lcd_mood_display_1inch69.py")
LCD_SCRIPT = Path(os.getenv("LCD_SCRIPT", str(Path(__file__).with_name(LCD_SCRIPT_NAME))))
LCD_COLLECTION = os.getenv("LCD_COLLECTION", "2")
LCD_EXPRESSION = os.getenv("LCD_EXPRESSION", "neutral")
LCD_MODE = os.getenv("LCD_MODE", "fit")
LCD_ORIENTATION = os.getenv("LCD_ORIENTATION", "landscape")
LCD_FPS = os.getenv("LCD_FPS", "8")
LCD_BACKLIGHT = os.getenv("LCD_BACKLIGHT", "100")
HEAD_MOTION_ENABLED = os.getenv("HEAD_MOTION_ENABLED", "1") != "0"
HEAD_PAN_LIMIT = int(os.getenv("HEAD_PAN_LIMIT", "5"))
HEAD_TILT_UP_LIMIT = int(os.getenv("HEAD_TILT_UP_LIMIT", "4"))
HEAD_TILT_DOWN_LIMIT = int(os.getenv("HEAD_TILT_DOWN_LIMIT", "-4"))
HEAD_MOVE_MIN_SECONDS = float(os.getenv("HEAD_MOVE_MIN_SECONDS", "0.85"))
HEAD_MOVE_MAX_SECONDS = float(os.getenv("HEAD_MOVE_MAX_SECONDS", "1.8"))
HEAD_CENTER_ON_STARTUP = os.getenv("HEAD_CENTER_ON_STARTUP", "0") != "0"
HEAD_LAZY_INIT = os.getenv("HEAD_LAZY_INIT", "1") != "0"
TTS_SYNC_TIMEOUT_SECONDS = float(os.getenv("TTS_SYNC_TIMEOUT_SECONDS", "300"))
TTS_EVENT_QUEUE_SIZE = max(8, int(os.getenv("TTS_EVENT_QUEUE_SIZE", "32")))
TTS_SOFT_INTERRUPT_TIMEOUT_SECONDS = max(
    0.05,
    float(os.getenv("TTS_SOFT_INTERRUPT_TIMEOUT_SECONDS", "0.35")),
)
TTS_HARD_INTERRUPT_TIMEOUT_SECONDS = max(
    0.05,
    float(os.getenv("TTS_HARD_INTERRUPT_TIMEOUT_SECONDS", "0.2")),
)
CHAT_PREFETCH_QUEUE_SIZE = max(8, int(os.getenv("CHAT_PREFETCH_QUEUE_SIZE", "128")))
WORKER_JOIN_TIMEOUT_SECONDS = float(os.getenv("WORKER_JOIN_TIMEOUT_SECONDS", "2.0"))
PERF_LOG = os.getenv("PERF_LOG", "1") != "0"

LANGUAGE_NAMES = {
    "en": "英文",
    "zh": "中文",
}

MOODS = ("neutral", "happy", "excited", "thinking", "sad", "angry", "sleepy", "surprised", "love")


class _RejectedTranscriptionLanguage(Exception):
    pass


class _AllowedLanguageModelProxy:
    """Filter CTranslate2 language results while reusing its encoder output."""

    def __init__(self, model, allowed_languages: tuple[str, ...]) -> None:
        self._model = model
        self.allowed_tokens = frozenset(f"<|{language}|>" for language in allowed_languages)
        self.last_detection: dict[str, str | float | bool] = {}

    def __getattr__(self, name):
        return getattr(self._model, name)

    def reset_detection(self) -> None:
        self.last_detection = {}

    @staticmethod
    def _language_code(token: str) -> str:
        return token[2:-2] if token.startswith("<|") and token.endswith("|>") else token

    def detect_language(self, encoder_output):
        filtered_batches = []
        for probabilities in self._model.detect_language(encoder_output):
            if not probabilities:
                filtered_batches.append(probabilities)
                continue
            allowed = [item for item in probabilities if item[0] in self.allowed_tokens]
            if not allowed:
                filtered_batches.append(probabilities)
                continue

            detected_token, detected_probability = probabilities[0]
            selected_token, selected_probability = max(allowed, key=lambda item: item[1])
            detected = self._language_code(detected_token)
            selected = self._language_code(selected_token)
            self.last_detection = {
                "detected": detected,
                "detected_probability": detected_probability,
                "selected": selected,
                "selected_probability": selected_probability,
            }
            if (
                detected_token not in self.allowed_tokens
                and selected_probability < WHISPER_LANGUAGE_REJECT_MIN_PROB
                and detected_probability - selected_probability >= WHISPER_LANGUAGE_REJECT_MARGIN
            ):
                self.last_detection["rejected"] = True
                raise _RejectedTranscriptionLanguage

            selected_item = (selected_token, selected_probability)
            filtered_batches.append(
                [selected_item]
                + [item for item in probabilities if item != selected_item]
            )
        return filtered_batches


def pcm16_rms(data: bytes) -> int:
    """Calculate PCM RMS with one temporary array instead of two."""
    samples = np.frombuffer(data, dtype=np.int16)
    if not samples.size:
        return 0
    float_samples = samples.astype(np.float32)
    return int(np.sqrt(np.dot(float_samples, float_samples) / samples.size))


def terminate_process(
    proc: subprocess.Popen | None,
    timeout: float = 1.0,
    process_group: bool = False,
) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        if process_group:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        else:
            proc.terminate()
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=timeout)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        if process_group:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        else:
            proc.kill()
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        pass


def strip_thinking(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<\s*think[^>]*>.*?<\s*/\s*think\s*>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<\s*thinking[^>]*>.*?<\s*/\s*thinking\s*>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"```(?:\s*thinking)?\s*.*?```", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"\[/?thinking\]", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+\n", "\n", text).strip()


def normalize_for_tts(text: str) -> str:
    return " ".join(strip_thinking(text).split())


URL_REFERENCE_RE = re.compile(r"\bhttps?://[^\s<>\"']+", flags=re.IGNORECASE)


def _strip_url_reference_match(match: re.Match) -> str:
    trailing = ""
    url = match.group(0)
    while url and url[-1] in ".,;:!?)]}":
        trailing = url[-1] + trailing
        url = url[:-1]
    suffix = next((char for char in reversed(trailing) if char in ".!?。！？"), "")
    if not suffix:
        suffix = next((char for char in reversed(trailing) if char in ",;:"), "")
    return f"the link{suffix}"


def strip_url_references(text: str) -> str:
    text = re.sub(
        r"\b(?:sources?|references?|links?)\s*:\s*(?:https?://[^\s<>\"']+\s*)+[.!?。！？]?",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\[([^\]]+)\]\(\s*https?://[^\s)]+\s*\)", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"[\[(<]\s*https?://[^\s\])>]+[\])>]", " ", text, flags=re.IGNORECASE)
    text = URL_REFERENCE_RE.sub(_strip_url_reference_match, text)
    text = re.sub(r"\(\s*\)|\[\s*\]|\{\s*\}", " ", text)
    text = re.sub(r"\b(?:sources?|references?|links?)\s*:\s*(?=[.!?。！？]?(?:\s|$))", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+([,.;:!?。！？])", r"\1", text)
    if re.fullmatch(r"[\s,.;:!?。！？]+", text):
        return ""
    return text


def normalize_for_spoken_tts(text: str) -> str:
    return " ".join(strip_url_references(strip_thinking(text)).split())


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text))


SIMPLIFIED_TO_TRADITIONAL = str.maketrans(
    {
        "爱": "愛",
        "边": "邊",
        "变": "變",
        "别": "別",
        "长": "長",
        "车": "車",
        "东": "東",
        "发": "發",
        "复": "復",
        "个": "個",
        "关": "關",
        "过": "過",
        "国": "國",
        "还": "還",
        "后": "後",
        "话": "話",
        "会": "會",
        "几": "幾",
        "间": "間",
        "见": "見",
        "将": "將",
        "进": "進",
        "觉": "覺",
        "开": "開",
        "来": "來",
        "里": "裡",
        "们": "們",
        "么": "麼",
        "没": "沒",
        "门": "門",
        "吗": "嗎",
        "难": "難",
        "脑": "腦",
        "气": "氣",
        "让": "讓",
        "时": "時",
        "说": "說",
        "听": "聽",
        "为": "為",
        "问": "問",
        "无": "無",
        "现": "現",
        "学": "學",
        "样": "樣",
        "应": "應",
        "语": "語",
        "这": "這",
        "种": "種",
        "中": "中",
        "总": "總",
        "最": "最",
    }
)


def display_text(text: str) -> str:
    return str(text).translate(SIMPLIFIED_TO_TRADITIONAL)


def tts_language_for_text(text: str, fallback: str = "en") -> str:
    return "zh" if contains_cjk(text) else fallback


def make_english_tts_safe(text: str) -> str:
    text = normalize_for_spoken_tts(text)
    if not contains_cjk(text):
        return text
    print("[TTS_GUARD] Blocked CJK text from English Piper voice.", flush=True)
    return "I understood, but my English voice cannot speak Chinese characters. Please ask me to answer in English."


def normalize_command_text(text: str) -> str:
    words = re.findall(r"[a-z]+", text.lower())
    return " ".join(words)


def normalize_cjk_command_text(text: str) -> str:
    text = display_text(text)
    return "".join(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+", text))


def _close_word(word: str, targets: tuple[str, ...], threshold: float) -> bool:
    return any(difflib.SequenceMatcher(None, word, target).ratio() >= threshold for target in targets)


@functools.lru_cache(maxsize=1)
def _normalized_wake_targets() -> tuple[tuple[str, ...], tuple[str, ...]]:
    english = tuple(
        target
        for target in (normalize_command_text(phrase) for phrase in (*WAKE_PHRASES, *WAKE_ALIASES))
        if target
    )
    cjk = tuple(
        target
        for target in (normalize_cjk_command_text(phrase) for phrase in (*WAKE_PHRASES, *WAKE_ALIASES))
        if target
    )
    return english, cjk


def is_wake_request(text: str) -> bool:
    normalized = normalize_command_text(text)
    normalized_cjk = normalize_cjk_command_text(text)
    if not normalized and not normalized_cjk:
        return False

    wake_targets, wake_cjk_targets = _normalized_wake_targets()
    if any(target in normalized for target in wake_targets):
        return True

    if any(target in normalized_cjk for target in wake_cjk_targets):
        return True

    if not WAKE_FUZZY_MATCH:
        return False

    words = normalized.split()
    greetings = ("hello", "hey", "hi", "yellow")
    robot_words = ("robot", "robert", "robots", "robo")
    for index, word in enumerate(words):
        if not _close_word(word, greetings, 0.68):
            continue
        nearby_words = words[index + 1 : index + 4]
        if any(_close_word(candidate, robot_words, WAKE_FUZZY_THRESHOLD) for candidate in nearby_words):
            print(f"[WAKE_FUZZY] matched greeting/robot words in '{normalized}'", flush=True)
            return True
    return False


@functools.lru_cache(maxsize=1)
def _normalized_barge_in_targets() -> frozenset[str]:
    return frozenset(normalize_command_text(phrase) for phrase in BARGE_IN_PHRASES)


def is_barge_in_request(text: str) -> bool:
    return normalize_command_text(text) in _normalized_barge_in_targets()


@functools.lru_cache(maxsize=1)
def _normalized_vosk_wake_targets() -> frozenset[str]:
    return frozenset(normalize_command_text(phrase) for phrase in WAKE_VOSK_PHRASES)


def is_vosk_wake_request(text: str) -> bool:
    return normalize_command_text(text) in _normalized_vosk_wake_targets()


def is_sleep_request(text: str) -> bool:
    normalized = normalize_command_text(text)
    if normalized in {"bye", "goodbye", "good bye"}:
        return True
    return normalized.startswith(("goodbye ", "good bye "))


def is_exit_request(text: str) -> bool:
    return normalize_command_text(text) in {"exit", "quit", "stop"}


def language_display_name(language_code: str | None) -> str:
    return LANGUAGE_NAMES.get(language_code or "", language_code or "unknown")


class LCDMoodDisplay:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.proc: subprocess.Popen | None = None
        self.reader: threading.Thread | None = None
        self.ready = threading.Event()
        self.write_lock = threading.Lock()
        self.closed = False
        if not enabled:
            print("[LCD] Disabled.", flush=True)
            return
        if not LCD_SCRIPT.exists():
            print(f"[LCD_ERROR] Missing LCD script: {LCD_SCRIPT}", flush=True)
            self.enabled = False
            return
        print(f"[LCD] Using screen={LCD_SCREEN} script={LCD_SCRIPT.name}", flush=True)

        cmd = [
            sys.executable,
            str(LCD_SCRIPT),
            "--hide-window",
            "--option",
            LCD_COLLECTION,
            "--expression",
            LCD_EXPRESSION,
            "--mode",
            LCD_MODE,
            "--orientation",
            LCD_ORIENTATION,
            "--fps",
            LCD_FPS,
            "--backlight",
            LCD_BACKLIGHT,
        ]
        try:
            self.proc = subprocess.Popen(
                cmd,
                cwd=str(LCD_SCRIPT.parent),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
            self.reader = threading.Thread(target=self._read_output, name="lcd-output-reader", daemon=True)
            self.reader.start()
            if not self.ready.wait(timeout=8.0):
                if self.proc.poll() is None:
                    print("[LCD_ERROR] LCD display did not report ready.", flush=True)
                else:
                    print("[LCD_ERROR] LCD display process exited during startup.", flush=True)
                self.enabled = False
            elif self.proc.poll() is not None:
                print("[LCD_ERROR] LCD display process exited during startup.", flush=True)
                self.enabled = False
            else:
                print("[LCD] Mood display started.", flush=True)
        except Exception as e:
            print(f"[LCD_ERROR] Could not start display: {e}", flush=True)
            self.enabled = False

    def _read_output(self) -> None:
        if self.proc is None or self.proc.stdout is None:
            return
        for line in self.proc.stdout:
            line = line.rstrip()
            if line:
                print(f"[LCD_OUT] {line}", flush=True)
                if line == "[LCD_READY]":
                    self.ready.set()

    def send_display(
        self,
        expression: str | None = None,
        collection: str | None = None,
        text: str | None = None,
        sleep_fish: bool | None = None,
        meteor_shower: bool | None = None,
        listening_waves: bool | None = None,
        idea_icon: bool | None = None,
    ) -> None:
        if not self.enabled or self.proc is None or self.proc.poll() is not None:
            return
        payload = {}
        if expression:
            payload["expression"] = expression
        if collection:
            payload["collection"] = collection
        if text is not None:
            payload["text"] = text
        if sleep_fish is not None:
            payload["sleep_fish"] = sleep_fish
        if meteor_shower is not None:
            payload["meteor_shower"] = meteor_shower
        if listening_waves is not None:
            payload["listening_waves"] = listening_waves
        if idea_icon is not None:
            payload["idea_icon"] = idea_icon
        if not payload:
            return
        try:
            assert self.proc.stdin is not None
            with self.write_lock:
                self.proc.stdin.write(json.dumps(payload) + "\n")
                self.proc.stdin.flush()
            if expression:
                print(f"[LCD_MOOD] {expression}", flush=True)
            if text is not None:
                print(f"[LCD_TEXT_SEND] {text[:60]}", flush=True)
            if sleep_fish is not None:
                print(f"[LCD_SLEEP_FISH_SEND] {'on' if sleep_fish else 'off'}", flush=True)
            if meteor_shower is not None:
                print(f"[LCD_METEOR_SHOWER_SEND] {'on' if meteor_shower else 'off'}", flush=True)
            if listening_waves is not None:
                print(f"[LCD_LISTENING_WAVES_SEND] {'on' if listening_waves else 'off'}", flush=True)
            if idea_icon is not None:
                print(f"[LCD_IDEA_ICON_SEND] {'on' if idea_icon else 'off'}", flush=True)
        except Exception as e:
            print(f"[LCD_ERROR] Could not send display update: {e}", flush=True)
            self.enabled = False

    def set_mood(
        self,
        expression: str,
        collection: str | None = None,
        text: str | None = None,
        sleep_fish: bool | None = None,
        meteor_shower: bool | None = None,
        listening_waves: bool | None = None,
        idea_icon: bool | None = None,
    ) -> None:
        self.send_display(
            expression=expression,
            collection=collection,
            text=text,
            sleep_fish=sleep_fish,
            meteor_shower=meteor_shower,
            listening_waves=listening_waves,
            idea_icon=idea_icon,
        )

    def set_text(self, text: str) -> None:
        self.send_display(text=text)

    def set_sleep_fish(self, enabled: bool) -> None:
        self.send_display(sleep_fish=enabled)

    def set_meteor_shower(self, enabled: bool) -> None:
        self.send_display(meteor_shower=enabled)

    def set_listening_waves(self, enabled: bool) -> None:
        self.send_display(listening_waves=enabled)

    def set_idea_icon(self, enabled: bool) -> None:
        self.send_display(idea_icon=enabled)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        proc = self.proc
        if proc and proc.poll() is None:
            try:
                self.set_mood("sleepy", meteor_shower=False, listening_waves=False, idea_icon=False)
            except Exception:
                pass
            terminate_process(proc, timeout=3.0, process_group=True)
        if proc:
            for pipe in (proc.stdin, proc.stdout):
                if pipe is not None:
                    try:
                        pipe.close()
                    except Exception:
                        pass
        if self.reader and self.reader.is_alive() and self.reader is not threading.current_thread():
            self.reader.join(timeout=WORKER_JOIN_TIMEOUT_SECONDS)


class HeadMotion:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.px = None
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.lock = threading.Lock()
        if not enabled:
            print("[HEAD] Disabled.", flush=True)
            return
        if HEAD_LAZY_INIT and not HEAD_CENTER_ON_STARTUP:
            print("[HEAD] Motion ready; hardware init deferred to avoid startup movement.", flush=True)
            return
        if self._initialize() and HEAD_CENTER_ON_STARTUP:
            self.center()

    def _initialize(self) -> bool:
        if not self.enabled:
            return False
        if self.px is not None:
            return True
        try:
            from picarx import Picarx

            self.px = Picarx()
            print("[HEAD] Motion ready.", flush=True)
            return True
        except Exception as e:
            print(f"[HEAD_ERROR] Could not initialize head motion: {e}", flush=True)
            self.enabled = False
            return False

    def center(self) -> None:
        if not self.enabled or self.px is None:
            return
        with self.lock:
            self.px.set_cam_pan_angle(0)
            self.px.set_cam_tilt_angle(0)

    def start(self) -> None:
        if not self.enabled or not self._initialize():
            return
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        while not self.stop_event.is_set():
            pan = random.randint(-HEAD_PAN_LIMIT, HEAD_PAN_LIMIT)
            tilt = random.randint(HEAD_TILT_DOWN_LIMIT, HEAD_TILT_UP_LIMIT)
            with self.lock:
                assert self.px is not None
                self.px.set_cam_pan_angle(pan)
                self.px.set_cam_tilt_angle(tilt)
            delay = random.uniform(HEAD_MOVE_MIN_SECONDS, HEAD_MOVE_MAX_SECONDS)
            self.stop_event.wait(delay)

    def stop(self) -> None:
        if not self.enabled:
            return
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.5)
        if self.px is not None:
            self.center()

    def close(self) -> None:
        self.stop()


def normalize_mood(value: str | None) -> str | None:
    mood = str(value or "").strip().lower()
    return mood if mood in MOODS else None


def _contains_mood_keyword(text: str, keyword: str) -> bool:
    if contains_cjk(keyword):
        return keyword in text
    return re.search(rf"(?<![a-z]){re.escape(keyword)}(?![a-z])", text) is not None


def choose_mood(text: str) -> str:
    lowered = text.lower()
    keyword_moods = (
        ("love", ("love", "heart", "hug", "favorite", "thank you", "thanks", "愛", "喜歡", "謝謝", "感谢", "可愛", "可爱", "抱抱")),
        ("sad", ("sad", "sorry", "hurt", "lost", "cry", "miss", "bad news", "難過", "难过", "抱歉", "遺憾", "遗憾", "失去", "哭")),
        ("angry", ("angry", "mad", "annoying", "frustrating", "unfair", "grr", "生氣", "生气", "憤怒", "愤怒", "討厭", "讨厌", "不公平", "煩", "烦")),
        ("surprised", ("wow", "whoa", "surprise", "amazing", "no way", "哇", "驚訝", "惊讶", "沒想到", "没想到", "竟然")),
        ("sleepy", ("sleep", "sleepy", "tired", "bed", "nap", "yawn", "睡", "累", "晚安", "休息", "睏", "困")),
        ("thinking", ("think", "maybe", "because", "wonder", "question", "idea", "let me", "想想", "也許", "也许", "因為", "因为", "可能", "問題", "问题", "點子", "点子", "讓我", "让我")),
        ("excited", ("great", "awesome", "cool", "yay", "ready", "excellent", "太棒", "好耶", "酷", "成功", "準備好了", "准备好了")),
        ("happy", ("happy", "glad", "fun", "nice", "good news", "perfect", "開心", "开心", "高興", "高兴", "不錯", "不错", "有趣", "很好")),
    )
    scores = {
        mood: sum(_contains_mood_keyword(lowered, keyword) for keyword in keywords)
        for mood, keywords in keyword_moods
    }
    strongest = max(scores, key=scores.get)
    if scores[strongest]:
        return strongest
    if "?" in text or "？" in text:
        return "thinking"
    if "!" in text or "！" in text:
        return "excited"
    return "neutral"


def generate_thinking_sound(path: Path = THINKING_SOUND_FILE) -> Path:
    import math
    import struct

    try:
        if path.stat().st_size > 44:
            return path
    except OSError:
        pass

    sample_rate = 16000
    tones = []
    for _ in range(random.randint(4, 8)):
        freq = random.choice([440, 523, 587, 659, 740, 784, 880, 988, 1175, 1319])
        duration = random.uniform(0.035, 0.11)
        tones.append((freq, duration))
        if random.random() < 0.5:
            tones.append((0, random.uniform(0.015, 0.05)))

    frames = bytearray()
    for freq, duration in tones:
        samples = int(sample_rate * duration)
        wobble = random.uniform(8, 35)
        phase_shift = random.random() * math.pi
        for i in range(samples):
            if freq == 0:
                value = 0
            else:
                env = min(1.0, i / 120) * min(1.0, (samples - i) / 120)
                mod = 1.0 + 0.05 * math.sin(2 * math.pi * wobble * i / sample_rate + phase_shift)
                sample = math.sin(2 * math.pi * freq * mod * i / sample_rate)
                sample += 0.35 * math.sin(2 * math.pi * freq * 2.01 * i / sample_rate)
                value = int(8500 * env * sample)
            frames.extend(struct.pack("<h", value))

    with wave.Wave_write(str(path)) as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(frames)

    return path


def play_thinking_sound() -> None:
    path = generate_thinking_sound()
    try:
        proc = subprocess.Popen(
            ["aplay", "-q", "-D", PLAYBACK_DEVICE, str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        threading.Thread(target=proc.wait, name="thinking-sound-reaper", daemon=True).start()
    except Exception as e:
        print(f"[SOUND_ERROR] {e}", flush=True)


def generate_fast_wake_ack(path: Path = FAST_WAKE_ACK_FILE) -> bool:
    if not FAST_WAKE_ACK_ENABLED:
        return False
    try:
        if path.stat().st_size > 44:
            return True
    except OSError:
        pass
    try:
        subprocess.run(
            [
                "espeak",
                "-v",
                FAST_WAKE_ACK_VOICE,
                "-s",
                str(FAST_WAKE_ACK_SPEED),
                "-w",
                str(path),
                WELCOME,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=True,
        )
        return True
    except Exception as e:
        print(f"[WAKE_ACK_ERROR] Could not prepare fast acknowledgement: {e}", flush=True)
        return False


def play_fast_wake_ack(path: Path = FAST_WAKE_ACK_FILE) -> bool:
    if not FAST_WAKE_ACK_ENABLED or not path.exists():
        return False
    started = time.monotonic()
    last_error = "unknown playback error"
    for attempt in range(5):
        try:
            result = subprocess.run(
                ["aplay", "-q", "-D", PLAYBACK_DEVICE, str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                print(
                    f"[WAKE_ACK] Fast welcome completed in {time.monotonic() - started:.2f}s "
                    f"(attempt {attempt + 1}).",
                    flush=True,
                )
                return True
            last_error = result.stderr.strip().replace("\n", " ") or f"aplay exit {result.returncode}"
        except Exception as e:
            last_error = str(e)
        time.sleep(0.2 * (attempt + 1))
    print(f"[WAKE_ACK_ERROR] Playback failed after 5 attempts: {last_error}", flush=True)
    return False


class WhisperSTT:
    def __init__(
        self,
        label: str,
        backend: str,
        model_name: str,
        language: str | None,
        beam_size: int,
        vad_filter: bool,
        voice_start_rms: int,
        voice_end_rms: int,
        end_silence_seconds: float,
        max_record_seconds: float,
        hotwords: str = "",
    ) -> None:
        self.label = label
        self.backend = backend
        self.model_name = model_name
        self.language = language
        self.beam_size = beam_size
        self.vad_filter = vad_filter
        self.voice_start_rms = voice_start_rms
        self.voice_end_rms = voice_end_rms
        self.end_silence_seconds = end_silence_seconds
        self.max_record_seconds = max_record_seconds
        self.hotwords = hotwords.strip()
        self.model = None
        self.language_limiter: _AllowedLanguageModelProxy | None = None
        self.session: requests.Session | None = None
        self.openai_api_key = ""
        self.supports_without_timestamps = False
        self.supports_multilingual = False
        self.model_lock = threading.Lock()

        if self.backend == "local":
            try:
                from faster_whisper import WhisperModel
            except ImportError as e:
                raise RuntimeError(
                    "faster-whisper is not installed. Run: ./run_19b_whisper.sh "
                    "or install it in a venv with system site packages."
                ) from e

            print(f"[STT:{self.label}] Loading faster-whisper model: {self.model_name}")
            self.model = WhisperModel(
                self.model_name,
                device=WHISPER_DEVICE,
                compute_type=WHISPER_COMPUTE_TYPE,
                cpu_threads=WHISPER_CPU_THREADS,
                num_workers=WHISPER_NUM_WORKERS,
            )
            try:
                transcribe_parameters = inspect.signature(self.model.transcribe).parameters
                self.supports_without_timestamps = "without_timestamps" in transcribe_parameters
                self.supports_multilingual = "multilingual" in transcribe_parameters
            except (TypeError, ValueError):
                self.supports_without_timestamps = False
                self.supports_multilingual = False
            if (
                not self.language
                and WHISPER_ALLOWED_LANGUAGES
                and WHISPER_SHARED_ENCODER_LANGUAGE_DETECTION
                and self.supports_multilingual
                and self.model.model.is_multilingual
            ):
                self.language_limiter = _AllowedLanguageModelProxy(
                    self.model.model,
                    WHISPER_ALLOWED_LANGUAGES,
                )
                self.model.model = self.language_limiter
            print(
                f"[STT:{self.label}] threads={WHISPER_CPU_THREADS} workers={WHISPER_NUM_WORKERS} "
                f"shared_language_encoder={int(self.language_limiter is not None)} "
                f"hotwords={int(bool(self.hotwords))}",
                flush=True,
            )
        elif self.backend == "openai":
            self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
            if not self.openai_api_key:
                raise RuntimeError("OPENAI_API_KEY is required when STT_BACKEND=openai.")
            self.session = requests.Session()
            print(f"[STT:{self.label}] Using OpenAI transcription model: {self.model_name}")
        else:
            raise RuntimeError("Unknown STT_BACKEND. Use local or openai.")

        print(f"[MIC:{self.label}] Using ALSA input: {MIC_ALSA_DEVICE} at {MIC_SAMPLE_RATE} Hz")
        self.last_language: str | None = self.language
        self.last_language_probability: float | None = None
        self.listen_count = 0

    def close(self) -> None:
        if self.session is not None:
            self.session.close()
            self.session = None
        self.language_limiter = None
        self.model = None

    def _language_hint(self) -> str | None:
        if self.language or not WHISPER_FAST_LANGUAGE_HINT:
            return None
        if self.last_language not in WHISPER_ALLOWED_LANGUAGES:
            return None
        if self.last_language_probability is not None and self.last_language_probability < WHISPER_LANGUAGE_HINT_MIN_PROB:
            return None
        if WHISPER_LANGUAGE_AUTO_EVERY > 0 and self.listen_count % WHISPER_LANGUAGE_AUTO_EVERY == 0:
            return None
        return self.last_language

    def listen(
        self,
        max_wait_seconds: float | None = None,
        stop_event: threading.Event | None = None,
        quiet: bool = False,
    ) -> str:
        record_started = time.monotonic()
        wav_path = self._record_to_wav(max_wait_seconds=max_wait_seconds, stop_event=stop_event, quiet=quiet)
        record_seconds = time.monotonic() - record_started
        if not wav_path:
            if PERF_LOG and not quiet:
                print(f"[PERF] stt={self.label} record={record_seconds:.2f}s transcribe=0.00s no_audio", flush=True)
            return ""
        return self.transcribe_wav(wav_path, record_seconds=record_seconds, quiet=quiet)

    def transcribe_wav(self, wav_path: str, record_seconds: float = 0.0, quiet: bool = False, delete: bool = True) -> str:
        try:
            if not quiet:
                print(f"[STT:{self.label}] Transcribing...")
            transcribe_started = time.monotonic()
            if self.backend == "openai":
                text, mode, language_probability = self._transcribe_openai(wav_path)
            else:
                text, mode, language_probability = self._transcribe_local(wav_path)
            language_name = LANGUAGE_NAMES.get(self.last_language or "", self.last_language or "unknown")
            if not quiet and language_probability is None:
                print(f"[STT_LANG] {language_name} mode={mode}", flush=True)
            elif not quiet:
                print(f"[STT_LANG] {language_name} probability={language_probability:.2f} mode={mode}", flush=True)
            transcribe_seconds = time.monotonic() - transcribe_started
            if PERF_LOG and not quiet:
                print(
                    f"[PERF] record={record_seconds:.2f}s transcribe={transcribe_seconds:.2f}s "
                    f"stt={self.label} backend={self.backend} model={self.model_name} "
                    f"vad={int(self.vad_filter)} mode={mode}",
                    flush=True,
                )
            if text or not quiet:
                print(f"[YOU:{self.label}] {text}")
            self.listen_count += 1
            return text
        finally:
            if delete:
                try:
                    os.unlink(wav_path)
                except OSError:
                    pass

    def _transcribe_local(self, wav_path: str) -> tuple[str, str, float | None]:
        assert self.model is not None
        transcribe_kwargs = {
            "beam_size": self.beam_size,
            "best_of": WHISPER_BEST_OF,
            "temperature": WHISPER_TEMPERATURE,
            "vad_filter": self.vad_filter,
            "condition_on_previous_text": False,
            "word_timestamps": False,
        }
        if WHISPER_WITHOUT_TIMESTAMPS and self.supports_without_timestamps:
            transcribe_kwargs["without_timestamps"] = True
        if self.hotwords:
            transcribe_kwargs["hotwords"] = self.hotwords
        hint_language = self._language_hint()
        shared_detection = bool(
            not self.language
            and not hint_language
            and self.language_limiter is not None
        )
        if self.language:
            transcribe_kwargs["language"] = self.language
        elif hint_language:
            transcribe_kwargs["language"] = hint_language
        elif shared_detection:
            transcribe_kwargs["language"] = WHISPER_ALLOWED_LANGUAGES[0]
            transcribe_kwargs["multilingual"] = True
        detection = {}

        # faster-whisper exposes every language score but has no whitelist.
        # Older versions need the outer detector patched before tokenizer
        # creation. Newer versions filter the detector attached to the shared
        # transcription encoder, avoiding a duplicate encoder pass.
        limit_detection = (
            not self.language
            and not hint_language
            and bool(WHISPER_ALLOWED_LANGUAGES)
            and not shared_detection
        )
        with self.model_lock:
            original_detector = None
            had_instance_detector = False
            previous_instance_detector = None
            if shared_detection:
                self.language_limiter.reset_detection()
            if limit_detection:
                original_detector = self.model.detect_language
                had_instance_detector = "detect_language" in vars(self.model)
                previous_instance_detector = vars(self.model).get("detect_language")

                def detect_allowed_language(*args, **kwargs):
                    assert original_detector is not None
                    detected, detected_probability, all_probabilities = original_detector(*args, **kwargs)
                    probabilities = dict(all_probabilities)
                    selected = max(
                        WHISPER_ALLOWED_LANGUAGES,
                        key=lambda language: probabilities.get(language, 0.0),
                    )
                    selected_probability = probabilities.get(selected, 0.0)
                    detection.update(
                        detected=detected,
                        detected_probability=detected_probability,
                        selected=selected,
                        selected_probability=selected_probability,
                    )
                    if (
                        detected not in WHISPER_ALLOWED_LANGUAGES
                        and selected_probability < WHISPER_LANGUAGE_REJECT_MIN_PROB
                        and detected_probability - selected_probability >= WHISPER_LANGUAGE_REJECT_MARGIN
                    ):
                        detection["rejected"] = True
                        raise _RejectedTranscriptionLanguage
                    return selected, selected_probability, all_probabilities

                self.model.detect_language = detect_allowed_language
            try:
                try:
                    segments, info = self.model.transcribe(
                        wav_path,
                        **transcribe_kwargs,
                    )
                    segments = list(segments)
                    if shared_detection:
                        detection.update(self.language_limiter.last_detection)
                except _RejectedTranscriptionLanguage:
                    if shared_detection:
                        detection.update(self.language_limiter.last_detection)
                    segments = []
                    info = None
            finally:
                if limit_detection:
                    if had_instance_detector:
                        self.model.detect_language = previous_instance_detector
                    else:
                        del self.model.detect_language
        if detection.get("rejected"):
            self.last_language = None
            self.last_language_probability = detection["selected_probability"]
            print(
                f"[STT_LANG_REJECT] detected={detection['detected']}"
                f"({detection['detected_probability']:.2f}) "
                f"best_allowed={detection['selected']}({detection['selected_probability']:.2f})",
                flush=True,
            )
            return "", "rejected-outside-en-zh", detection["selected_probability"]

        if shared_detection and detection:
            detected_language = str(detection.get("selected") or "")
            language_probability = float(detection.get("selected_probability") or 0.0)
        else:
            detected_language = getattr(info, "language", None)
            language_probability = getattr(info, "language_probability", None)
        self.last_language = self.language or detected_language or hint_language
        if language_probability is not None:
            self.last_language_probability = language_probability
        elif not hint_language:
            self.last_language_probability = None
        mode = (
            "forced"
            if self.language
            else "hint"
            if hint_language
            else "shared-encoder-auto"
            if shared_detection
            else "limited-auto"
        )
        if detection and detection["detected"] != detection["selected"]:
            print(
                f"[STT_LANG_LIMIT] rejected={detection['detected']}({detection['detected_probability']:.2f}) "
                f"selected={detection['selected']}({detection['selected_probability']:.2f})",
                flush=True,
            )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return text, mode, language_probability

    def _transcribe_openai(self, wav_path: str) -> tuple[str, str, float | None]:
        assert self.session is not None
        data = {
            "model": self.model_name,
            "response_format": "json",
        }
        if self.language:
            data["language"] = self.language
        if OPENAI_TRANSCRIBE_PROMPT:
            data["prompt"] = OPENAI_TRANSCRIBE_PROMPT
        headers = {"Authorization": f"Bearer {self.openai_api_key}"}
        with open(wav_path, "rb") as audio_file:
            files = {"file": (Path(wav_path).name, audio_file, "audio/wav")}
            response = self.session.post(
                OPENAI_TRANSCRIBE_URL,
                headers=headers,
                data=data,
                files=files,
                timeout=OPENAI_TRANSCRIBE_TIMEOUT_SECONDS,
            )
        if response.status_code >= 400:
            detail = response.text.strip().replace("\n", " ")[:500]
            raise RuntimeError(f"OpenAI transcription failed ({response.status_code}): {detail}")
        payload = response.json()
        text = normalize_for_tts(str(payload.get("text", "")))
        self.last_language = self.language or ("zh" if contains_cjk(text) else "en" if text else None)
        self.last_language_probability = None
        mode = "forced" if self.language else "openai-auto"
        return text, mode, None

    def _record_to_wav(
        self,
        max_wait_seconds: float | None = None,
        stop_event: threading.Event | None = None,
        quiet: bool = False,
    ) -> str:
        chunks = bytearray()
        speaking = False
        speech_started_at: float | None = None
        last_voice_at: float | None = None
        noise_floor_rms: float | None = None
        start_blocks = 0
        listen_started_at = time.monotonic()
        chunk_bytes = max(1024, int(MIC_SAMPLE_RATE * 0.06) * 2)
        chunk_seconds = chunk_bytes / float(MIC_SAMPLE_RATE * 2)
        start_hold_blocks = max(1, int(round(VOICE_START_HOLD_SECONDS / chunk_seconds)))
        preroll_chunks = max(1, int(round(VOICE_PREROLL_SECONDS / chunk_seconds)))
        preroll: deque[bytes] = deque(maxlen=preroll_chunks)
        cancelled = False

        if not quiet:
            print("\nListening... (Ctrl+C to stop)", flush=True)
        proc = subprocess.Popen(
            [
                "arecord",
                "-q",
                "-D",
                MIC_ALSA_DEVICE,
                "-f",
                "S16_LE",
                "-r",
                str(MIC_SAMPLE_RATE),
                "-c",
                "1",
                "-t",
                "raw",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            while True:
                if stop_event and stop_event.is_set():
                    cancelled = True
                    break
                assert proc.stdout is not None
                data = proc.stdout.read(chunk_bytes)
                if not data:
                    stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
                    if stderr.strip():
                        print(f"[MIC_ERROR] {stderr.strip()}", flush=True)
                    break
                rms = pcm16_rms(data)
                now = time.monotonic()

                if not speaking:
                    preroll.append(data)
                    if not quiet:
                        print(f"[MIC] waiting... rms={rms}   ", end="\r", flush=True)
                    start_threshold = self.voice_start_rms
                    if VOICE_DYNAMIC_RMS and noise_floor_rms is not None:
                        start_threshold = max(
                            start_threshold,
                            int(noise_floor_rms * VOICE_START_RMS_MULTIPLIER),
                        )
                    if rms >= start_threshold:
                        start_blocks += 1
                    else:
                        start_blocks = 0
                        if noise_floor_rms is None:
                            noise_floor_rms = float(rms)
                        else:
                            noise_floor_rms = (
                                noise_floor_rms * (1.0 - VOICE_NOISE_FLOOR_ALPHA)
                                + float(rms) * VOICE_NOISE_FLOOR_ALPHA
                            )
                    if start_blocks >= start_hold_blocks:
                        speaking = True
                        speech_started_at = now
                        last_voice_at = now
                        chunks = bytearray()
                        for preroll_chunk in preroll:
                            chunks.extend(preroll_chunk)
                        if not quiet:
                            baseline = noise_floor_rms if noise_floor_rms is not None else 0.0
                            print(
                                f"[MIC] recording rms={rms} threshold={start_threshold} "
                                f"noise={baseline:.0f}",
                                flush=True,
                            )
                        continue
                    elif max_wait_seconds is not None and now - listen_started_at >= max_wait_seconds:
                        if not quiet:
                            print("[MIC] listen timeout.     ", flush=True)
                        break
                    continue

                if speaking:
                    chunks.extend(data)
                    end_threshold = self.voice_end_rms
                    if VOICE_DYNAMIC_RMS and noise_floor_rms is not None:
                        end_threshold = max(
                            end_threshold,
                            int(noise_floor_rms * VOICE_END_RMS_MULTIPLIER),
                        )
                    if rms >= end_threshold:
                        last_voice_at = now
                    elif last_voice_at and now - last_voice_at >= self.end_silence_seconds:
                        if speech_started_at and now - speech_started_at < VOICE_MIN_RECORD_SECONDS:
                            chunks.clear()
                            speaking = False
                            speech_started_at = None
                            last_voice_at = None
                            start_blocks = 0
                            preroll.clear()
                            if not quiet:
                                print("[MIC] ignored short noise.  ", flush=True)
                            continue
                        break

                if speech_started_at and now - speech_started_at >= self.max_record_seconds:
                    break
        finally:
            terminate_process(proc)

        if cancelled or not chunks:
            return ""
        return self._write_wav(chunks)

    def _write_wav(self, audio: bytes | bytearray) -> str:
        fd, wav_path = tempfile.mkstemp(prefix="whisper_input_", suffix=".wav")
        os.close(fd)
        with wave.Wave_write(wav_path) as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(MIC_SAMPLE_RATE)
            wav.writeframes(audio)
        return wav_path


class VoskWakeListener:
    def __init__(self, model_path: Path = WAKE_VOSK_MODEL_PATH) -> None:
        if not model_path.exists():
            raise RuntimeError(f"Vosk wake model not found: {model_path}")
        try:
            from vosk import KaldiRecognizer, Model, SetLogLevel
        except ImportError as e:
            raise RuntimeError("Vosk is not installed for the wake recognizer.") from e

        SetLogLevel(-1)
        started = time.monotonic()
        self.model = Model(str(model_path))
        self.recognizer_class = KaldiRecognizer
        self.grammar = list(dict.fromkeys((*WAKE_VOSK_PHRASES, *WAKE_VOSK_REJECT_PHRASES, "[unk]")))
        self.stop_event = threading.Event()
        self.detect_queue: "queue.Queue[str]" = queue.Queue(maxsize=1)
        self.thread: threading.Thread | None = None
        self.proc: subprocess.Popen | None = None
        self.proc_lock = threading.Lock()
        print(
            f"[WAKE_VOSK] Loaded {model_path.name} in {time.monotonic() - started:.2f}s "
            f"with {len(WAKE_VOSK_PHRASES)} wake phrases.",
            flush=True,
        )

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, name="vosk-wake-listener", daemon=True)
        self.thread.start()
        print("[WAKE_VOSK] Streaming wake listener started.", flush=True)

    def stop(self, clear_queue: bool = True) -> None:
        self.stop_event.set()
        with self.proc_lock:
            proc = self.proc
        if proc and proc.poll() is None:
            proc.terminate()
        if self.thread and self.thread.is_alive() and self.thread is not threading.current_thread():
            self.thread.join(timeout=1.5)
        if self.thread and self.thread.is_alive():
            terminate_process(proc)
            if self.thread is not threading.current_thread():
                self.thread.join(timeout=WORKER_JOIN_TIMEOUT_SECONDS)
        if clear_queue:
            self._clear_queue()

    def listen(
        self,
        max_wait_seconds: float | None = None,
        stop_event: threading.Event | None = None,
        quiet: bool = False,
    ) -> str:
        self.start()
        deadline = time.monotonic() + max_wait_seconds if max_wait_seconds is not None else None
        while not self.stop_event.is_set():
            if stop_event and stop_event.is_set():
                return ""
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return ""
                timeout = min(0.2, remaining)
            else:
                timeout = 0.2
            try:
                return self.detect_queue.get(timeout=timeout)
            except queue.Empty:
                continue
        return ""

    def _run(self) -> None:
        while not self.stop_event.is_set():
            try:
                self._record_session()
            except Exception as e:
                if not self.stop_event.is_set():
                    print(f"[WAKE_VOSK_ERROR] {e}", flush=True)
            if not self.stop_event.wait(WAKE_VOSK_RESTART_SECONDS):
                continue

    def _record_session(self) -> None:
        recognizer = self.recognizer_class(self.model, MIC_SAMPLE_RATE, json.dumps(self.grammar))
        block_bytes = max(640, int(MIC_SAMPLE_RATE * WAKE_VOSK_BLOCK_MS / 1000) * 2)
        proc = subprocess.Popen(
            [
                "arecord",
                "-q",
                "-D",
                MIC_ALSA_DEVICE,
                "-f",
                "S16_LE",
                "-r",
                str(MIC_SAMPLE_RATE),
                "-c",
                "1",
                "-t",
                "raw",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        with self.proc_lock:
            self.proc = proc
        last_candidate = ""
        stable_blocks = 0
        recognition_cpu_seconds = 0.0
        try:
            while not self.stop_event.is_set():
                assert proc.stdout is not None
                data = proc.stdout.read(block_bytes)
                if not data:
                    stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
                    if stderr.strip() and not self.stop_event.is_set():
                        print(f"[MIC_ERROR] {stderr.strip()}", flush=True)
                    return

                recognize_started = time.monotonic()
                is_final = recognizer.AcceptWaveform(data)
                payload = json.loads(recognizer.Result() if is_final else recognizer.PartialResult())
                recognition_cpu_seconds += time.monotonic() - recognize_started
                candidate = str(payload.get("text") or payload.get("partial") or "").strip().lower()
                if not candidate:
                    continue
                if candidate == last_candidate:
                    stable_blocks += 1
                else:
                    last_candidate = candidate
                    stable_blocks = 1
                if not is_vosk_wake_request(candidate):
                    continue
                if not is_final and stable_blocks < max(1, WAKE_VOSK_PARTIAL_STABILITY_BLOCKS):
                    continue

                while self.detect_queue.full():
                    try:
                        self.detect_queue.get_nowait()
                    except queue.Empty:
                        break
                self.detect_queue.put(candidate)
                print(
                    f"[WAKE_VOSK] detected='{candidate}' partial_blocks={stable_blocks} "
                    f"recognition_cpu={recognition_cpu_seconds:.3f}s",
                    flush=True,
                )
                return
        finally:
            terminate_process(proc)
            with self.proc_lock:
                if self.proc is proc:
                    self.proc = None

    def _clear_queue(self) -> None:
        while True:
            try:
                self.detect_queue.get_nowait()
            except queue.Empty:
                return


class ContinuousWakeListener:
    def __init__(self, stt: WhisperSTT) -> None:
        self.stt = stt
        self.stop_event = threading.Event()
        self.audio_queue: "queue.Queue[tuple[str, float, float]]" = queue.Queue(maxsize=max(1, WAKE_CONTINUOUS_QUEUE_SIZE))
        self.thread: threading.Thread | None = None
        self.proc: subprocess.Popen | None = None
        self.proc_lock = threading.Lock()

    def start(self) -> None:
        if not WAKE_CONTINUOUS_RECORDING:
            return
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        print("[WAKE_REC] Continuous wake recording started.", flush=True)

    def stop(self, clear_queue: bool = True) -> None:
        self.stop_event.set()
        with self.proc_lock:
            proc = self.proc
        if proc and proc.poll() is None:
            proc.terminate()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.5)
        if self.thread and self.thread.is_alive():
            terminate_process(proc)
            self.thread.join(timeout=WORKER_JOIN_TIMEOUT_SECONDS)
        if clear_queue:
            self._clear_queue()

    def listen(
        self,
        max_wait_seconds: float | None = None,
        stop_event: threading.Event | None = None,
        quiet: bool = False,
    ) -> str:
        if not WAKE_CONTINUOUS_RECORDING:
            return self.stt.listen(max_wait_seconds=max_wait_seconds, stop_event=stop_event, quiet=quiet)
        self.start()
        deadline = time.monotonic() + max_wait_seconds if max_wait_seconds is not None else None
        while not self.stop_event.is_set():
            if stop_event and stop_event.is_set():
                return ""
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return ""
                queue_timeout = min(0.25, remaining)
            else:
                queue_timeout = 0.25
            candidate = self._get_latest_candidate(timeout=queue_timeout)
            if candidate is None:
                continue
            wav_path, record_seconds, queued_at = candidate
            age_seconds = time.monotonic() - queued_at
            if age_seconds > WAKE_CANDIDATE_MAX_AGE_SECONDS:
                print(f"[WAKE_REC] Dropped stale wake candidate age={age_seconds:.1f}s.", flush=True)
                try:
                    os.unlink(wav_path)
                except OSError:
                    pass
                continue
            try:
                return self.stt.transcribe_wav(wav_path, record_seconds=record_seconds, quiet=quiet)
            except Exception as e:
                print(f"[WAKE_REC_ERROR] Transcription failed: {e}", flush=True)
        return ""

    def _get_latest_candidate(self, timeout: float) -> tuple[str, float, float] | None:
        try:
            latest = self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

        dropped = 0
        while True:
            try:
                newer = self.audio_queue.get_nowait()
            except queue.Empty:
                break
            old_path, _, _ = latest
            try:
                os.unlink(old_path)
            except OSError:
                pass
            latest = newer
            dropped += 1
        if dropped:
            print(f"[WAKE_REC] Skipped {dropped} stale queued candidate(s); using latest.", flush=True)
        return latest

    def _run(self) -> None:
        while not self.stop_event.is_set():
            try:
                self._record_session()
            except Exception as e:
                if not self.stop_event.is_set():
                    print(f"[WAKE_REC_ERROR] Recorder failed: {e}", flush=True)
            if not self.stop_event.is_set():
                time.sleep(WAKE_RECORDER_RESTART_SECONDS)

    def _record_session(self) -> None:
        chunk_bytes = max(1024, int(MIC_SAMPLE_RATE * 0.06) * 2)
        chunk_seconds = chunk_bytes / float(MIC_SAMPLE_RATE * 2)
        preroll_chunks = max(1, int(WAKE_PREROLL_SECONDS / chunk_seconds))
        preroll: deque[bytes] = deque(maxlen=preroll_chunks)
        chunks = bytearray()
        speaking = False
        speech_started_at: float | None = None
        last_voice_at: float | None = None
        noise_floor_rms: float | None = None

        proc = subprocess.Popen(
            [
                "arecord",
                "-q",
                "-D",
                MIC_ALSA_DEVICE,
                "-f",
                "S16_LE",
                "-r",
                str(MIC_SAMPLE_RATE),
                "-c",
                "1",
                "-t",
                "raw",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        with self.proc_lock:
            self.proc = proc
        try:
            while not self.stop_event.is_set():
                assert proc.stdout is not None
                data = proc.stdout.read(chunk_bytes)
                if not data:
                    stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
                    if stderr.strip() and not self.stop_event.is_set():
                        print(f"[MIC_ERROR] {stderr.strip()}", flush=True)
                    break

                rms = pcm16_rms(data)
                now = time.monotonic()

                if not speaking:
                    preroll.append(data)
                    start_threshold = self.stt.voice_start_rms
                    if WAKE_DYNAMIC_RMS and noise_floor_rms is not None:
                        baseline = noise_floor_rms
                        start_threshold = max(start_threshold, int(baseline * WAKE_START_RMS_MULTIPLIER))
                    if rms >= start_threshold:
                        speaking = True
                        speech_started_at = now
                        last_voice_at = now
                        chunks = bytearray()
                        for preroll_chunk in preroll:
                            chunks.extend(preroll_chunk)
                        baseline = noise_floor_rms if noise_floor_rms is not None else 0.0
                        print(
                            f"[WAKE_REC] recording wake candidate rms={rms} "
                            f"threshold={start_threshold} noise={baseline:.0f}",
                            flush=True,
                        )
                    else:
                        if noise_floor_rms is None:
                            noise_floor_rms = float(rms)
                        else:
                            noise_floor_rms = (
                                noise_floor_rms * (1.0 - WAKE_NOISE_FLOOR_ALPHA)
                                + float(rms) * WAKE_NOISE_FLOOR_ALPHA
                            )
                    continue

                chunks.extend(data)
                baseline = noise_floor_rms if noise_floor_rms is not None else self.stt.voice_end_rms
                end_threshold = self.stt.voice_end_rms
                if WAKE_DYNAMIC_RMS:
                    end_threshold = max(end_threshold, int(baseline * WAKE_END_RMS_MULTIPLIER))
                if rms >= end_threshold:
                    last_voice_at = now
                elif last_voice_at and now - last_voice_at >= self.stt.end_silence_seconds:
                    self._queue_wake_candidate(chunks)
                    chunks = bytearray()
                    speaking = False
                    speech_started_at = None
                    last_voice_at = None
                    preroll.clear()
                    continue

                if speech_started_at and now - speech_started_at >= self.stt.max_record_seconds:
                    self._queue_wake_candidate(chunks)
                    chunks = bytearray()
                    speaking = False
                    speech_started_at = None
                    last_voice_at = None
                    preroll.clear()
        finally:
            terminate_process(proc)
            with self.proc_lock:
                if self.proc is proc:
                    self.proc = None

    def _queue_wake_candidate(self, audio: bytes | bytearray) -> None:
        if not audio or self.stop_event.is_set():
            return
        record_seconds = len(audio) / float(MIC_SAMPLE_RATE * 2)
        if record_seconds < WAKE_MIN_RECORD_SECONDS:
            print(f"[WAKE_REC] Dropped too-short wake candidate ({record_seconds:.2f}s).", flush=True)
            return
        wav_path = self.stt._write_wav(audio)
        while self.audio_queue.full():
            try:
                old_path, _, _ = self.audio_queue.get_nowait()
                os.unlink(old_path)
                print("[WAKE_REC] Dropped older wake candidate.", flush=True)
            except queue.Empty:
                break
            except OSError:
                pass
        self.audio_queue.put((wav_path, record_seconds, time.monotonic()))
        print(f"[WAKE_REC] queued wake candidate ({record_seconds:.2f}s)", flush=True)

    def _clear_queue(self) -> None:
        while True:
            try:
                wav_path, _, _ = self.audio_queue.get_nowait()
            except queue.Empty:
                return
            try:
                os.unlink(wav_path)
            except OSError:
                pass


class TTSProcess:
    def __init__(self, head_motion: HeadMotion | None = None, lcd_display: LCDMoodDisplay | None = None) -> None:
        self.head_motion = head_motion
        self.lcd_display = lcd_display
        self.sync_events: "queue.Queue[str]" = queue.Queue(maxsize=TTS_EVENT_QUEUE_SIZE)
        self.reset_events: "queue.Queue[str]" = queue.Queue(maxsize=TTS_EVENT_QUEUE_SIZE)
        self.display_events: "queue.Queue[tuple[str, str | bool] | None]" = queue.Queue(
            maxsize=TTS_EVENT_QUEUE_SIZE
        )
        self.pending_speech_line = ""
        self.last_done_at: float | None = None
        self.ready = threading.Event()
        self.send_lock = threading.Lock()
        self.worker = Path(__file__).with_name("tts_piper_stream_worker_19v2.py")
        self.worker_temp_dir = Path(tempfile.mkdtemp(prefix="picarx_tts_v2_"))
        self.proc: subprocess.Popen[str] | None = None
        self.reader: threading.Thread | None = None
        self.closed = False
        self.suspended = False
        self._start_worker()
        self.display_thread = threading.Thread(target=self._process_display_events, daemon=True)
        self.display_thread.start()

    def _start_worker(self) -> None:
        self.ready.clear()
        self._cleanup_worker_temp_files()
        self.worker_temp_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        worker_env = os.environ.copy()
        worker_env["TTS_TEMP_DIR"] = str(self.worker_temp_dir)
        self.proc = subprocess.Popen(
            [sys.executable, "-u", str(self.worker)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
            env=worker_env,
        )
        self.reader = threading.Thread(target=self._read_output, args=(self.proc,), daemon=True)
        self.reader.start()

    def _terminate_worker(self, timeout: float = 1.5) -> None:
        proc = self.proc
        if proc is None or proc.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            return
        except Exception as e:
            print(f"[TTS_INTERRUPT_ERROR] terminate failed: {e}", flush=True)
            proc.terminate()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                proc.kill()
            proc.wait(timeout=timeout)

    def _drain_sync_events(self) -> None:
        while True:
            try:
                self.sync_events.get_nowait()
            except queue.Empty:
                return

    def _drain_reset_events(self) -> None:
        while True:
            try:
                self.reset_events.get_nowait()
            except queue.Empty:
                return

    def _cleanup_worker_temp_files(self) -> None:
        if not self.worker_temp_dir.exists():
            return
        for path in self.worker_temp_dir.iterdir():
            try:
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path)
                else:
                    path.unlink()
            except OSError:
                pass

    def _queue_display_event(self, event: str, value: str | bool) -> None:
        if not self.lcd_display or self.closed:
            return
        item = (event, value)
        try:
            self.display_events.put_nowait(item)
        except queue.Full:
            try:
                self.display_events.get_nowait()
            except queue.Empty:
                pass
            try:
                self.display_events.put_nowait(item)
            except queue.Full:
                pass

    def _process_display_events(self) -> None:
        while True:
            item = self.display_events.get()
            if item is None:
                return
            if not self.lcd_display:
                continue
            updates = {item[0]: item[1]}
            should_stop = False
            while True:
                try:
                    newer = self.display_events.get_nowait()
                except queue.Empty:
                    break
                if newer is None:
                    should_stop = True
                    break
                updates[newer[0]] = newer[1]
            self.lcd_display.send_display(
                text=display_text(str(updates["text"])) if "text" in updates else None,
                meteor_shower=bool(updates["meteor_shower"]) if "meteor_shower" in updates else None,
                listening_waves=bool(updates["listening_waves"]) if "listening_waves" in updates else None,
                idea_icon=bool(updates["idea_icon"]) if "idea_icon" in updates else None,
            )
            if should_stop:
                return

    def _read_output(self, proc: subprocess.Popen[str]) -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip()
            print(line, flush=True)
            if line == "[TTS_READY]":
                self.ready.set()
            if line.startswith("[TTS_START] "):
                parts = line.split(" ", 2)
                self.pending_speech_line = parts[2] if len(parts) >= 3 else ""
            if line.startswith("[TTS_START_HIDDEN] "):
                self.pending_speech_line = ""
            if line == "[TTS_PLAY_START]" and self.head_motion:
                self.head_motion.start()
            if line == "[TTS_PLAY_START]" and self.lcd_display:
                if self.pending_speech_line:
                    self._queue_display_event("text", self.pending_speech_line)
                self._queue_display_event("listening_waves", False)
                self._queue_display_event("meteor_shower", True)
            if (line == "[TTS_DONE]" or line.startswith("[TTS_ERROR]")) and self.lcd_display:
                self._queue_display_event("meteor_shower", False)
            if line.startswith("[TTS_SYNC_DONE] "):
                sync_id = line.split(" ", 1)[1]
                try:
                    self.sync_events.put_nowait(sync_id)
                except queue.Full:
                    self._drain_sync_events()
                    self.sync_events.put_nowait(sync_id)
            if line.startswith("[TTS_RESET_DONE] "):
                reset_id = line.split(" ", 1)[1]
                try:
                    self.reset_events.put_nowait(reset_id)
                except queue.Full:
                    self._drain_reset_events()
                    self.reset_events.put_nowait(reset_id)

    def send(self, msg: dict) -> bool:
        is_speech = msg.get("command") in {"say", "beep"}
        if is_speech and self.suspended:
            return False
        if self.proc is None or self.proc.poll() is not None:
            if self.closed or not self.restart():
                raise RuntimeError("TTS worker process exited")
        assert self.proc.stdin is not None
        with self.send_lock:
            if is_speech and self.suspended:
                return False
            self.proc.stdin.write(json.dumps(msg) + "\n")
            self.proc.stdin.flush()
        return True

    def say(self, text: str, language: str | None = None, show_on_lcd: bool = True) -> None:
        text = normalize_for_spoken_tts(text)
        if text:
            msg = {"command": "say", "text": text, "display": show_on_lcd}
            if language:
                msg["language"] = language
            self.send(msg)

    def inter_sentence_beep(self) -> None:
        self.send({"command": "beep"})

    def restart(self) -> bool:
        if self.closed:
            return False
        with self.send_lock:
            self.suspended = False
            if self.proc is not None and self.proc.poll() is None:
                return True
            old_reader = self.reader
            if old_reader and old_reader.is_alive() and old_reader is not threading.current_thread():
                old_reader.join(timeout=WORKER_JOIN_TIMEOUT_SECONDS)
            self._drain_sync_events()
            self._drain_reset_events()
            self.pending_speech_line = ""
            self._start_worker()
        return True

    def _wait_for_reset(self, reset_id: str, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            try:
                event_id = self.reset_events.get(timeout=remaining)
            except queue.Empty:
                return False
            if event_id == reset_id:
                return True

    def interrupt(self, restart: bool = True) -> None:
        print("[TTS_INTERRUPT] stopping current speech", flush=True)
        started = time.monotonic()
        reset_id = str(time.monotonic_ns())
        proc = self.proc
        soft_interrupt_sent = False

        with self.send_lock:
            self.suspended = True
            if proc is not None and proc.poll() is None and proc.stdin is not None:
                try:
                    os.kill(proc.pid, signal.SIGUSR1)
                    proc.stdin.write(json.dumps({"command": "reset", "id": reset_id}) + "\n")
                    proc.stdin.flush()
                    soft_interrupt_sent = True
                except (BrokenPipeError, OSError):
                    soft_interrupt_sent = False

        worker_preserved = soft_interrupt_sent and self._wait_for_reset(
            reset_id,
            TTS_SOFT_INTERRUPT_TIMEOUT_SECONDS,
        )
        if not worker_preserved:
            with self.send_lock:
                old_reader = self.reader
                if proc is not None and self.proc is proc and proc.poll() is None:
                    self._terminate_worker(timeout=TTS_HARD_INTERRUPT_TIMEOUT_SECONDS)
                if old_reader and old_reader.is_alive() and old_reader is not threading.current_thread():
                    old_reader.join(timeout=WORKER_JOIN_TIMEOUT_SECONDS)
                self.ready.clear()
                self._cleanup_worker_temp_files()
                self._drain_sync_events()
                self._drain_reset_events()
                self.pending_speech_line = ""
                if restart and not self.closed:
                    self._start_worker()
            fallback_action = "worker restarted" if restart else "restart deferred"
            print(f"[TTS_INTERRUPT_FALLBACK] worker stopped; {fallback_action}", flush=True)
        else:
            self._drain_sync_events()
            self.pending_speech_line = ""
            print("[TTS_INTERRUPT_FAST] playback stopped; voice model preserved", flush=True)

        if restart:
            with self.send_lock:
                self.suspended = False
        self.last_done_at = time.monotonic()
        if PERF_LOG:
            print(
                f"[PERF] tts_interrupt={self.last_done_at - started:.3f}s "
                f"worker_preserved={int(worker_preserved)}",
                flush=True,
            )
        if self.head_motion:
            self.head_motion.stop()
        if self.lcd_display:
            self._queue_display_event("meteor_shower", False)

    def wait_until_done(
        self,
        timeout: float | None = None,
        interrupt_event: threading.Event | None = None,
    ) -> bool:
        if timeout is None:
            timeout = TTS_SYNC_TIMEOUT_SECONDS
        sync_id = str(time.monotonic_ns())
        self.send({"command": "sync", "id": sync_id})
        try:
            deadline = time.monotonic() + timeout
            while True:
                if interrupt_event and interrupt_event.is_set():
                    self.last_done_at = time.monotonic()
                    return False
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    print(f"[TTS_TIMEOUT] TTS worker did not sync within {timeout:g}s", flush=True)
                    self.last_done_at = time.monotonic()
                    return False
                try:
                    poll_seconds = BARGE_IN_INTERRUPT_POLL_SECONDS if interrupt_event else 1.0
                    event_id = self.sync_events.get(timeout=min(poll_seconds, remaining))
                except queue.Empty:
                    continue
                if event_id == sync_id:
                    self.last_done_at = time.monotonic()
                    return True
        finally:
            if self.head_motion:
                self.head_motion.stop()
            if self.lcd_display:
                self._queue_display_event("meteor_shower", False)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            if self.proc and self.proc.poll() is None:
                try:
                    self.send({"command": "quit"})
                except Exception:
                    pass
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._terminate_worker()
        finally:
            if self.head_motion:
                self.head_motion.stop()
            if self.lcd_display:
                self.lcd_display.set_meteor_shower(False)
            while True:
                try:
                    self.display_events.put_nowait(None)
                    break
                except queue.Full:
                    try:
                        self.display_events.get_nowait()
                    except queue.Empty:
                        break
            if self.display_thread.is_alive():
                self.display_thread.join(timeout=WORKER_JOIN_TIMEOUT_SECONDS)
            if self.reader and self.reader.is_alive() and self.reader is not threading.current_thread():
                self.reader.join(timeout=WORKER_JOIN_TIMEOUT_SECONDS)
            self._cleanup_worker_temp_files()
            shutil.rmtree(self.worker_temp_dir, ignore_errors=True)


class ThinkingCue:
    def __init__(
        self,
        tts: TTSProcess,
        lcd: LCDMoodDisplay,
        delay_seconds: float,
        language: str = "en",
    ) -> None:
        self.tts = tts
        self.lcd = lcd
        self.delay_seconds = delay_seconds
        self.language = "zh" if language == "zh" else "en"
        self.phrases = THINKING_FILLERS_ZH if self.language == "zh" else THINKING_FILLERS_EN
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        self.lcd.set_idea_icon(True)
        if not THINKING_FILLER_ENABLED or not self.phrases:
            return
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        if self.stop_event.wait(self.delay_seconds):
            return
        phrase = random.choice(self.phrases)
        print(f"[THINKING_FILLER] lang={self.language} {phrase}", flush=True)
        try:
            self.tts.say(phrase, language=self.language, show_on_lcd=False)
        except Exception as e:
            print(f"[THINKING_FILLER_ERROR] {e}", flush=True)

    def stop(self) -> None:
        self.stop_event.set()
        self.lcd.set_idea_icon(False)
        if self.thread and self.thread.is_alive() and self.thread is not threading.current_thread():
            self.thread.join(timeout=WORKER_JOIN_TIMEOUT_SECONDS)


class BargeInMonitor:
    def __init__(
        self,
        wake_listener,
        stt: WhisperSTT,
        tts: TTSProcess,
        lcd: LCDMoodDisplay,
    ) -> None:
        self.wake_listener = wake_listener
        self.stt = stt
        self.tts = tts
        self.lcd = lcd
        self.stop_event = threading.Event()
        self.capture_stop_event = threading.Event()
        self.interrupt_event = threading.Event()
        self.followup_capture_started = threading.Event()
        self.followup_ready = threading.Event()
        self.followup_text = ""
        self.last_handoff_seconds: float | None = None
        self.last_followup_seconds: float | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        self.stop()
        if self.thread and self.thread.is_alive():
            self.interrupt_event.clear()
            print("[BARGE_IN] Previous listener is still stopping; barge-in skipped for this response.", flush=True)
            return
        self.stop_event.clear()
        self.capture_stop_event.clear()
        self.interrupt_event.clear()
        self.followup_capture_started.clear()
        self.followup_ready.clear()
        self.followup_text = ""
        self.last_handoff_seconds = None
        self.last_followup_seconds = None
        if not BARGE_IN_ENABLED:
            return
        self.thread = threading.Thread(target=self._run, name="barge-in-followup", daemon=True)
        self.thread.start()

    def _run(self) -> None:
        while not self.stop_event.is_set() and not self.interrupt_event.is_set():
            try:
                text = self.wake_listener.listen(
                    max_wait_seconds=BARGE_IN_LISTEN_TIMEOUT_SECONDS,
                    stop_event=self.stop_event,
                    quiet=True,
                )
            except Exception as e:
                if not self.stop_event.is_set():
                    print(f"[BARGE_IN_ERROR] {e}", flush=True)
                return
            if self.stop_event.is_set():
                return
            if not text:
                continue
            if is_barge_in_request(text):
                triggered_at = time.monotonic()
                print(f"[BARGE_IN] Wake phrase heard during response: {text}", flush=True)
                self.interrupt_event.set()
                self.tts.interrupt(restart=False)
                self.lcd.send_display(
                    text="Now listening...",
                    meteor_shower=False,
                    listening_waves=True,
                    idea_icon=False,
                    sleep_fish=False,
                )
                if not BARGE_IN_FOLLOWUP_ENABLED:
                    self.followup_ready.set()
                    return

                self.wake_listener.stop()
                print("[BARGE_IN_FOLLOWUP] Listening for the new question.", flush=True)
                try:
                    self.last_handoff_seconds = time.monotonic() - triggered_at
                    if PERF_LOG:
                        print(
                            f"[PERF] barge_handoff={self.last_handoff_seconds:.3f}s",
                            flush=True,
                        )
                    self.followup_capture_started.set()
                    self.followup_text = self.stt.listen(
                        max_wait_seconds=BARGE_IN_FOLLOWUP_START_TIMEOUT_SECONDS,
                        stop_event=self.capture_stop_event,
                    )
                    if self.followup_text:
                        print(f"[BARGE_IN_FOLLOWUP] {self.followup_text}", flush=True)
                    else:
                        print("[BARGE_IN_FOLLOWUP] No new question recognized.", flush=True)
                except Exception as e:
                    if not self.capture_stop_event.is_set():
                        print(f"[BARGE_IN_FOLLOWUP_ERROR] {e}", flush=True)
                finally:
                    self.last_followup_seconds = time.monotonic() - triggered_at
                    if PERF_LOG:
                        print(
                            f"[PERF] barge_followup={self.last_followup_seconds:.2f}s",
                            flush=True,
                        )
                    self.followup_ready.set()
                return
            print(f"[BARGE_IN] Ignoring non-wake speech during response: {text}", flush=True)

    def interrupted(self) -> bool:
        return self.interrupt_event.is_set()

    def wait_for_followup(self) -> str:
        if not BARGE_IN_FOLLOWUP_ENABLED:
            return ""

        deadline = time.monotonic() + BARGE_IN_FOLLOWUP_TOTAL_TIMEOUT_SECONDS
        if not self.interrupt_event.wait(BARGE_IN_FOLLOWUP_TOTAL_TIMEOUT_SECONDS):
            return ""

        remaining = max(0.0, deadline - time.monotonic())
        if not self.followup_ready.wait(remaining):
            print("[BARGE_IN_FOLLOWUP] Timed out waiting for transcription.", flush=True)
            self.capture_stop_event.set()
            return ""
        return self.followup_text

    def stop(self) -> None:
        self.stop_event.set()
        self.capture_stop_event.set()
        self.wake_listener.stop()
        if self.thread and self.thread.is_alive() and self.thread is not threading.current_thread():
            self.thread.join(timeout=1.5)


class OllamaStreamChat:
    def __init__(self, model: str, url: str, instructions: str, max_messages: int = 20) -> None:
        self.display_name = "ollama"
        self.model = model
        self.url = url
        self.max_messages = max_messages
        self.session = requests.Session()
        self.messages = [{"role": "system", "content": instructions}]
        self.response_lock = threading.Lock()
        self.active_response: requests.Response | None = None
        self.warmup_thread: threading.Thread | None = None
        if OLLAMA_WARMUP:
            self.warmup_thread = threading.Thread(target=self._warmup, name="ollama-warmup", daemon=True)
            self.warmup_thread.start()

    def _request_options(self, text: str, *, warmup: bool = False) -> dict:
        num_predict = 1 if warmup else OLLAMA_NUM_PREDICT
        lowered = text.lower()
        detailed_english = ("elaborate", "explain more", "detail", "details", "long", "thorough")
        detailed_chinese = ("深入", "詳細", "多說", "解釋")
        if not warmup and (
            any(phrase in lowered for phrase in detailed_english)
            or any(phrase in text for phrase in detailed_chinese)
        ):
            num_predict = OLLAMA_NUM_PREDICT_DETAILED
        return {
            "num_ctx": OLLAMA_NUM_CTX,
            "num_predict": num_predict,
            "temperature": OLLAMA_TEMPERATURE,
            "top_p": OLLAMA_TOP_P,
        }

    def _warmup(self) -> None:
        started = time.monotonic()
        try:
            with requests.Session() as warmup_session:
                response = warmup_session.post(
                    self.url,
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": "ok"}],
                        "stream": False,
                        "keep_alive": OLLAMA_KEEP_ALIVE,
                        "options": self._request_options("ok", warmup=True),
                    },
                    timeout=(2, 20),
                )
                response.raise_for_status()
            if PERF_LOG:
                print(f"[PERF] ollama_warmup={time.monotonic() - started:.2f}s", flush=True)
        except Exception as e:
            print(f"[CHAT_BACKEND] Ollama warmup skipped: {e}", flush=True)

    def _trim_messages(self) -> None:
        system_messages = [m for m in self.messages if m["role"] == "system"]
        other_messages = [m for m in self.messages if m["role"] != "system"]
        self.messages = system_messages[:1] + other_messages[-self.max_messages:]

    def prompt(self, text: str):
        user_message = {"role": "user", "content": text}
        self.messages.append(user_message)
        self._trim_messages()
        response_recorded = False

        request_started = time.monotonic()
        response = self.session.post(
            self.url,
            json={
                "model": self.model,
                "messages": self.messages,
                "stream": True,
                "keep_alive": OLLAMA_KEEP_ALIVE,
                "options": self._request_options(text),
            },
            stream=True,
            timeout=(10, None),
        )
        with self.response_lock:
            self.active_response = response
        try:
            response.raise_for_status()

            full = []
            first_token_at = None
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                data = json.loads(line)
                if "error" in data:
                    raise RuntimeError(data["error"])
                content = data.get("message", {}).get("content", "")
                if content:
                    if first_token_at is None:
                        first_token_at = time.monotonic()
                        if PERF_LOG:
                            print(f"[PERF] ollama_first_token={first_token_at - request_started:.2f}s", flush=True)
                    full.append(content)
                    yield content
                if data.get("done"):
                    break

            if full:
                self.messages.append({"role": "assistant", "content": "".join(full)})
                self._trim_messages()
                response_recorded = True
            if PERF_LOG:
                print(f"[PERF] ollama_stream={time.monotonic() - request_started:.2f}s", flush=True)
        finally:
            response.close()
            with self.response_lock:
                if self.active_response is response:
                    self.active_response = None
            if not response_recorded:
                self.messages = [message for message in self.messages if message is not user_message]

    def cancel_current(self) -> None:
        with self.response_lock:
            response = self.active_response
        if response is not None:
            response.close()

    def close(self) -> None:
        self.cancel_current()
        self.session.close()
        if self.warmup_thread and self.warmup_thread.is_alive():
            self.warmup_thread.join(timeout=WORKER_JOIN_TIMEOUT_SECONDS)


class CodexCLIChat:
    def __init__(
        self,
        command: str,
        instructions: str,
        model: str = "",
        reasoning_effort: str = "minimal",
        verbosity: str = "low",
        web_search: bool = True,
        max_messages: int = 20,
        timeout: float = 90.0,
    ) -> None:
        self.display_name = "codex"
        self.command = command
        self.instructions = instructions
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.verbosity = verbosity
        self.web_search = web_search
        self.max_messages = max_messages
        self.timeout = timeout
        self.messages: list[dict[str, str]] = []
        self.proc_lock = threading.Lock()
        self.active_proc: subprocess.Popen[str] | None = None

    def _trim_messages(self) -> None:
        self.messages = self.messages[-self.max_messages :]

    def _build_prompt(self, text: str) -> str:
        history_lines = []
        for message in self.messages:
            role = "User" if message["role"] == "user" else "Assistant"
            history_lines.append(f"{role}: {message['content']}")
        history = "\n".join(history_lines[-self.max_messages :])
        if not history:
            history = "(No prior conversation.)"
        return (
            f"{self.instructions}\n\n"
            "You are responding through a small talking robot. "
            "Return strict JSON only, with no markdown and no extra text. "
            'Use this schema: {"speech_text":"...","speech_lang":"en|zh","display_text":"...","mood":"neutral|happy|excited|thinking|sad|angry|sleepy|surprised|love"}. '
            "speech_text is the complete answer and the exact words the robot should say out loud. "
            "display_text is the same complete answer formatted for the LCD; do not put extra answer content in display_text that is absent from speech_text. "
            "Choose mood from the schema to match the emotional meaning and tone of the complete answer; use neutral for ordinary factual answers. "
            "Prefer a short answer, usually one to four short sentences, but if the user explicitly asks you to elaborate, explain more, or give details, give a longer complete answer. "
            "Use speech_lang zh when speech_text is Chinese, and en when speech_text is English. "
            "Keep English as English. If display_text contains Chinese, use Traditional Chinese characters. "
            "Use web search when the user asks about current, latest, recent, or changing information. "
            "Never put raw URLs such as http:// or https:// in speech_text; say 'the link' if a link must be mentioned. "
            "Do not edit files, run commands, mention Codex, or include markdown.\n\n"
            f"Conversation so far:\n{history}\n\n"
            f"User: {text}\n"
            "Assistant:"
        )

    def prompt(self, text: str):
        prompt = self._build_prompt(text)
        fd, output_path = tempfile.mkstemp(prefix="codex_reply_", suffix=".txt")
        os.close(fd)
        cmd = shlex.split(self.command)
        if self.web_search and "--search" not in cmd:
            cmd.append("--search")
        cmd += [
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--skip-git-repo-check",
            "--ignore-rules",
            "--cd",
            "/tmp",
            "--sandbox",
            "read-only",
            "--color",
            "never",
            "--config",
            f"model_reasoning_effort=\"{self.reasoning_effort}\"",
            "--config",
            f"model_verbosity=\"{self.verbosity}\"",
            "--config",
            "model_reasoning_summary=\"none\"",
            "--config",
            "memories.use_memories=false",
            "--output-last-message",
            output_path,
        ]
        if self.model:
            cmd.extend(["--model", self.model])
        cmd.append("-")

        try:
            print(f"[CHAT_BACKEND] codex cli: {' '.join(cmd[:-1])} -", flush=True)
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            with self.proc_lock:
                self.active_proc = proc
            try:
                stdout, stderr = proc.communicate(input=prompt, timeout=self.timeout)
            except subprocess.TimeoutExpired as e:
                terminate_process(proc, timeout=1.5, process_group=True)
                raise RuntimeError(f"Codex CLI timed out after {self.timeout:g}s") from e
            finally:
                with self.proc_lock:
                    if self.active_proc is proc:
                        self.active_proc = None
            if proc.returncode != 0:
                detail = (stderr or stdout).strip()
                raise RuntimeError(detail or f"Codex CLI exited with code {proc.returncode}")
            reply = Path(output_path).read_text(encoding="utf-8", errors="replace").strip()
        finally:
            try:
                os.unlink(output_path)
            except OSError:
                pass

        parsed_reply = self._parse_reply(reply)
        speech = normalize_for_tts(parsed_reply["speech_text"])
        speech_lang = parsed_reply["speech_lang"]
        display = display_text(parsed_reply["display_text"].strip() or speech)
        mood = parsed_reply["mood"]
        if speech:
            self.messages.append({"role": "user", "content": text})
            self.messages.append({"role": "assistant", "content": display})
            self._trim_messages()
            yield json.dumps(
                {"speech_text": speech, "speech_lang": speech_lang, "display_text": display, "mood": mood},
                ensure_ascii=False,
            )

    def cancel_current(self) -> None:
        with self.proc_lock:
            proc = self.active_proc
        terminate_process(proc, timeout=1.0, process_group=True)

    def close(self) -> None:
        self.cancel_current()

    def _parse_reply(self, reply: str) -> dict[str, str]:
        reply = strip_thinking(reply).strip()
        match = re.search(r"\{.*\}", reply, flags=re.DOTALL)
        raw_json = match.group(0) if match else reply
        try:
            payload = json.loads(raw_json)
            speech = normalize_for_tts(str(payload.get("speech_text", "") or payload.get("speech_en", "")))
            speech_lang = str(payload.get("speech_lang", "")).strip().lower()
            display = " ".join(str(payload.get("display_text", "")).split())
            mood = normalize_mood(str(payload.get("mood", "")))
        except Exception:
            speech = normalize_for_tts(reply)
            speech_lang = ""
            display = " ".join(reply.split())
            mood = None
        if not speech:
            speech = "I understood."
        if speech_lang not in {"en", "zh"}:
            speech_lang = tts_language_for_text(speech)
        if not display:
            display = speech
        display = display_text(display)
        display_matches_speech_language = contains_cjk(display) if speech_lang == "zh" else not contains_cjk(display)
        if display and len(display) > len(speech) + 12 and display_matches_speech_language:
            print(
                f"[CODEX_TTS_FILL] using fuller display_text for TTS speech={len(speech)} display={len(display)}",
                flush=True,
            )
            speech = normalize_for_tts(display)
        return {
            "speech_text": speech,
            "speech_lang": speech_lang,
            "display_text": display,
            "mood": mood or choose_mood(display),
        }


def make_chat_backend(argv: list[str]):
    backend = RESPONSE_BACKEND
    for arg in argv:
        if arg == "--codex":
            backend = "codex"
        elif arg in {"--local-llm", "--ollama"}:
            backend = "ollama"
        elif arg.startswith("--backend="):
            backend = arg.split("=", 1)[1].strip().lower()

    if backend in {"local", "local-llm", "ollama"}:
        print(
            "[CHAT_BACKEND] "
            f"ollama model={OLLAMA_MODEL} url={OLLAMA_URL} ctx={OLLAMA_NUM_CTX} "
            f"predict={OLLAMA_NUM_PREDICT}/{OLLAMA_NUM_PREDICT_DETAILED} "
            f"keep_alive={OLLAMA_KEEP_ALIVE} warmup={int(OLLAMA_WARMUP)}",
            flush=True,
        )
        return OllamaStreamChat(
            model=OLLAMA_MODEL,
            url=OLLAMA_URL,
            instructions=INSTRUCTIONS,
            max_messages=MAX_MESSAGES,
        )
    if backend in {"codex", "codex-cli"}:
        print(
            "[CHAT_BACKEND] "
            f"codex command={CODEX_COMMAND} model={CODEX_MODEL or 'default'} "
            f"reasoning={CODEX_REASONING_EFFORT} verbosity={CODEX_VERBOSITY} "
            f"web_search={CODEX_WEB_SEARCH}",
            flush=True,
        )
        return CodexCLIChat(
            command=CODEX_COMMAND,
            instructions=INSTRUCTIONS,
            model=CODEX_MODEL,
            reasoning_effort=CODEX_REASONING_EFFORT,
            verbosity=CODEX_VERBOSITY,
            web_search=CODEX_WEB_SEARCH,
            max_messages=CODEX_MAX_MESSAGES,
            timeout=CODEX_TIMEOUT_SECONDS,
        )

    raise ValueError("Unknown response backend. Use ollama/local-llm or codex/codex-cli.")


class PrefetchedChatResponse:
    """Start backend work eagerly while the UI and thinking cue are prepared."""

    def __init__(self, chat, text: str) -> None:
        self.chat = chat
        self.text = text
        self.items: "queue.Queue[tuple[str, object]]" = queue.Queue(maxsize=CHAT_PREFETCH_QUEUE_SIZE)
        self.cancel_event = threading.Event()
        self.interrupt_event: threading.Event | None = None
        self.thread = threading.Thread(target=self._produce, daemon=True)
        self.started_at: float | None = None

    def start(self) -> None:
        self.started_at = time.monotonic()
        self.thread.start()
        print(f"[CHAT_PREFETCH] started backend={self.chat.display_name}", flush=True)

    def _produce(self) -> None:
        stream = None
        first_chunk = True
        try:
            stream = self.chat.prompt(self.text)
            for chunk in stream:
                if self.cancel_event.is_set():
                    break
                if first_chunk:
                    first_chunk = False
                    if PERF_LOG and self.started_at is not None:
                        print(
                            f"[PERF] chat_prefetch_first={time.monotonic() - self.started_at:.2f}s "
                            f"backend={self.chat.display_name}",
                            flush=True,
                        )
                if not self._put_item(("chunk", chunk)):
                    break
        except Exception as e:
            if not self.cancel_event.is_set():
                self._put_item(("error", e))
        finally:
            if self.cancel_event.is_set() and stream is not None:
                stream.close()
            if not self.cancel_event.is_set():
                self._put_item(("done", None))

    def _put_item(self, item: tuple[str, object]) -> bool:
        while not self.cancel_event.is_set():
            try:
                self.items.put(item, timeout=0.1)
                return True
            except queue.Full:
                continue
        return False

    def __iter__(self):
        while True:
            if self.interrupt_event and self.interrupt_event.is_set():
                return
            try:
                timeout = BARGE_IN_INTERRUPT_POLL_SECONDS if self.interrupt_event else None
                kind, value = self.items.get(timeout=timeout)
            except queue.Empty:
                continue
            if kind == "chunk":
                yield value
            elif kind == "error":
                self.thread.join(timeout=WORKER_JOIN_TIMEOUT_SECONDS)
                raise value
            else:
                self.thread.join(timeout=WORKER_JOIN_TIMEOUT_SECONDS)
                return

    def cancel(self) -> None:
        self.cancel_event.set()
        cancel_current = getattr(self.chat, "cancel_current", None)
        if callable(cancel_current):
            cancel_current()
        if self.thread.is_alive() and self.thread is not threading.current_thread():
            self.thread.join(timeout=WORKER_JOIN_TIMEOUT_SECONDS)


def pop_completed_sentences(buffer: str) -> tuple[list[str], str]:
    sentences = []
    start = 0
    sentence_end = r"(?:[。！？]+[\"'”’」』）)]*\s*|[.!?]+[\"'”’」』）)]*(?:\s+|$))"
    for match in re.finditer(sentence_end, buffer):
        end = match.end()
        sentence = buffer[start:end].strip()
        if sentence:
            sentences.append(sentence)
        start = end
    if buffer.endswith((".", "!", "?", "。", "！", "？")):
        sentence = buffer[start:].strip()
        if sentence:
            sentences.append(sentence)
            start = len(buffer)
    return sentences, buffer[start:]


def split_tts_queue_sentences(text: str, language: str) -> list[str]:
    text = normalize_for_spoken_tts(text)
    if not text:
        return []

    if language == "zh":
        sentence_end = r"[。！？!?]+[\"'”’」』）)]*\s*"
    else:
        sentence_end = r"[.!?]+[\"'”’）)]*(?:\s+|$)"

    chunks = []
    start = 0
    for match in re.finditer(sentence_end, text):
        end = match.end()
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end

    tail = text[start:].strip()
    if tail:
        chunks.append(tail)
    return chunks or [text]


def pop_speakable_chunks(buffer: str) -> tuple[list[str], str]:
    chunks, tail = pop_completed_sentences(buffer)
    if chunks:
        return chunks, tail

    compact = buffer.strip()
    if len(compact) < TTS_EAGER_CHARS:
        return [], buffer

    split_at = -1
    for punctuation in (", ", "; ", ": ", " - ", "，", "、", "；", "："):
        idx = buffer.rfind(punctuation)
        if idx >= TTS_MIN_CHARS:
            split_at = idx + len(punctuation)
            break

    if split_at < TTS_MIN_CHARS:
        return [], buffer

    chunk = buffer[:split_at].strip()
    return [chunk], buffer[split_at:]


def main():
    wake_listener = None
    stt = None
    wake_stt = None
    chat = None
    utility_mode = any(arg in sys.argv for arg in ("--tts-test", "--beep-test", "--mood-test"))
    if not utility_mode and WAKE_ENGINE in {"vosk", "auto"}:
        try:
            wake_listener = VoskWakeListener()
            wake_listener.start()
        except RuntimeError as e:
            print(f"[WAKE_VOSK_ERROR] {e}; falling back to Whisper wake recognition.", flush=True)
    elif not utility_mode and WAKE_ENGINE != "whisper":
        print(f"[WAKE_ENGINE] Unknown engine '{WAKE_ENGINE}'; falling back to Whisper.", flush=True)
    fast_wake_ack_ready = generate_fast_wake_ack() if not utility_mode else False

    head = HeadMotion(enabled=HEAD_MOTION_ENABLED and "--no-head" not in sys.argv)
    lcd = LCDMoodDisplay(enabled="--no-lcd" not in sys.argv)
    tts = TTSProcess(head_motion=head, lcd_display=lcd)

    if "--tts-test" in sys.argv:
        tts.say("This is a TTS worker test. If you hear this, playback is working.")
        tts.wait_until_done()
        tts.close()
        lcd.close()
        head.close()
        return

    if "--beep-test" in sys.argv:
        tts.say("This is the first sentence.")
        tts.inter_sentence_beep()
        tts.say("This is the second sentence.")
        tts.wait_until_done()
        tts.close()
        lcd.close()
        head.close()
        return

    if "--mood-test" in sys.argv:
        for sample in [
            "I am thinking about that.",
            "That is awesome!",
            "I love that idea.",
            "Oh no, I am sorry.",
            "Wow, that surprised me.",
        ]:
            mood = choose_mood(sample)
            lcd.set_mood(mood, text=sample)
            tts.say(sample)
        tts.wait_until_done()
        tts.close()
        lcd.close()
        head.close()
        return

    try:
        chat_stt_model = OPENAI_TRANSCRIBE_MODEL if STT_BACKEND == "openai" else WHISPER_MODEL
        stt = WhisperSTT(
            label="chat",
            backend=STT_BACKEND,
            model_name=chat_stt_model,
            language=WHISPER_LANGUAGE,
            beam_size=WHISPER_BEAM_SIZE,
            vad_filter=WHISPER_VAD_FILTER,
            voice_start_rms=VOICE_START_RMS,
            voice_end_rms=VOICE_END_RMS,
            end_silence_seconds=END_SILENCE_SECONDS,
            max_record_seconds=MAX_RECORD_SECONDS,
            hotwords=WHISPER_HOTWORDS,
        )
        if wake_listener is None:
            wake_stt_model = WAKE_OPENAI_TRANSCRIBE_MODEL if WAKE_STT_BACKEND == "openai" else WAKE_WHISPER_MODEL
            wake_stt = stt
            if (
                WAKE_STT_BACKEND != STT_BACKEND
                or wake_stt_model != chat_stt_model
                or WAKE_WHISPER_LANGUAGE != WHISPER_LANGUAGE
                or WAKE_WHISPER_BEAM_SIZE != WHISPER_BEAM_SIZE
                or WAKE_WHISPER_VAD_FILTER != WHISPER_VAD_FILTER
                or WAKE_VOICE_START_RMS != VOICE_START_RMS
                or WAKE_VOICE_END_RMS != VOICE_END_RMS
                or WAKE_END_SILENCE_SECONDS != END_SILENCE_SECONDS
                or WAKE_MAX_RECORD_SECONDS != MAX_RECORD_SECONDS
            ):
                wake_stt = WhisperSTT(
                    label="wake",
                    backend=WAKE_STT_BACKEND,
                    model_name=wake_stt_model,
                    language=WAKE_WHISPER_LANGUAGE,
                    beam_size=WAKE_WHISPER_BEAM_SIZE,
                    vad_filter=WAKE_WHISPER_VAD_FILTER,
                    voice_start_rms=WAKE_VOICE_START_RMS,
                    voice_end_rms=WAKE_VOICE_END_RMS,
                    end_silence_seconds=WAKE_END_SILENCE_SECONDS,
                    max_record_seconds=WAKE_MAX_RECORD_SECONDS,
                    hotwords=WAKE_WHISPER_HOTWORDS,
                )
            wake_listener = ContinuousWakeListener(wake_stt)
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        if wake_listener:
            wake_listener.stop()
        if wake_stt is not None and wake_stt is not stt:
            wake_stt.close()
        if stt is not None:
            stt.close()
        tts.close()
        lcd.close()
        head.close()
        return

    try:
        chat = make_chat_backend(sys.argv[1:])
    except ValueError as e:
        print(f"[ERROR] {e}")
        if wake_listener:
            wake_listener.stop()
        if wake_stt is not None and wake_stt is not stt:
            wake_stt.close()
        if stt is not None:
            stt.close()
        tts.close()
        lcd.close()
        head.close()
        return

    assert wake_listener is not None
    assert stt is not None
    barge_in = BargeInMonitor(wake_listener, stt, tts, lcd)
    active_wake_phrases = WAKE_VOSK_PHRASES if isinstance(wake_listener, VoskWakeListener) else WAKE_PHRASES
    awake = False
    awake_sleep_deadline: float | None = None
    response_stream: PrefetchedChatResponse | None = None
    pending_text: str | None = None

    def reset_awake_sleep_deadline(reason: str) -> None:
        nonlocal awake_sleep_deadline
        awake_sleep_deadline = time.monotonic() + SLEEP_TIMEOUT_SECONDS
        print(f"[SLEEP_TIMER] reset {reason}; sleeping in {SLEEP_TIMEOUT_SECONDS:g}s without input.", flush=True)

    def enter_sleep(announcement: str | None = "Going to sleep.", screen_text: str = SLEEP_TEXT) -> None:
        nonlocal awake, awake_sleep_deadline
        awake = False
        awake_sleep_deadline = None
        lcd.set_mood("sleepy", text=screen_text, sleep_fish=True, listening_waves=False)
        if announcement:
            tts.say(announcement)
            tts.wait_until_done()
        if screen_text != SLEEP_TEXT:
            lcd.set_text(SLEEP_TEXT)

    def accept_interrupted_followup() -> None:
        nonlocal pending_text, response_stream
        followup = barge_in.wait_for_followup()
        barge_in.stop()
        tts.restart()
        response_stream = None
        if followup:
            pending_text = followup
            user_language = language_display_name(stt.last_language)
            lcd.send_display(
                text=display_text(f"You ({user_language}): {followup}"),
                meteor_shower=False,
                listening_waves=False,
                idea_icon=False,
            )
            print("[BARGE_IN_FOLLOWUP] New question accepted.", flush=True)
            reset_awake_sleep_deadline("after interrupted question")
            return

        lcd.send_display(
            text="Now listening...",
            meteor_shower=False,
            listening_waves=True,
            idea_icon=False,
        )
        reset_awake_sleep_deadline("after interruption")

    lcd.set_mood("sleepy", text=SLEEP_TEXT, sleep_fish=True, listening_waves=False)
    print(f"[INFO] Sleeping. Wake phrases: {', '.join(active_wake_phrases)}", flush=True)

    try:
        while True:
            if awake:
                wake_listener.stop()
                if pending_text is not None:
                    text = pending_text
                    pending_text = None
                    print(f"[BARGE_IN_FOLLOWUP] Processing new question: {text}", flush=True)
                else:
                    now = time.monotonic()
                    if awake_sleep_deadline is None:
                        awake_sleep_deadline = (tts.last_done_at or now) + SLEEP_TIMEOUT_SECONDS
                    remaining_awake_seconds = awake_sleep_deadline - now
                    if remaining_awake_seconds <= 0:
                        print("[INFO] Awake sleep timer expired. Going to sleep.", flush=True)
                        enter_sleep()
                        time.sleep(0.1)
                        continue
                    if tts.last_done_at is None:
                        print(
                            f"[INFO] Awake. Waiting up to {remaining_awake_seconds:.1f}s for speech input.",
                            flush=True,
                        )
                    else:
                        since_tts = time.monotonic() - tts.last_done_at
                        print(
                            f"[INFO] TTS finished {since_tts:.1f}s ago. "
                            f"Sleep timer has {remaining_awake_seconds:.1f}s remaining.",
                            flush=True,
                        )
                    lcd.send_display(
                        text="Now listening...",
                        sleep_fish=False,
                        meteor_shower=False,
                        listening_waves=True,
                    )
                    text = stt.listen(max_wait_seconds=remaining_awake_seconds)
            else:
                print("[INFO] Sleeping. Listening for wake phrase.", flush=True)
                lcd.send_display(text=SLEEP_TEXT, sleep_fish=True, meteor_shower=False, listening_waves=False)
                text = wake_listener.listen()
            lcd.set_listening_waves(False)

            if not text:
                if awake:
                    remaining_awake_seconds = (awake_sleep_deadline or time.monotonic()) - time.monotonic()
                    if remaining_awake_seconds > 0.25:
                        print(
                            f"[INFO] Nothing recognized. Still awake for {remaining_awake_seconds:.1f}s.",
                            flush=True,
                        )
                        time.sleep(0.1)
                        continue
                    print("[INFO] No response before sleep deadline. Going to sleep.", flush=True)
                    enter_sleep()
                else:
                    print("[INFO] Nothing recognized. Still sleeping.")
                time.sleep(0.1)
                continue

            if is_exit_request(text):
                print("[INFO] Exit phrase recognized. Stopping program.", flush=True)
                break

            if not awake:
                if is_wake_request(text):
                    print("[INFO] Wake phrase recognized.", flush=True)
                    wake_listener.stop()
                    awake = True
                    lcd.set_mood("happy", text=WELCOME, sleep_fish=False, listening_waves=False)
                    if not tts.ready.is_set() and fast_wake_ack_ready and play_fast_wake_ack():
                        tts.last_done_at = time.monotonic()
                    else:
                        tts.say(WELCOME)
                        tts.wait_until_done()
                    reset_awake_sleep_deadline("after welcome")
                else:
                    print("[INFO] Ignoring speech while sleeping.", flush=True)
                    lcd.set_mood("sleepy", text=SLEEP_TEXT, sleep_fish=True, listening_waves=False)
                time.sleep(0.1)
                continue

            if is_sleep_request(text):
                print("[INFO] Sleep phrase recognized. Continuing to listen for wake phrase.", flush=True)
                enter_sleep("Goodbye!", screen_text="Goodbye!")
                time.sleep(0.1)
                continue

            chat_started = time.monotonic()
            response_stream = PrefetchedChatResponse(chat, text)
            response_stream.start()
            thinking_language = "zh" if stt.last_language == "zh" or contains_cjk(text) else "en"
            user_language = language_display_name(stt.last_language)
            lcd.set_mood(
                "thinking",
                text=display_text(f"You ({user_language}): {text}"),
                sleep_fish=False,
                listening_waves=False,
                idea_icon=True,
            )
            play_thinking_sound()

            sentence_buffer = ""
            speech_chunks_queued = 0
            response_mood_set = False
            thinking_delay = (
                CODEX_THINKING_FILLER_DELAY_SECONDS
                if isinstance(chat, CodexCLIChat)
                else OLLAMA_THINKING_FILLER_DELAY_SECONDS
            )
            thinking_cue = ThinkingCue(tts, lcd, thinking_delay, language=thinking_language)
            response_interrupted = False
            barge_in.start()
            response_stream.interrupt_event = barge_in.interrupt_event
            thinking_cue.start()
            model_output_started = False
            try:
                for next_word in response_stream:
                    if barge_in.interrupted():
                        response_interrupted = True
                        break
                    if not next_word:
                        continue
                    if not model_output_started:
                        thinking_cue.stop()
                        model_output_started = True
                    print(next_word, end="", flush=True)

                    if isinstance(chat, CodexCLIChat):
                        try:
                            codex_payload = json.loads(next_word)
                            speech_chunk = normalize_for_tts(str(codex_payload.get("speech_text", "") or codex_payload.get("speech_en", "")))
                            speech_language = str(codex_payload.get("speech_lang", "")).strip().lower()
                            if speech_language not in {"en", "zh"}:
                                speech_language = tts_language_for_text(speech_chunk)
                            display_chunk = display_text(str(codex_payload.get("display_text", "")) or speech_chunk)
                            response_mood = normalize_mood(str(codex_payload.get("mood", "")))
                        except Exception:
                            speech_chunk = normalize_for_tts(next_word)
                            speech_language = tts_language_for_text(speech_chunk)
                            display_chunk = display_text(next_word)
                            response_mood = None
                        if speech_chunk:
                            if not response_mood_set:
                                lcd.set_mood(response_mood or choose_mood(speech_chunk))
                                response_mood_set = True
                            for speech_sentence in split_tts_queue_sentences(speech_chunk, speech_language):
                                if barge_in.interrupted():
                                    response_interrupted = True
                                    break
                                print(f"\n[TTS_QUEUE] {speech_sentence}", flush=True)
                                if speech_chunks_queued:
                                    tts.inter_sentence_beep()
                                tts.say(speech_sentence, language=speech_language)
                                speech_chunks_queued += 1
                        if response_interrupted:
                            break
                        if STREAM_LOOP_SLEEP_SECONDS > 0:
                            time.sleep(STREAM_LOOP_SLEEP_SECONDS)
                        continue

                    sentence_buffer += next_word
                    chunks, sentence_buffer = pop_speakable_chunks(sentence_buffer)
                    for chunk in chunks:
                        if barge_in.interrupted():
                            response_interrupted = True
                            break
                        display_chunk = normalize_for_tts(chunk)
                        if display_chunk:
                            if contains_cjk(display_chunk):
                                speech_chunk = display_chunk
                                speech_language = "zh"
                            else:
                                speech_chunk = display_chunk
                                speech_language = "en"
                            print(f"\n[TTS_QUEUE] {speech_chunk or '[cjk skipped]'}", flush=True)
                            if speech_chunk and speech_chunks_queued:
                                tts.inter_sentence_beep()
                            if not response_mood_set:
                                lcd.set_mood(choose_mood(display_chunk))
                                response_mood_set = True
                            if speech_chunk:
                                tts.say(speech_chunk, language=speech_language)
                                speech_chunks_queued += 1
                            if STREAM_LOOP_SLEEP_SECONDS > 0:
                                time.sleep(STREAM_LOOP_SLEEP_SECONDS)
                    if response_interrupted:
                        break
            except Exception as e:
                response_stream.cancel()
                thinking_cue.stop()
                if barge_in.interrupted():
                    response_interrupted = True
                    print("\n[BARGE_IN] Response interrupted.", flush=True)
                    accept_interrupted_followup()
                    time.sleep(0.05)
                    continue
                barge_in.stop()
                err = str(e)
                if isinstance(chat, OllamaStreamChat) and "not found" in err.lower() and "model" in err.lower():
                    msg = f"Ollama model '{OLLAMA_MODEL}' not found. Run: ollama pull {OLLAMA_MODEL}"
                    print(f"\n[ERROR] {msg}")
                    tts.say("Ollama model not found. Please pull the model.")
                    tts.wait_until_done()
                    reset_awake_sleep_deadline("after backend error")
                    time.sleep(0.05)
                    continue
                print(f"\n[ERROR] Response backend failed: {err}")
                tts.say("Sorry, the response backend failed.")
                tts.wait_until_done()
                reset_awake_sleep_deadline("after backend error")
                time.sleep(0.05)
                continue
            print("")
            thinking_cue.stop()
            if response_interrupted or barge_in.interrupted():
                response_stream.cancel()
                print("[BARGE_IN] Response interrupted; capturing the new question.", flush=True)
                accept_interrupted_followup()
                time.sleep(0.05)
                continue
            if PERF_LOG:
                print(
                    f"[PERF] response_queue={time.monotonic() - chat_started:.2f}s "
                    f"tts_chunks={speech_chunks_queued}",
                    flush=True,
                )

            display_tail = "" if barge_in.interrupted() else normalize_for_tts(sentence_buffer)
            if display_tail:
                if contains_cjk(display_tail):
                    speech_tail = display_tail
                    speech_language = "zh"
                else:
                    speech_tail = display_tail
                    speech_language = "en"
                print(f"[TTS_QUEUE] {speech_tail or '[cjk skipped]'}", flush=True)
                if speech_tail and speech_chunks_queued and not barge_in.interrupted():
                    tts.inter_sentence_beep()
                if not response_mood_set:
                    lcd.set_mood(choose_mood(display_tail))
                if speech_tail and not barge_in.interrupted():
                    tts.say(speech_tail, language=speech_language)
                    speech_chunks_queued += 1

            tts.wait_until_done(interrupt_event=barge_in.interrupt_event)
            if barge_in.interrupted():
                print("[BARGE_IN] Response playback interrupted; capturing the new question.", flush=True)
                accept_interrupted_followup()
                time.sleep(0.05)
                continue
            barge_in.stop()
            response_stream = None
            reset_awake_sleep_deadline("after response")
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n[INFO] Stopping...")
    finally:
        wake_listener.stop()
        barge_in.stop()
        if response_stream is not None:
            response_stream.cancel()
        close_chat = getattr(chat, "close", None)
        if callable(close_chat):
            close_chat()
        if wake_stt is not None and wake_stt is not stt:
            wake_stt.close()
        if stt is not None:
            stt.close()
        lcd.set_mood("sleepy", text="Goodbye!", listening_waves=False)
        if tts.ready.is_set():
            tts.say("Goodbye!")
            tts.wait_until_done()
        else:
            print("[TTS] Skipping spoken shutdown while the voice model is still loading.", flush=True)
        tts.close()
        lcd.close()
        head.close()
        print("Bye.")


if __name__ == "__main__":
    main()
