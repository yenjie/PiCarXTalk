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
- Chat recording retains 0.45 seconds of preroll, allows a 0.55-second natural
  pause, and estimates rising background noise conservatively so quieter speech
  is less likely to be absorbed into the noise floor.
- Phrase-level English and Traditional Chinese hotwords improve common command,
  question, and project vocabulary without loading a larger model.

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

## Transcription Fixtures

The integrated automatic-language path was tested with seven English and seven
Mandarin recordings covering reminders, timers, weather, science questions,
and PiCar-X vocabulary.

| Measurement | Result |
| --- | ---: |
| Content-correct fixture transcripts | 14 / 14 |
| Warm `base` model average | 2.36 s |
| Warm `base` model range | 2.14-2.69 s |
| Tested languages | English, Mandarin |

The earlier vocabulary produced Mandarin homophone errors for `帶雨傘`, `鹹的`,
and `請用五個詳細的句子`. Phrase-level hotwords corrected all three while the
seven English fixtures remained correct. The `small` model took about 5.7
seconds on the two ambiguous Mandarin fixtures, so it remains an optional
higher-latency setting rather than the default.

## Validation

- 24 deterministic 19v2 runtime tests pass.
- 10 consecutive hardware playback interruptions averaged 2.5 ms and had a
  6.0 ms maximum.
- The same Piper worker PID survived all 10 interruptions.

## Wake And Memory Checks

The production Vosk grammar and 80 ms partial-result pipeline were exercised
with synthesized wake and near-match recordings:

| Phrase | Result | Trigger time |
| --- | --- | ---: |
| `hello robot` | accepted | 1.20 s |
| `hey robot` | accepted | 1.20 s |
| `hello Robert` | rejected | n/a |
| `yellow robot` | rejected | n/a |
| `hello rabbit` | rejected | n/a |

The exact-phrase gate adds no extra model pass. A 500-save memory stress test
kept only the configured 24 entries, reloaded the same 24 entries from disk,
and averaged 1.89 ms per atomic save (2.28 ms p95, 6.01 ms maximum). The
persistent context and in-process list are both bounded.

Relevant-memory selection is local and bounded to six results by default. A
100,000-query benchmark over 24 retained facts averaged 0.28 ms per lookup
after the bounded term cache was warm, so it does not add another Codex,
Ollama, or embedding-model request.
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
