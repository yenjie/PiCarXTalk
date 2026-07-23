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
- English/Mandarin language selection now reuses Whisper's transcription encoder output instead of
  running a separate encoder pass before decoding.
- CTranslate2 defaults to four CPU threads and one worker on the Raspberry Pi, avoiding
  oversubscription and duplicate model-worker memory.
- Configurable `WHISPER_HOTWORDS` and `WAKE_WHISPER_HOTWORDS` improve recognition of robot names,
  project names, and common bilingual terms without changing the selected Whisper model or beam size.

## Transcription Measurements

On the four-core Cortex-A76 Raspberry Pi, eight short English/Mandarin fixtures using multilingual
`base`, INT8, and beam size 2 averaged:

| Configuration | Mean transcription time | Aggregate similarity |
| --- | ---: | ---: |
| Previous two-pass auto detection | 3.99 seconds | 0.952 |
| Shared encoder plus bilingual hotwords | 2.58 seconds | 0.992 |

This is a 35% mean transcription-latency reduction. Speaker-to-USB-microphone tests also produced
exact English and Mandarin transcripts through the normal recording, preroll, RMS threshold, and
silence-detection path.

Alternatives were measured and rejected as defaults:

- beam size 1 was only 3-4% faster and reduced aggregate similarity;
- the `small` model took about 11-12 seconds per short fixture, roughly three times `base`;
- in-memory audio input did not materially improve latency because model inference dominates WAV decoding.

The English/Mandarin filter still rejects confidently unsupported speech. Set
`WHISPER_SHARED_ENCODER_LANGUAGE_DETECTION=0` to restore the previous two-pass path if needed.
Customize `WHISPER_HOTWORDS` for frequently used names and terminology, and keep
`WHISPER_NUM_WORKERS=1` unless concurrent transcription is intentionally required.

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

The July 23, 2026 transcription checks covered:

- 14 unrelated and domain-focused English/Mandarin fixtures;
- acoustic English and Mandarin capture through the robot speaker and USB microphone;
- confident Spanish rejection through the optimized language filter;
- ten repeated model inferences, with RSS stable at 329.09 MiB after one-time allocator/cache growth;
- full Vosk wake, welcome, chat recording, local Ollama streaming, TTS queue, and clean shutdown.

Useful bounds can be adjusted with `CHAT_PREFETCH_QUEUE_SIZE`, `TTS_EVENT_QUEUE_SIZE`, `LCD_COMMAND_QUEUE_SIZE`, and `WORKER_JOIN_TIMEOUT_SECONDS`. The defaults are intended for Raspberry Pi and should normally be retained.
