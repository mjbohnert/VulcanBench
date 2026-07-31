# Voice Eval Suite v1

Measures the performance delta between a model answering an eval as **text**
versus the identical eval delivered as **spoken audio**. The headline metric
is the **voice tax**: text accuracy minus audio accuracy on the clean/normal
condition, over paired items.

> **Framing note.** This suite measures a delta between input modalities for
> the same model. It makes no claim about the validity of other benchmarks.

> **First results** (July 31, 2026, Report No. 11 — see
> `docs/results/voice-v1-2026-07/`): Grok Voice Think Fast 2.0 scores
> 99.0% text / 95.7% audio (voice tax **+3.3 pp**); GPT Realtime 97.5% /
> 93.5% (**+4.0 pp**). Both models lose ~10 pp on spoken arithmetic; Grok
> gains 1.7 pp on numeric extraction. 1,840 units, 0 errors, 0 STT
> fallbacks. Gemini Live and Qwen3-Omni have not yet run.

## Question set

`tasks/voice-v1/questions.jsonl` — 200 original short-form questions with
objectively checkable answers, 40 per category:

| Category | Probe |
|---|---|
| `arithmetic` | mental math |
| `multi-step-reasoning` | short word/logic problems |
| `general-knowledge` | stable factual recall |
| `instruction-following` | exact sequences and constrained outputs |
| `numeric-extraction` | numbers embedded in spoken context |

All items were written for this suite in July 2026 (see
`decontamination_notes` in `tasks/voice-v1/suite.json`); none are drawn from
public benchmarks — TTS-rendered public evals are trivially trainable.

## Audio pipeline

- **Master format**: 24 kHz mono PCM16 WAV (OpenAI TTS native output and
  OpenAI Realtime's input rate). Gemini Live requires 16 kHz, so that
  adapter downsamples at send time. Both rates are in the run manifest.
- **TTS**: OpenAI `tts-1` (honours a numeric `speed` parameter, which makes
  the fast condition well-defined). Voices: `onyx` (male), `shimmer`
  (female), `fable` (British-accented). Swappable via
  `harness/voice/tts.py::TTSProvider`.
- **Conditions**: full question set on clean audio at normal rate for each
  of the 3 voices; a seeded subset (n=60, seed `20260729`) additionally runs
  1.25x rate and a 10 dB SNR ambient-noise condition (clip provenance:
  `tasks/voice-v1/noise/README.md`; per-item clip chosen by hashing the
  item id).
- **Cache**: rendered audio lands in `audio_cache/voice-v1/` keyed by
  `(question_id, voice, rate, noise)`, with a sha256 of the question text
  per render — editing a question invalidates its audio. Reruns never
  re-synthesize fresh files.

## Models

Adapters implement `answer_text(question)` and `answer_audio(wav_path)`
(`harness/voice/adapters.py`):

| Adapter | Endpoint | Text baseline path |
|---|---|---|
| `openai-realtime` | OpenAI Realtime (websocket) | same realtime session, text item |
| `gemini-live` | Gemini Live (websocket) | same live session, text turn |
| `qwen-omni` | Qwen3-Omni via DashScope (SSE) | same endpoint, text content |
| `grok-voice` | xAI Grok Voice realtime (websocket) | same realtime session, text item |

The first three request **text output**, so scoring rarely needs
transcription. `grok-voice` is true speech-to-speech: it answers in audio
in *both* modes (only the input modality differs — the quantity under
measurement); its own transcript is scored, with the pinned STT fallback
(`gpt-4o-transcribe`) when a transcript is absent. Any STT use is recorded
per-row as `transcribed_by`. The grok adapter pins
`grok-voice-think-fast-2.0` explicitly — `grok-voice-latest` aliases 1.0
until 2026-08-05.

API keys (environment, never hardcoded): `OPENAI_API_KEY` (TTS, Realtime,
STT), `GEMINI_API_KEY`, `DASHSCOPE_API_KEY`, `XAI_API_KEY`, plus the judge
provider's key.

## Scoring — one scorer, both modes

`harness/voice/scorer.py::score_response` is the single entry point for both
modalities: normalize (case, punctuation, articles, number-words→digits) →
exact/alias match → pinned LLM judge (default `anthropic:claude-opus-5`,
rubric at `tasks/voice-v1/RUBRIC.md`). Judge model, STT model, TTS voices,
seed, git commit, and question-file hash are all recorded in
`runs/voice-*/manifest.json`.

## Running

```bash
# 1. cheap end-to-end validation (5 questions, one voice, clean only)
vulcanbench voice run -m openai-realtime --dry-run

# 2. pre-render the audio cache (optional; run also renders on demand)
vulcanbench voice render

# 3. full run, resumable — re-invoke with --run-id to skip finished units
vulcanbench voice run -m openai-realtime,gemini-live,qwen-omni,grok-voice

# 4. report: voice tax overall / per category / per condition + latency
vulcanbench voice report runs/voice-<id> -o report.md
```

Determinism: subset sampling is seeded; temperature is 0 where the API
accepts it (recorded per adapter). Latency is reported as median/P95/P99
for both time-to-first-token and total turn time, per mode.
