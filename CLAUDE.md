# VulcanBench — project notes

## Brand: logo & typography

Use these whenever producing anything user-facing or shareable (charts, reports,
social images, docs headers) for VulcanBench.

- **Logo**: [docs/assets/vulcanbench-logo.png](docs/assets/vulcanbench-logo.png)
  — the canonical mark: a white angular layered "V" on a black square
  (1078×1078 PNG, no alpha). Live copy at https://vulcanbench.com/assets/logo.png.
  Present it as a rounded-corner chip (~22% corner radius) next to the wordmark.
  ⚠️ The dashboard favicon (`dashboard/app/favicon.ico`, black circle + white
  triangle) is an outdated placeholder — do NOT use it as the logo.
- **Wordmark**: "VulcanBench" set in **Chakra Petch SemiBold (600)**, black
  (`#0b0b0b`) on light backgrounds, white on dark. Google Fonts family
  "Chakra Petch"; static per-weight TTFs register as separate families
  ("Chakra Petch", "Chakra Petch Medium", "Chakra Petch SemiBold") in
  matplotlib — address them by those names.
- **Headings / display text**: Chakra Petch (Medium for section titles).
- **Secondary / code face**: IBM Plex Mono (400/500) — vulcanbench.com's
  second family.
- **Brand palette**: monochrome black/white. The dashboard app UI accent is
  emerald-500 (`#10b981`), and the dashboard app font is Geist (via
  `next/font`) — those are app-UI choices, not the marketing brand; the
  wordmark face is always Chakra Petch.

## Shareable results charts

The generator for the three-panel suite-v3 results PNG (pass@1 rankings,
speed panel, effort-curve cards, all in brand styling) lives in
[scripts/rankings-chart/](scripts/rankings-chart/) — see its README for
usage, aggregation rules, and asset licenses. Per-lab colors: Anthropic clay
`#D97757`, OpenAI `#10A37F`, DeepSeek `#5786FE`, xAI black `#0A0A0A`,
Moonshot dark slate `#44445E` (official Moonshot black collides with xAI —
slate is the deliberate stand-in). Chart-integrity rules that must survive
edits: per-column run counts (`n=`) and ±1 stderr whiskers stay visible;
partial-coverage columns keep their asterisks; externally sourced columns
(e.g. Opus 5 from Report 10) and list-price cost caveats stay footnoted.
