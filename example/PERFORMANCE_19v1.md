# 19v1 Performance And Lifecycle Notes

## Runtime Improvements

- PCM RMS calculation uses one conversion buffer and is about 2.9x faster in the focused benchmark.
- Recorded speech uses bounded `bytearray` buffers instead of lists followed by a full `bytes` join.
- Thinking and wake acknowledgement sounds are reused instead of regenerated on every turn.
- TTS display events, LCD commands, and model-prefetch output all use bounded queues.
- LCD display events are coalesced, and unchanged response-text layout is cached.
- Ollama HTTP responses and Codex process groups can be cancelled on interruption.
- HTTP sessions, worker threads, subprocesses, temporary files, and LCD pipes are closed explicitly.
- Mandarin Edge TTS uses the Python API directly instead of starting a new Python interpreter per sentence.
- A six-sound random beep bank removes repeated waveform generation and is deleted at worker shutdown.

## Pikachu Animation

Pikachu now has breathing, blinking, pupil movement, ear twitches, tail wagging, cheek pulses, animated speech, listening poses, and clearer paws and face details. Animation is driven by the existing LCD frame timer and speaking/listening state, so it does not add another worker thread.

## Verification

Run the hardware-free regression suite:

```bash
cd example
.venv-whisper/bin/python -m unittest -v test_19v1_runtime.py
```

The July 22, 2026 stress checks covered:

- 3,000 animated frames with stable RSS across all six measured batches;
- 300 saturated prefetch/cancel cycles ending with one active thread and 32 KiB RSS drift;
- queue bounds, backend cancellation, process reaping, PCM accuracy, and all animation states;
- TTS shutdown with no remaining worker processes or temporary audio/reply files.

Useful bounds can be adjusted with `CHAT_PREFETCH_QUEUE_SIZE`, `TTS_EVENT_QUEUE_SIZE`, `LCD_COMMAND_QUEUE_SIZE`, and `WORKER_JOIN_TIMEOUT_SECONDS`. The defaults are intended for Raspberry Pi and should normally be retained.
