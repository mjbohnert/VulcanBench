# Voice Eval Suite v1, run report

_Run `voice-v1-run-001` · 200 items · models: grok-voice, openai-realtime · judge anthropic:claude-opus-5 · TTS openai (onyx, shimmer, fable) · seed 20260729_

## Voice tax (text - audio accuracy, clean/normal, paired items)

| Model | Text | Audio (clean/normal) | Voice tax |
|---|---|---|---|
| grok-voice | 99.0% | 95.7% | +3.3 pp |
| openai-realtime | 97.5% | 93.5% | +4.0 pp |

## grok-voice, by category

| Category | Text | Audio | Tax |
|---|---|---|---|
| arithmetic | 100.0% | 89.2% | +10.8 pp |
| general-knowledge | 100.0% | 98.3% | +1.7 pp |
| instruction-following | 100.0% | 94.2% | +5.8 pp |
| multi-step-reasoning | 97.5% | 97.5% | +0.0 pp |
| numeric-extraction | 97.5% | 99.2% | -1.7 pp |

## grok-voice, by condition

| Condition | n | Accuracy | Text acc (same items) | Tax |
|---|---|---|---|---|
| fable_normal_clean | 200 | 96.5% | 99.0% | +2.5 pp |
| onyx_fast_clean | 60 | 96.7% | 98.3% | +1.7 pp |
| onyx_normal_clean | 200 | 94.5% | 99.0% | +4.5 pp |
| onyx_normal_noise10db | 60 | 93.3% | 98.3% | +5.0 pp |
| shimmer_normal_clean | 200 | 96.0% | 99.0% | +3.0 pp |
| text | 200 | 99.0% |, |, |

## grok-voice, latency (seconds)

| Mode | Metric | Median | P95 | P99 |
|---|---|---|---|---|
| text | t_first_s | 0.847 | 1.657 | 2.072 |
| text | t_total_s | 1.041 | 1.956 | 2.158 |
| audio | t_first_s | 1.224 | 2.242 | 3.555 |
| audio | t_total_s | 1.425 | 2.487 | 3.703 |

## openai-realtime, by category

| Category | Text | Audio | Tax |
|---|---|---|---|
| arithmetic | 100.0% | 90.8% | +9.2 pp |
| general-knowledge | 95.0% | 94.2% | +0.8 pp |
| instruction-following | 100.0% | 94.2% | +5.8 pp |
| multi-step-reasoning | 92.5% | 90.0% | +2.5 pp |
| numeric-extraction | 100.0% | 98.3% | +1.7 pp |

## openai-realtime, by condition

| Condition | n | Accuracy | Text acc (same items) | Tax |
|---|---|---|---|---|
| fable_normal_clean | 200 | 93.0% | 97.5% | +4.5 pp |
| onyx_fast_clean | 60 | 91.7% | 93.3% | +1.7 pp |
| onyx_normal_clean | 200 | 95.0% | 97.5% | +2.5 pp |
| onyx_normal_noise10db | 60 | 93.3% | 93.3% | +0.0 pp |
| shimmer_normal_clean | 200 | 92.5% | 97.5% | +5.0 pp |
| text | 200 | 97.5% |, |, |

## openai-realtime, latency (seconds)

| Mode | Metric | Median | P95 | P99 |
|---|---|---|---|---|
| text | t_first_s | 0.296 | 0.437 | 0.625 |
| text | t_total_s | 2.466 | 2.727 | 2.895 |
| audio | t_first_s | 0.528 | 0.874 | 1.1 |
| audio | t_total_s | 2.703 | 3.073 | 3.37 |
