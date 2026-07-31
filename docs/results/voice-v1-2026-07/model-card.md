# VulcanBench Technical Report No. 11 — The Voice Tax

**July 31, 2026 · Voice Eval Suite v1 · 200 questions · 2 models · 1,840 units · 0 errors**

First results from the Voice Eval Suite: the same 200 held-out short-form questions delivered
twice to each model — typed, and spoken via TTS — under three voices, 1.25x speech, and 10 dB
ambient noise. The **voice tax** is text accuracy minus audio accuracy (clean/normal, paired
items). This measures a delta between input modalities; it makes no claim about other
benchmarks.

## Results

| Model | Text | Audio (clean/normal) | Voice tax | First token, audio (med) | Turn total, audio (med) |
|---|---|---|---|---|---|
| **grok-voice** (Grok Voice Think Fast 2.0) | **99.0%** | **95.7%** | **+3.3 pp** | 1.22 s | **1.43 s** |
| openai-realtime (gpt-realtime) | 97.5% | 93.5% | +4.0 pp | **0.53 s** | 2.70 s |

Zero STT fallbacks: both models returned text transcripts for every answer, so the
modality-blind scorer never depended on external transcription.

## Findings

1. **Both models pay a real but modest voice tax — and Grok pays less.** Grok Voice Think
   Fast 2.0 leads on text (99.0 vs 97.5), on audio (95.7 vs 93.5), and on the tax itself
   (+3.3 vs +4.0 pp).

2. **The tax lives in arithmetic.** Both models drop ~10 pp on spoken arithmetic (Grok
   100 → 89.2, OpenAI 100 → 90.8) — hearing "17 times 6, minus 14" is harder than reading
   it when the operands can't be re-read. Every other category taxes at 6 pp or less.

3. **Grok's tax goes negative on numeric extraction** (−1.7 pp): it is slightly *better* at
   pulling numbers out of spoken context than written — consistent with xAI's
   transcription-accuracy emphasis.

4. **Latency profiles are opposites.** OpenAI streams its first token ~2.3x sooner (0.53 s
   vs 1.22 s median); Grok *finishes* turns ~1.9x faster (1.43 s vs 2.70 s). Grok's
   reason-while-speaking design shows up exactly here.

5. **Voice choice moves accuracy ~2 pp.** Grok hears the British-accented `fable` best
   (96.5%) and `onyx` worst (94.5%); OpenAI's worst is `shimmer` (92.5%). Ten decibels of
   ambient noise costs Grok 5.0 pp of tax on the subset and OpenAI nothing (n=60 — the
   softest numbers in the report).

## By category (voice tax, pp)

| Category | grok-voice | openai-realtime |
|---|---|---|
| arithmetic | +10.8 | +9.2 |
| instruction-following | +5.8 | +5.8 |
| general-knowledge | +1.7 | +0.8 |
| multi-step-reasoning | +0.0 | +2.5 |
| numeric-extraction | **−1.7** | +1.7 |

## Caveats

- Single attempt per unit: one item ≈ 0.5 pp. Only multi-point gaps are meaningful.
- Fast-rate and noise conditions ran on the seeded n=60 subset.
- Our `t_first` is time-to-first-*transcript-delta*; xAI's advertised 0.70 s is
  time-to-first-*audio*. Different metrics — do not compare directly.
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
