# VulcanBench Technical Report No. 11: Grok Voice Think Fast 2.0 vs GPT Realtime

**July 31, 2026 · Voice Eval Suite v1 · 200 questions · 2 models · 1,840 units · 0 errors**

First results from the Voice Eval Suite. The same 200 held-out questions went to each model
twice, typed and spoken via TTS, under three voices, 1.25x speech, and 10 dB ambient noise.
The **voice tax** is text accuracy minus audio accuracy (clean/normal, paired items). This
measures a delta between input modalities; it makes no claim about other benchmarks.

## Results

| Model | Text | Audio | Voice tax | First token (audio) | Turn total (audio) |
|---|---|---|---|---|---|
| **grok-voice** (Grok Voice Think Fast 2.0) | **99.0%** | **95.7%** | **+3.3 pp** | 1.22 s | **1.43 s** |
| openai-realtime (gpt-realtime) | 97.5% | 93.5% | +4.0 pp | **0.53 s** | 2.70 s |

Zero STT fallbacks: both models returned transcripts for every answer, so the scorer never
depended on external transcription.

## Findings

1. **Both models pay a real but modest voice tax; Grok pays less.** It leads on text, on
   audio, and on the tax itself.

2. **The tax lives in arithmetic.** Both models drop about 10 pp on spoken arithmetic (Grok
   100 to 89.2, OpenAI 100 to 90.8). Spoken operands can't be re-read. Every other category
   taxes 6 pp or less.

3. **Grok's tax goes negative on numeric extraction** (-1.7 pp): slightly better at pulling
   numbers out of spoken context than written.

4. **Latency profiles are opposites.** OpenAI streams its first token 2.3x sooner (0.53 s vs
   1.22 s median); Grok finishes turns 1.9x faster (1.43 s vs 2.70 s).

5. **Voice choice moves accuracy about 2 pp.** Grok hears `fable` best and `onyx` worst;
   OpenAI's worst is `shimmer`. Noise costs Grok 5.0 pp of tax and OpenAI none (n=60, the
   softest numbers in the report).

## By category (voice tax, pp)

| Category | grok-voice | openai-realtime |
|---|---|---|
| arithmetic | +10.8 | +9.2 |
| instruction-following | +5.8 | +5.8 |
| general-knowledge | +1.7 | +0.8 |
| multi-step-reasoning | +0.0 | +2.5 |
| numeric-extraction | **-1.7** | +1.7 |

## Caveats

- Single attempt per unit: one item is about 0.5 pp. Only multi-point gaps are meaningful.
- Fast-rate and noise conditions ran on the seeded n=60 subset.
- Our `t_first` is time to first transcript delta; xAI's advertised 0.70 s is time to first
  audio. Different metrics; do not compare directly.
- Two models; Gemini Live and Qwen3-Omni adapters exist but did not run (keys not provisioned).

## Reproducibility

Suite `voice-v1` at commit `7391391` (v0.8.0). Full manifest (TTS voices, judge
`anthropic:claude-opus-5`, STT pin, seed 20260729, question-file sha256) in
`run-manifest.json`; per-unit rows in `runs/voice-v1-run-001/results.jsonl` (local).
Question set, rubric, and noise-clip provenance: `tasks/voice-v1/`.

```
vulcanbench voice run -m grok-voice,openai-realtime
vulcanbench voice report runs/voice-<id>
```
