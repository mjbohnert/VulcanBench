import Link from "next/link";
import { REPO } from "@/lib/api";

// Numbered technical reports live as model cards in the repo under
// docs/results/<dir>/. This index mirrors docs/results/README.md; the featured
// report also embeds its chart from /public/report-assets.
interface Report {
  no: number;
  title: string;
  dir: string;
  date: string;
  blurb: string;
  chart?: string;
}

const REPORTS: Report[] = [
  {
    no: 13,
    title: "GLM 5.3: model versus harness",
    dir: "v3-glm53-2026-08",
    date: "August 2026",
    blurb:
      "The same GLM 5.3 on the identical v3 suite, run two ways: VulcanBench's uniform loop on the raw z.ai API, and Z.ai's own ZCode harness on a GLM Coding Plan. A 21.8-point pass@1 gap at max effort (65.2% API vs 87.0% ZCode), opposite effort curves, and a clean split in failure mode: every raw-API failure is a wall-clock timeout, every ZCode failure a wrong answer.",
    chart: "/report-assets/v3-glm53-harness.png",
  },
  {
    no: 12,
    title: "Qwen3.8-Max across the effort knob",
    dir: "v3-qwen38-max-2026-08",
    date: "August 2026",
    blurb:
      "First full v3 measurement of Alibaba's Qwen3.8-Max at repeat-3. The reasoning knob runs backwards: low leads xhigh by 26 points, and every failure at higher effort is unfinished work, not wrong work.",
  },
  {
    no: 11,
    title: "Grok Voice Think Fast 2.0 vs GPT Realtime",
    dir: "voice-v1-2026-07",
    date: "July 2026",
    blurb:
      "The voice track: two realtime speech models on spoken software-engineering prompts, scored on transcript-level correctness and latency.",
  },
  {
    no: 10,
    title: "Claude Opus 5 across the effort knob",
    dir: "v3-opus5-effort-2026-07",
    date: "July 2026",
    blurb:
      "Opus 5's effort curve on v3: a 9-point inversion from low to xhigh, the first report to document reasoning effort trading capability for unfinished runs under a fixed budget.",
  },
  {
    no: 9,
    title: "Does training-data contamination move Claude Opus 5's score?",
    dir: "v4-contamination-2026-07",
    date: "July 2026",
    blurb:
      "A controlled contamination study on the v4 suite, measuring how much exposure to a task's upstream fix changes the score.",
  },
  {
    no: 4,
    title: "Grok 4.5 vs Claude Fable 5 vs GPT-5.6 Sol",
    dir: "v3-3way-2026-07",
    date: "July 2026",
    blurb:
      "A three-way frontier comparison on v3 across pass@1, cost, and speed.",
  },
];

function cardUrl(dir: string): string {
  return `https://github.com/${REPO}/blob/main/docs/results/${dir}/model-card.md`;
}

function dirUrl(dir: string): string {
  return `https://github.com/${REPO}/tree/main/docs/results/${dir}`;
}

export default function Reports() {
  const [featured, ...rest] = REPORTS;

  return (
    <div className="min-h-screen bg-zinc-950 text-white p-8 font-sans">
      <div className="max-w-5xl mx-auto">
        <div className="flex justify-between items-baseline mb-2">
          <h1 className="text-4xl font-semibold tracking-tight">Reports</h1>
          <Link href="/" className="text-sm text-zinc-400 hover:text-white">
            &larr; Home
          </Link>
        </div>
        <p className="text-sm text-zinc-400 max-w-2xl mb-10">
          Numbered technical reports from full suite runs. Each is a point-in-time
          snapshot with a model card, machine-readable JSON, and a branded chart, all
          reproducible from the recorded runs.
        </p>

        {/* Featured (latest) */}
        <section className="mb-14 border border-white/10 rounded-2xl overflow-hidden bg-zinc-900/40">
          {featured.chart && (
            <a href={dirUrl(featured.dir)} target="_blank" rel="noopener noreferrer">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={featured.chart}
                alt={`Report No. ${featured.no} chart`}
                className="w-full border-b border-white/10 bg-[#fcfcfb]"
              />
            </a>
          )}
          <div className="p-8">
            <div className="flex items-center gap-3 mb-3">
              <span className="uppercase tracking-[3px] text-xs text-emerald-500">
                Report No. {featured.no}
              </span>
              <span className="text-xs text-zinc-500">{featured.date}</span>
            </div>
            <h2 className="text-2xl font-semibold tracking-tight">{featured.title}</h2>
            <p className="mt-3 text-sm text-zinc-400 max-w-3xl leading-relaxed">
              {featured.blurb}
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <a
                href={cardUrl(featured.dir)}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex h-10 items-center rounded-full bg-white px-6 text-sm font-medium text-black hover:bg-zinc-200"
              >
                Read the model card
              </a>
              <a
                href={dirUrl(featured.dir)}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex h-10 items-center rounded-full border border-white/20 px-6 text-sm hover:bg-white/5"
              >
                Data &amp; chart
              </a>
            </div>
          </div>
        </section>

        {/* Back catalog */}
        <div className="space-y-3">
          {rest.map((r) => (
            <a
              key={r.no}
              href={cardUrl(r.dir)}
              target="_blank"
              rel="noopener noreferrer"
              className="block border border-white/10 rounded-xl p-5 hover:bg-white/5 transition-colors"
            >
              <div className="flex items-baseline gap-3">
                <span className="text-xs text-emerald-500 tracking-[2px] shrink-0">
                  No. {r.no}
                </span>
                <h3 className="text-base font-medium tracking-tight">{r.title}</h3>
                <span className="ml-auto text-xs text-zinc-500 shrink-0">{r.date}</span>
              </div>
              <p className="mt-2 text-sm text-zinc-400 leading-relaxed">{r.blurb}</p>
            </a>
          ))}
        </div>

        <p className="mt-12 text-xs text-zinc-500">
          Subscription-harness results (for example ZCode in Report No. 13) measure a model
          plus its product harness and must never be added to a raw-API leaderboard. See each
          model card&apos;s caveats.
        </p>
      </div>
    </div>
  );
}
