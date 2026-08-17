import Link from 'next/link'
import { buttonVariants } from '@/components/ui/button'
import PipelineFlow, { type PipelineStage } from '@/components/PipelineFlow'
import RunTrace from '@/components/RunTrace'
import ArchitectureDiagram from '@/components/ArchitectureDiagram'

function StatusBadge({ label, punched }: { label: string; punched: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-[10px] tracking-wide uppercase ${
        punched ? 'text-card-stock-success' : 'text-card-stock-accent'
      }`}
    >
      {punched ? (
        <span aria-hidden="true" className="h-2 w-2 rounded-full border-2 border-card-stock-success" />
      ) : (
        <span aria-hidden="true" className="h-2 w-2 border border-card-stock-muted bg-card-stock-muted" />
      )}
      {label}
    </span>
  )
}

const LIFECYCLE: PipelineStage[] = [
  { id: 'orchestrator', label: 'Runtime', status: 'live' },
  { id: 'agent', label: 'Agent', status: 'live' },
  { id: 'gateway', label: 'Gateway', status: 'live' },
  { id: 'guardrails', label: 'Guardrails', status: 'planned' },
  { id: 'response', label: 'Response', status: 'live' },
]

const SHIPPING = [
  {
    label: 'Runtime & Auth',
    detail: 'Projects, runs, and a real execution timeline behind Supabase Auth and Row-Level Security.',
  },
  {
    label: 'Tool Calling',
    detail: 'Register a REST tool, invoke it directly, see status and latency. SQL, Python and GitHub adapters share the same interface.',
  },
]

const BUILDING_NOW = {
  label: 'Memory',
  detail:
    'Session memory scoped to a conversation, long-term semantic recall in Qdrant. Spec is written — this is the next build.',
}

const FEATURED_PILLARS = [
  {
    label: 'Tool Calling',
    status: 'LIVE' as const,
    body: "Register any REST endpoint against a project and it's callable inside a run — request, response, and latency, all visible in the Tool Manager. SQL, Python, and GitHub adapters share the same interface, built one at a time.",
  },
  {
    label: 'Memory',
    status: 'BUILDING NOW' as const,
    body: "Session memory scoped to a conversation, long-term semantic recall in Qdrant once a run is over. The design is written — this is what's being built next.",
  },
]

const REMAINING_PILLARS = [
  {
    label: 'Multi-Agent Orchestration',
    body: 'A Planner, Researcher, Executor, and Verifier coordinated through one runtime, instead of one agent doing everything alone.',
  },
  {
    label: 'Retrieval (RAG)',
    body: 'Hybrid search over your own documents, with citations attached to every answer that used them.',
  },
  {
    label: 'Guardrails',
    body: 'Catch a prompt injection or a malformed output before it ships, not after.',
  },
  {
    label: 'Evaluation',
    body: 'Run a golden dataset against every change and get a quality score before it reaches production.',
  },
  {
    label: 'Observability',
    body: "A full trace of every run — every tool call, every retrieval, every model call — not just the events on today's timeline.",
  },
  {
    label: 'Cost & Token Control',
    body: "Response caching, context compression, and model routing, so a run's cost is a decision, not a surprise.",
  },
]

const PLANNED = [
  { label: 'Multi-Agent Orchestration', detail: 'Planner, Researcher, Executor and Verifier coordinated through one runtime.' },
  { label: 'Advanced RAG', detail: 'Hybrid search, citations, retrieval-chunk compression.' },
  { label: 'Guardrails', detail: 'Prompt-injection detection, PII masking, policy checks.' },
  { label: 'Evaluation', detail: 'Golden-dataset regression tests, quality scoring.' },
  { label: 'Observability', detail: 'Full execution traces, tool logs, latency capture.' },
  { label: 'Prompt Management', detail: 'Versioned templates with test-run.' },
  { label: 'Token Optimization', detail: 'Response caching, context compression, model routing.' },
  { label: 'Deployment', detail: 'Docker image build and publish, cloud targets.' },
  { label: 'Cost Analytics', detail: 'Per-run token, latency and cost breakdown.' },
]

export default function LandingPage() {
  return (
    <>
      <header className="sticky top-0 z-10 flex min-h-14 flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-border bg-background/85 px-6 py-3 backdrop-blur-md">
        <a href="#top" className="flex items-baseline gap-2">
          <span className="font-heading text-sm font-bold tracking-tight text-primary sm:text-base">MAIP</span>
          <span className="hidden text-[10px] tracking-wide text-muted-foreground uppercase sm:inline">
            Multi-Agent Intelligence Platform
          </span>
        </a>
        <nav className="flex items-center gap-6">
          <a href="#architecture" className="hidden text-sm text-muted-foreground transition-colors hover:text-foreground sm:inline">
            How it works
          </a>
          <a href="#capabilities" className="hidden text-sm text-muted-foreground transition-colors hover:text-foreground sm:inline">
            Capabilities
          </a>
          <a href="#roadmap" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
            Roadmap
          </a>
          <Link href="/login" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
            Log in
          </Link>
          <Link href="/signup" className={buttonVariants({ size: 'sm' })}>
            Get started
          </Link>
        </nav>
      </header>

      <main id="top" className="mx-auto w-full min-w-0 max-w-5xl px-6 py-16 sm:py-24">
        <div className="max-w-2xl">
          <h1 className="font-heading text-4xl leading-[1.02] font-bold tracking-tight uppercase sm:text-6xl">
            Build AI applications you can actually understand.
          </h1>
          <p className="mt-5 text-lg text-muted-foreground">
            Orchestrate agents, ground them in your data, secure their actions, evaluate their
            behavior, and see exactly what happened in every run.
          </p>
          <div className="mt-8 flex gap-3">
            <Link href="/signup" className={buttonVariants()}>
              Get started
            </Link>
            <Link href="/login" className={buttonVariants({ variant: 'outline' })}>
              Log in
            </Link>
          </div>
          <p className="mt-6 border-t border-border pt-4 text-sm text-muted-foreground">
            Not another agent framework — the control plane underneath the one you already have.
          </p>
        </div>

        <div className="punch-corner-lg card-stack-shadow mt-[80px] grid gap-8 overflow-x-auto border border-border bg-card p-8 sm:grid-cols-2 sm:mt-[120px]">
          <div>
            <p className="mb-6 text-[10px] tracking-wide text-muted-foreground uppercase">Request lifecycle</p>
            <PipelineFlow stages={LIFECYCLE} />
          </div>
          <RunTrace />
        </div>

        <div className="mt-[80px] grid gap-8 border-y border-border py-10 sm:mt-[120px] sm:grid-cols-2 sm:gap-12">
          <div>
            <h2 className="font-heading text-sm font-bold tracking-wide text-muted-foreground uppercase">What this isn&apos;t</h2>
            <p className="mt-2 text-lg text-foreground">
              A workflow builder, or a replacement for LangGraph, n8n, or whatever&apos;s already
              orchestrating your agents.
            </p>
          </div>
          <div>
            <h2 className="font-heading text-sm font-bold tracking-wide text-muted-foreground uppercase">What this is</h2>
            <p className="mt-2 text-lg text-foreground">
              The control plane those tools run on top of — memory, tool calling, guardrails,
              evaluation, and cost accounting your orchestration layer doesn&apos;t provide on its own.
            </p>
          </div>
        </div>

        <div id="architecture" className="mt-[80px] scroll-mt-20 sm:mt-[120px]">
          <h2 className="font-heading text-2xl font-bold uppercase">How it works</h2>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            One runtime coordinates every call a run makes, and everything it does converges on a
            trace you can read afterward. Hover a piece to see how it fits.
          </p>
          <div className="mt-8">
            <ArchitectureDiagram />
          </div>
        </div>

        <div id="capabilities" className="mt-[80px] scroll-mt-20 sm:mt-[120px]">
          <h2 className="font-heading text-2xl font-bold uppercase">The eight building blocks</h2>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            Multi-agent orchestration, retrieval, memory, tool calling, guardrails, evaluation,
            observability, and cost control — one runtime, not eight separate services.
          </p>

          <div className="mt-8 grid gap-6 sm:grid-cols-2">
            {FEATURED_PILLARS.map((pillar) => (
              <div key={pillar.label} className="accent-line-t card-hover border border-border bg-card p-6">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-heading text-lg font-bold uppercase">{pillar.label}</p>
                  <StatusBadge label={pillar.status} punched={pillar.status === 'LIVE'} />
                </div>
                <p className="mt-2 text-sm text-muted-foreground">{pillar.body}</p>
              </div>
            ))}
          </div>

          <div className="mt-10 grid gap-x-8 gap-y-6 border-t border-border pt-8 sm:grid-cols-2">
            {REMAINING_PILLARS.map((pillar) => (
              <div key={pillar.label} className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:gap-4">
                <p className="text-sm font-medium text-foreground sm:w-44 sm:shrink-0">{pillar.label}</p>
                <p className="text-sm text-muted-foreground">{pillar.body}</p>
              </div>
            ))}
          </div>
        </div>

        <div id="roadmap" className="mt-[80px] scroll-mt-20 sm:mt-[120px]">
          <h2 className="font-heading text-2xl font-bold uppercase">What&apos;s built, what&apos;s next</h2>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            No panel ships ahead of the backend behind it — here&apos;s exactly where each
            capability stands.
          </p>

          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            {SHIPPING.map((item) => (
              <div
                key={item.label}
                className={`punch-corner card-stack-shadow card-hover bg-card-stock p-5 text-card-stock-foreground ${
                  item.label === 'Runtime & Auth' ? 'sm:col-span-2' : ''
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="font-heading text-sm font-bold uppercase">{item.label}</p>
                  <StatusBadge label="SHIPPING" punched />
                </div>
                <p className="mt-2 text-sm text-card-stock-muted">{item.detail}</p>
              </div>
            ))}
          </div>

          <div className="punch-corner card-stack-shadow card-hover mt-4 bg-card-stock p-5 text-card-stock-foreground">
            <div className="flex items-center justify-between gap-2">
              <p className="font-heading text-sm font-bold uppercase">{BUILDING_NOW.label}</p>
              <StatusBadge label="BUILDING NOW" punched={false} />
            </div>
            <p className="mt-2 text-sm text-card-stock-muted">{BUILDING_NOW.detail}</p>
          </div>

          <div className="mt-8 border border-border">
            <p className="border-b border-border px-5 py-3 text-xs tracking-wide text-muted-foreground uppercase">
              Undrafted — planned
            </p>
            <ul>
              {PLANNED.map((item, index) => (
                <li
                  key={item.label}
                  className={`flex flex-col gap-1 px-5 py-4 sm:flex-row sm:items-baseline sm:gap-6 ${
                    index !== PLANNED.length - 1 ? 'border-b border-border' : ''
                  }`}
                >
                  <p className="text-sm font-medium text-foreground sm:w-56 sm:shrink-0">{item.label}</p>
                  <p className="text-sm text-muted-foreground">{item.detail}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="punch-corner-lg card-stack-shadow mt-[80px] flex flex-col items-start gap-6 border border-border bg-card p-8 sm:mt-[120px] sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-heading text-2xl font-bold uppercase">Start on the control plane</h2>
            <p className="mt-2 max-w-md text-muted-foreground">
              Create a project, send a run, watch the trace land in the timeline.
            </p>
          </div>
          <Link href="/signup" className={buttonVariants({ size: 'lg' })}>
            Get started
          </Link>
        </div>
      </main>

      <footer className="border-t border-border px-6 py-6">
        <p className="text-xs text-muted-foreground">© 2026 MAIP — Multi-Agent Intelligence Platform</p>
      </footer>
    </>
  )
}
