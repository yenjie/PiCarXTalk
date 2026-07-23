import json
import asyncio
import math
import os
import random
import re
import subprocess
import sys
import tempfile
import time
import wave

from picarx.tts import Piper

TTS_MODEL = os.getenv("PIPER_TTS_MODEL", "en_US-lessac-high")
PLAYBACK_DEVICE = os.getenv("TTS_PLAYBACK_DEVICE", "pulse")
BEEP_VOLUME = int(os.getenv("TTS_BEEP_VOLUME", "7000"))
CHINESE_TTS_ENGINE = os.getenv("CHINESE_TTS_ENGINE", "edge")
CHINESE_TTS_COMMAND = os.getenv("CHINESE_TTS_COMMAND", "espeak")
CHINESE_TTS_VOICE = os.getenv("CHINESE_TTS_VOICE", "zh")
CHINESE_TTS_SPEED = os.getenv("CHINESE_TTS_SPEED", "150")
EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "zh-TW-HsiaoChenNeural")
EDGE_TTS_RATE = os.getenv("EDGE_TTS_RATE", "+0%")
EDGE_TTS_VOLUME = os.getenv("EDGE_TTS_VOLUME", "+0%")
EDGE_TTS_PITCH = os.getenv("EDGE_TTS_PITCH", "+0Hz")
KOKORO_CHINESE_VOICE = os.getenv("KOKORO_CHINESE_VOICE", "zf_001")
KOKORO_CHINESE_SPEED = float(os.getenv("KOKORO_CHINESE_SPEED", "1"))
KOKORO_CHINESE_VARIANT = os.getenv("KOKORO_CHINESE_VARIANT", "v1.1-zh")

kokoro_chinese_pipeline = None
inter_sentence_beeps: list[str] = []


def play_wav(path: str) -> None:
    last_error = None
    for attempt in range(5):
        try:
            subprocess.run(
                ["aplay", "-q", "-D", PLAYBACK_DEVICE, path],
                check=True,
            )
            return
        except subprocess.CalledProcessError as e:
            last_error = e
            time.sleep(0.2 * (attempt + 1))
    if last_error:
        raise last_error


def generate_inter_sentence_beep() -> str:
    sample_rate = 16000
    duration = random.uniform(0.055, 0.11)
    freq = random.choice([660, 740, 784, 880, 988, 1047])
    wobble = random.uniform(4.0, 18.0)
    samples = int(sample_rate * duration)

    with tempfile.NamedTemporaryFile(prefix="piper_gap_beep_", suffix=".wav", delete=False) as wav_file:
        wav_path = wav_file.name

    with wave.open(wav_path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        frames = bytearray()
        for i in range(samples):
            fade = min(1.0, i / 160) * min(1.0, (samples - i) / 160)
            mod = 1.0 + 0.025 * math.sin(2 * math.pi * wobble * i / sample_rate)
            sample = math.sin(2 * math.pi * freq * mod * i / sample_rate)
            frames.extend(int(BEEP_VOLUME * fade * sample).to_bytes(2, "little", signed=True))
        wav.writeframes(frames)

    return wav_path


def play_inter_sentence_beep() -> None:
    if not inter_sentence_beeps:
        inter_sentence_beeps.extend(generate_inter_sentence_beep() for _ in range(6))
    play_wav(random.choice(inter_sentence_beeps))


def cleanup_inter_sentence_beeps() -> None:
    while inter_sentence_beeps:
        wav_path = inter_sentence_beeps.pop()
        try:
            os.unlink(wav_path)
        except OSError:
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


def split_chinese_tts_sentences(text: str) -> list[str]:
    chunks = []
    start = 0
    for match in re.finditer(r"[。！？!?]+[\"'”’」』）)]*\s*", text):
        end = match.end()
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end

    tail = text[start:].strip()
    if tail:
        chunks.append(tail)
    return chunks or [text]


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text))


def normalize_language(language: str, text: str) -> str:
    language = (language or "").strip().lower()
    if language in {"zh", "zh-tw", "zh-cn", "cmn", "mandarin", "chinese"}:
        return "zh"
    if contains_cjk(text):
        return "zh"
    return "en"


def synthesize_chinese_espeak(text: str, wav_path: str) -> None:
    subprocess.run(
        [
            CHINESE_TTS_COMMAND,
            "-v",
            CHINESE_TTS_VOICE,
            "-s",
            CHINESE_TTS_SPEED,
            "-w",
            wav_path,
            text,
        ],
        check=True,
    )


