# PiCarXTalk 19v2

19v2 can stop an answer while it is being spoken and immediately accept a
new question.

## Run

```bash
./run_19v2.sh
```

Use `--ollama` to select Ollama instead of the default Codex backend:

```bash
./run_19v2.sh --ollama
```

## Interrupt A Response

1. While the robot is speaking, say `hello robot` or `hey robot`.
2. The current backend response and TTS playback stop.
3. When the LCD shows `Now listening...`, ask the new question.
4. The new question is transcribed in English or Mandarin and handled as the
   next conversation turn.

The robot waits five seconds for the new question to begin. These controls can
be overridden when needed:

```bash
BARGE_IN_FOLLOWUP_START_TIMEOUT_SECONDS=8 ./run_19v2.sh
BARGE_IN_INTERRUPT_POLL_SECONDS=0.03 ./run_19v2.sh
```

Set `BARGE_IN_FOLLOWUP_ENABLED=0` to retain the older behavior, which only
stops the response and returns to the normal listening loop.

## Test

```bash
.venv-whisper/bin/python -m unittest -v test_19v2_runtime.py
```
