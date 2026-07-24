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

## Fast Wake Accuracy

The default streaming Vosk wake listener responds only when it recognizes
`hello robot` or `hey robot`. Similar phrases such as `hello Robert`, `yellow
robot`, and `hello rabbit` are rejected. This stricter gate does not add a
second recognition pass or change the 80 ms streaming blocks, so the fast
partial-result wake path remains active.

Override the accepted phrases only when deliberately changing this behavior:

```bash
WAKE_VOSK_PHRASES="hello robot,hey robot" ./run_19v2.sh
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

19v2 preserves the loaded Piper voice model when playback is interrupted. If
the worker is still synthesizing and cannot stop promptly, it uses a bounded
hard stop and waits until follow-up transcription is complete before reloading
Piper. See [PERFORMANCE_19v2.md](PERFORMANCE_19v2.md) for measurements.

## Important Memory

19v2 keeps the short in-process conversation history and also persists a
bounded set of important user facts. Say an explicit request such as `remember
that my favorite color is green` or `請記住我喜歡吃水餃`. Durable identity and
preference statements such as `my name is...`, `I prefer...`, `我的名字是...`,
and `我喜歡...` are also retained automatically.

After a new fact is saved, the robot says `Now I remember it.` in English or
`我記住了。` in Mandarin. This acknowledgement does not replace the original
user message on the LCD. Repeated facts are de-duplicated, and updated
single-value facts such as the user's name replace the older value.

Memory management commands are handled locally without waiting for Codex or
Ollama:

| Action | English example | Mandarin example |
| --- | --- | --- |
| List | `What do you remember about me?` | `你記得我什麼？` |
| Forget one | `Forget green tea.` | `請忘記綠茶。` |
| Clear request | `Forget everything.` | `忘記全部。` |
| Confirm clear | `Confirm forget everything.` | `確認忘記全部。` |

Clearing all memories requires the confirmation phrase within 15 seconds. The
confirmation timer starts after the robot finishes speaking its warning.
Targeted forgetting reports the exact fact removed and leaves other memories
untouched.

The private JSON file defaults to
`~/.local/share/picarxtalk/important_memories.json`, is limited to 24 entries,
and supplies up to six relevant facts to Codex or Ollama for each question.
English keywords, Mandarin character pairs, fact categories, and global answer
preferences are matched locally, so retrieval adds no model request. Passwords,
PINs, API keys, tokens, private keys, seed phrases, and payment identifiers are
not stored.

```bash
CHAT_MEMORY_ENABLED=0 ./run_19v2.sh
CHAT_MEMORY_FILE="$HOME/robot-memory.json" CHAT_MEMORY_MAX_ITEMS=12 ./run_19v2.sh
CHAT_MEMORY_RELEVANT_MAX_ITEMS=4 ./run_19v2.sh
```

## Transcription Quality

The default local transcription profile keeps the fast multilingual `base`
model while improving English and Mandarin recognition with phrase-level
hotwords, Traditional Chinese normalization, 0.45 seconds of audio preroll, and
more tolerant speech endpoints. It accepts prompts up to 18 seconds.

Add names, places, or technical terms without replacing the built-in vocabulary:

```bash
WHISPER_HOTWORDS_FILE="$HOME/my_robot_words.txt" ./run_19v2.sh
```

The file is UTF-8 text and may contain words or short phrases separated by
spaces or newlines. For maximum local accuracy at higher latency, the installed
`small` model remains available:

```bash
WHISPER_MODEL=small WHISPER_BEAM_SIZE=2 ./run_19v2.sh
```

For a quiet speaker, lower `VOICE_START_RMS` from `420` toward `380`. In a noisy
room, raise it instead. Increase `END_SILENCE_SECONDS` above `0.55` if natural
pauses still split a prompt.

## Pikachu Display

Both supported LCD sizes use the same animated Pikachu renderer. The nine moods
have distinct expressions, posture, ear poses, and scenery while retaining the
lower subtitle area for English, Traditional Chinese, and mixed-language
responses.

## Test

```bash
.venv-whisper/bin/python -m unittest -v test_19v2_runtime.py
```
