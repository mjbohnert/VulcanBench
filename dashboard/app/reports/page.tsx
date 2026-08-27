import Link from "next/link";
import { REPO } from "@/lib/api";

// Numbered technical reports live as model cards in the repo under
// docs/results/<dir>/. This index mirrors docs/results/README.md; the featured
// report also embeds its chart from /public/report-assets.
interface Report {
  no: number;
  title: string;
  dir?: string; // local model-card directory (linked on GitHub)
  url?: string; // external link (published on vulcanbench.com), preferred when set
  date: string;
  blurb: string;
  chart?: string;
}

const SITE = "https://vulcanbench.com/benchmarks";

// The featured report is local (this checkout); the rest are the most recent
// reports as published on vulcanbench.com, which is the source of truth for
// report numbering. The full archive lives at vulcanbench.com/benchmarks.
const REPORTS: Report[] = [
  {
    no: 18,
    title: "GLM 5.3 in ZCode vs. a bare-bones harness",
    dir: "v3-glm53-2026-08",
    date: "August 2026 · Harness Study No. 03",
    blurb:
      "The same GLM 5.3 on the identical v3 suite, run two ways: VulcanBench's uniform loop on the raw z.ai API, and Z.ai's own ZCode harness on a GLM Coding Plan. A 21.8-point pass@1 gap at max effort (65.2% API vs 87.0% ZCode), opposite effort curves, and a clean split in failure mode: every raw-API failure is a wall-clock timeout, every ZCode failure a wrong answer.",
    chart: "/report-assets/v3-glm53-harness.png",
  },
  {
    no: 17,
    title: "Qwen3.8-27B across the effort knob",
    url: `${SITE}/17-qwen38-27b-effort.html`,
    date: "August 2026",
    blurb:
      "The open-weights Qwen3.8-27B on v3, measured across its effort settings.",
  },
  {
    no: 16,
    title: "Grok 4.6: xAI CLI vs Cursor vs a bare-bones loop",
    url: `${SITE}/16-grok46-grok-build.html`,
    date: "August 2026 · Harness Study No. 02",
    blurb:
      "The same Grok 4.6 through three harnesses: xAI's own agent CLI, Cursor, and a deliberately minimal reference loop.",
  },
  {
    no: 15,
    title: "Grok 4.6 in Cursor vs. a bare-bones harness",
    url: `${SITE}/15-grok46-cursor-harness.html`,
    date: "August 2026 · Harness Study No. 01",
    blurb:
      "The first harness study, and the template for Report No. 18: the same Grok 4.6 through Cursor and through a minimal reference loop.",
  },
];

function cardUrl(dir?: string): string {
  return dir ? `https://github.com/${REPO}/blob/main/docs/results/${dir}/model-card.md` : SITE;
}

function dirUrl(dir?: string): string {
  return dir ? `https://github.com/${REPO}/tree/main/docs/results/${dir}` : SITE;
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
              href={r.url ?? cardUrl(r.dir)}
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

        <div className="mt-8">
          <a
            href={SITE + ".html"}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex h-10 items-center rounded-full border border-white/20 px-6 text-sm hover:bg-white/5"
          >
            Browse all reports on vulcanbench.com &rarr;
          </a>
        </div>

        <p className="mt-10 text-xs text-zinc-500">
          Subscription-harness results (for example ZCode in Report No. 18) measure a model
          plus its product harness and must never be added to a raw-API leaderboard. See each
          model card&apos;s caveats.
        </p>
      </div>
    </div>
  );
}