def synthesize_chinese_kokoro(text: str, wav_path: str) -> None:
    global kokoro_chinese_pipeline
    if kokoro_chinese_pipeline is None:
        from pykokoro import GenerationConfig, KokoroPipeline, PipelineConfig

        print(
            f"[TTS_ZH_INIT] Kokoro voice={KOKORO_CHINESE_VOICE} variant={KOKORO_CHINESE_VARIANT}",
            flush=True,
        )
        kokoro_chinese_pipeline = KokoroPipeline(
            PipelineConfig(
                voice=KOKORO_CHINESE_VOICE,
                generation=GenerationConfig(lang="zh", speed=KOKORO_CHINESE_SPEED),
                model_variant=KOKORO_CHINESE_VARIANT,
            )
        )
    import soundfile as sf

    result = kokoro_chinese_pipeline.run(text)
    sf.write(wav_path, result.audio, result.sample_rate)


def synthesize_chinese_edge(text: str, wav_path: str) -> None:
    import edge_tts

    with tempfile.NamedTemporaryFile(prefix="edge_tts_", suffix=".mp3", delete=False) as media:
        media_path = media.name
    try:
        communicate = edge_tts.Communicate(
            text,
            EDGE_TTS_VOICE,
            rate=EDGE_TTS_RATE,
            volume=EDGE_TTS_VOLUME,
            pitch=EDGE_TTS_PITCH,
        )
        asyncio.run(communicate.save(media_path))
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                media_path,
                "-ar",
                "22050",
                "-ac",
                "1",
                wav_path,
            ],
            check=True,
        )
    finally:
        try:
            os.unlink(media_path)
        except OSError:
            pass


def synthesize_chinese(text: str, wav_path: str) -> None:
    if CHINESE_TTS_ENGINE == "edge":
        try:
            synthesize_chinese_edge(text, wav_path)
            return
        except Exception as e:
            print(f"[TTS_ZH_ERROR] Edge TTS failed, falling back to Kokoro/espeak: {e}", flush=True)
    if CHINESE_TTS_ENGINE == "kokoro":
        try:
            synthesize_chinese_kokoro(text, wav_path)
            return
        except Exception as e:
            print(f"[TTS_ZH_ERROR] Kokoro failed, falling back to espeak: {e}", flush=True)
    synthesize_chinese_espeak(text, wav_path)


def main() -> int:
    print(
        f"[TTS_INIT] Piper model={TTS_MODEL} playback={PLAYBACK_DEVICE} chinese_engine={CHINESE_TTS_ENGINE}",
        flush=True,
    )
    tts = Piper()
    tts.set_model(TTS_MODEL)
    print("[TTS_READY]", flush=True)

    try:
        for line in sys.stdin:
            try:
                msg = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[TTS_ERROR] bad json: {e}", flush=True)
                continue

            command = msg.get("command")
            if command == "say":
                text = normalize_for_tts(msg.get("text", ""))
                language = normalize_language(str(msg.get("language", "")), text)
                display_text = bool(msg.get("display", True))
                if text:
                    segments = split_chinese_tts_sentences(text) if language == "zh" else [text]
                    for segment in segments:
                        event = "TTS_START" if display_text else "TTS_START_HIDDEN"
                        print(f"[{event}] lang={language} {segment}", flush=True)
                        wav_path = None
                        try:
                            with tempfile.NamedTemporaryFile(prefix="piper_tts_", suffix=".wav", delete=False) as wav:
                                wav_path = wav.name
                            if language == "zh":
                                synthesize_chinese(segment, wav_path)
                            else:
                                tts.tts(segment, wav_path)
                            print("[TTS_PLAY_START]", flush=True)
                            play_wav(wav_path)
                        except Exception as e:
                            print(f"[TTS_ERROR] {e}", flush=True)
                        finally:
                            if wav_path:
                                try:
                                    os.unlink(wav_path)
                                except OSError:
                                    pass
                    print("[TTS_DONE]", flush=True)
            elif command == "beep":
                try:
                    print("[TTS_BEEP]", flush=True)
                    play_inter_sentence_beep()
                except Exception as e:
                    print(f"[TTS_ERROR] beep failed: {e}", flush=True)
            elif command == "sync":
                print(f"[TTS_SYNC_DONE] {msg.get('id', '')}", flush=True)
            elif command == "quit":
                return 0
        return 0
    finally:
        if kokoro_chinese_pipeline is not None:
            kokoro_chinese_pipeline.close()
        cleanup_inter_sentence_beeps()


if __name__ == "__main__":
    raise SystemExit(main())
