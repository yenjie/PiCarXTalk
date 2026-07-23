# PiCarXTalk 19v1

`19v1` is a bilingual English/Mandarin voice-chat program for PiCar-X. It uses:

- streaming Vosk wake detection for `hello robot` and `hey robot`;
- local faster-whisper transcription constrained to English and Mandarin;
- Codex CLI or local Ollama responses;
- English Piper and Taiwanese Mandarin TTS;
- animated Pikachu moods with speaking/listening motion, bilingual response text, and 1.69-inch or 2.4-inch SPI LCD output;
- input-language thinking fillers while the response backend runs concurrently.

Thinking fillers are audio-only. The LCD keeps the user's original transcript visible until the real response starts.
Long-running queues and audio buffers are bounded, and backend, TTS, LCD, temporary-file, and worker lifecycles are cleaned up explicitly.

## Run

Create the runtime environment and install this repository's PiCar-X package:

```bash
python3 -m venv --system-site-packages example/.venv-whisper
example/.venv-whisper/bin/pip install -r requirements-19v1.txt
example/.venv-whisper/bin/pip install -e .
```

Install/configure Codex CLI, and install the Vosk model at:

```text
~/.vosk_models/vosk-model-small-en-us-0.15
```

The LCD vendor Python directory defaults to:

```text
~/LCD_Module_RPI_code/RaspberryPi/python
```

Override it with `LCD_PYTHON_DIR` when needed. Then run:

```bash
cd example
./run_19v1.sh
```

The runner defaults to Codex, the 2.4-inch LCD, and direct HifiBerry output. Examples:

```bash
./run_19v1.sh --ollama
./run_19v1.sh --lcd-1inch69
TTS_PLAYBACK_DEVICE=pulse ./run_19v1.sh
```

Useful environment settings include `CODEX_MODEL`, `OLLAMA_MODEL`, `MIC_ALSA_DEVICE`, `LCD_SCREEN`, `LCD_PYTHON_DIR`, `TTS_PLAYBACK_DEVICE`, `WHISPER_MODEL`, `THINKING_FILLERS_EN`, and `THINKING_FILLERS_ZH`.

While the robot is responding, interruption is intentionally stricter than wake-from-sleep recognition. By default, only exact `hello robot` or `hey robot` interrupts a response. Set `BARGE_IN_PHRASES` to customize that list; permissive wake aliases remain available while sleeping.

## Test

Run the hardware-free runtime and renderer tests with:

```bash
cd example
.venv-whisper/bin/python -m unittest -v test_19v1_runtime.py
```

See [`example/PERFORMANCE_19v1.md`](example/PERFORMANCE_19v1.md) for the performance changes, memory stress results, and queue settings.
