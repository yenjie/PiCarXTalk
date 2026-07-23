#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$SCRIPT_DIR/.venv-whisper/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
    printf 'Missing Python environment: %s\n' "$PYTHON_BIN" >&2
    printf 'Set PYTHON_BIN or create example/.venv-whisper first.\n' >&2
    exit 1
fi

export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
export RESPONSE_BACKEND="${RESPONSE_BACKEND:-codex}"
export STT_BACKEND="${STT_BACKEND:-local}"
export WAKE_ENGINE="${WAKE_ENGINE:-vosk}"
export WAKE_STT_BACKEND="${WAKE_STT_BACKEND:-local}"
export WHISPER_ALLOWED_LANGUAGES="${WHISPER_ALLOWED_LANGUAGES:-en,zh}"
export WHISPER_BEAM_SIZE="${WHISPER_BEAM_SIZE:-2}"
export WHISPER_CPU_THREADS="${WHISPER_CPU_THREADS:-4}"
export WHISPER_NUM_WORKERS="${WHISPER_NUM_WORKERS:-1}"
export WHISPER_SHARED_ENCODER_LANGUAGE_DETECTION="${WHISPER_SHARED_ENCODER_LANGUAGE_DETECTION:-1}"
export LCD_SCREEN="${LCD_SCREEN:-2inch4}"
export TTS_PLAYBACK_DEVICE="${TTS_PLAYBACK_DEVICE:-plughw:CARD=sndrpihifiberry,DEV=0}"
export CODEX_MODEL="${CODEX_MODEL:-gpt-5.3-codex-spark}"

exec "$PYTHON_BIN" "$SCRIPT_DIR/19v1.local_voice_chatbot_bilingual_thinking.py" "$@"
