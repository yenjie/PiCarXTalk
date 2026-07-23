# 19v2 Performance Validation

Measurements were taken on the target Raspberry Pi with the high-quality
`en_US-lessac-high` Piper voice, `base` faster-whisper model, USB microphone,
and HifiBerry playback device.

## Changes

- Active playback is interrupted with `SIGUSR1`; the worker stops only its
  `aplay` child and retains the loaded Piper model.
- Old queued speech and beeps are discarded until the follow-up question has
  been transcribed.
- If interruption occurs during non-cancellable synthesis, the hard-stop
  fallback is bounded and Piper reload is deferred until after Whisper.
- Every worker uses a parent-owned temporary directory, which is cleaned after
  normal shutdown and forced termination.
- Runtime logs now report `tts_interrupt`, `barge_handoff`, and
  `barge_followup` timings.

## Before And After

| Measurement | Original 19v2 | Optimized 19v2 |
| --- | ---: | ---: |
| Active playback interruption | 0.165 s | 0.002 s |
| Synthesis fallback interruption | 1.518 s | 0.568 s |
| Whisper while Piper reloads | 3.550 s | 2.485 s |
| Follow-up microphone handoff | 0.017 s | 0.003 s |
| Hardware fixture follow-up path | 12.28 s | 6.29 s |

The hardware fixture path includes playing a recorded question through the
same HifiBerry device. A person speaking into the separate USB microphone does
not incur that fixture playback time.

## Validation

- 12 deterministic runtime tests pass.
- 10 consecutive hardware playback interruptions averaged 2.5 ms and had a
  6.0 ms maximum.
- The same Piper worker PID survived all 10 interruptions.
- Worker RSS grew by 8.3 MiB during warm caches and then stabilized.
- No worker temporary files or audio subprocesses remained after testing.
- Five of five recorded wake-phrase trials were recognized by Vosk.
- English and Mandarin hardware follow-up questions were both identified and
  transcribed correctly.
- Beam size 1 was approximately 7% faster on matched fixtures, but beam size 2
  remains the default to retain more decoding margin for real speech.

## Tuning

The defaults favor reliable model preservation:

```bash
TTS_SOFT_INTERRUPT_TIMEOUT_SECONDS=0.35
TTS_HARD_INTERRUPT_TIMEOUT_SECONDS=0.2
WHISPER_BEAM_SIZE=2
```

Reducing the soft timeout can make synthesis fallback faster, but it can also
unnecessarily discard the loaded Piper model under high CPU load.
