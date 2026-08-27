import { sankey, sankeyJustify } from 'd3-sankey';
import { JobStatus } from './models';

export interface ChartJob { status: JobStatus; interviewRound?: number | null; appliedAtUtc: string; }

export const STATUS_COLORS: Record<string, string> = { Applied: '#ed6b3f', Waiting: '#ed6b3f', Interview: '#8d7de1', JobOffer: '#72aa77', Rejected: '#bbb9b1', Ghosted: '#8b8780' };

export interface PipelineStat { label: string; status: JobStatus; count: number; width: number; color: string; }

export function countOf(jobs: ChartJob[], status: JobStatus): number {
  return jobs.filter(job => job.status === status).length;
}

export function pipelineStats(jobs: ChartJob[]): PipelineStat[] {
  const definitions = [
    { label: 'Applied', status: 'Applied' as JobStatus, color: 'orange' },
    { label: 'Interview', status: 'Interview' as JobStatus, color: 'purple' },
    { label: 'Job offer', status: 'JobOffer' as JobStatus, color: 'green' },
    { label: 'Rejected', status: 'Rejected' as JobStatus, color: 'gray' }
  ];
  const max = Math.max(1, ...definitions.map(definition => countOf(jobs, definition.status)));
  return definitions.map(definition => ({ ...definition, count: countOf(jobs, definition.status), width: (countOf(jobs, definition.status) / max) * 100 }));
}

export interface KanbanColumnDef { label: string; status: JobStatus; round?: number; }

export function kanbanColumns(interviewRounds: number): KanbanColumnDef[] {
  const rounds = Math.min(10, Math.max(1, interviewRounds));
  const interview: KanbanColumnDef[] = rounds > 1
    ? Array.from({ length: rounds }, (_, index) => ({ label: `Interview ${index + 1}`, status: 'Interview' as JobStatus, round: index + 1 }))
    : [{ label: 'Interview', status: 'Interview' }];
  return [{ label: 'Applied', status: 'Applied' }, ...interview, { label: 'Job offer', status: 'JobOffer' }, { label: 'Ghosted', status: 'Ghosted' }, { label: 'Rejected', status: 'Rejected' }];
}

export function jobsInColumn<T extends ChartJob>(jobs: T[], column: KanbanColumnDef): T[] {
  return jobs.filter(job => {
    if (job.status !== column.status) return false;
    if (column.status !== 'Interview') return true;
    if (!column.round) return true;
    return (job.interviewRound ?? 1) === column.round;
  });
}

export function rateNumber(part: number, whole: number): number { return whole ? Math.round((part / whole) * 100) : 0; }

export function funnelSteps(jobs: ChartJob[]): { label: string; stepClass: string; count: number; pct: number }[] {
  const responded = jobs.filter(job => ['Interview', 'JobOffer', 'Rejected'].includes(job.status)).length;
  const interviewed = countOf(jobs, 'Interview');
  const offered = countOf(jobs, 'JobOffer');
  const total = jobs.length;
  const steps = [
    { label: 'Applied', stepClass: 'one', count: total },
    { label: 'Responded', stepClass: 'two', count: responded },
    { label: 'Interviewed', stepClass: 'three', count: interviewed },
    { label: 'Offer', stepClass: 'four', count: offered }
  ];
  return steps.map(step => ({ ...step, pct: rateNumber(step.count, total) }));
}

export interface CumulativePoint { x: number; y: number; }
export interface CumulativeResult { points: string; area: string; dots: CumulativePoint[]; max: number; firstLabel: string; midLabel: string; lastLabel: string; weekBars: number[]; }

export function cumulativeSeries(jobs: ChartJob[], days = 56): CumulativeResult {
  const empty: CumulativeResult = { points: '', area: '', dots: [], max: 0, firstLabel: '', midLabel: '', lastLabel: '', weekBars: [] };
  if (!jobs.length) return empty;
  const dayMs = 86400000;
  const end = startOfDay(Date.now()) + dayMs;
  const start = end - days * dayMs;
  const sorted = [...jobs].sort((a, b) => a.appliedAtUtc.localeCompare(b.appliedAtUtc));
  let running = sorted.filter(job => Date.parse(job.appliedAtUtc) < start).length;
  const series: number[] = [];
  for (let index = 0; index < days; index++) {
    const dayStart = start + index * dayMs;
    running += sorted.filter(job => { const time = Date.parse(job.appliedAtUtc); return time >= dayStart && time < dayStart + dayMs; }).length;
    series.push(running);
  }
  const max = Math.max(1, ...series);
  const left = 34; const top = 12; const bottom = 168; const width = 596;
  const dots = series.map((value, index) => ({ x: left + (index / (days - 1)) * width, y: bottom - (value / max) * (bottom - top) }));
  const points = dots.map(point => `${round(point.x)},${round(point.y)}`).join(' ');
  const area = `M ${round(dots[0].x)},${bottom} L ${points.split(' ').join(' L ')} L ${round(dots[dots.length - 1].x)},${bottom} Z`;
  const fmt = (time: number) => new Date(time).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  const weekly = series.slice().reverse().filter((_, index) => index % 7 === 0).reverse();
  const weekMax = Math.max(1, ...weekly);
  return { points, area, dots, max, firstLabel: fmt(start), midLabel: fmt(start + (days / 2) * dayMs), lastLabel: fmt(end - dayMs), weekBars: weekly.map(value => (value / weekMax) * 100) };
}

export type StackMode = 'week' | 'month';
export interface StackBucket { label: string; counts: Record<string, number>; total: number; }

export function stackBuckets(jobs: ChartJob[], mode: StackMode): StackBucket[] {
  const buckets = new Map<string, StackBucket>();
  const now = new Date();
  if (mode === 'month') {
    for (let index = 5; index >= 0; index--) {
      const date = new Date(now.getFullYear(), now.getMonth() - index, 1);
      buckets.set(monthKey(date), { label: date.toLocaleDateString(undefined, { month: 'short' }), counts: {}, total: 0 });
    }
  } else {
    const monday = startOfWeek(now.getTime());
    for (let index = 7; index >= 0; index--) {
      const time = monday - index * 7 * 86400000;
      buckets.set(new Date(time).toISOString().slice(0, 10), { label: new Date(time).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }), counts: {}, total: 0 });
    }
  }
  for (const job of jobs) {
    const key = mode === 'month'
      ? monthKey(new Date(job.appliedAtUtc))
      : new Date(startOfWeek(Date.parse(job.appliedAtUtc))).toISOString().slice(0, 10);
    const bucket = buckets.get(key);
    if (!bucket) continue;
    bucket.counts[job.status] = (bucket.counts[job.status] ?? 0) + 1;
    bucket.total++;
  }
  return [...buckets.values()];
}

export function bucketSegments(buckets: StackBucket[], bucket: StackBucket): { cls: string; pct: number }[] {
  const max = Math.max(1, ...buckets.map(item => item.total));
  return ['Applied', 'Waiting', 'Interview', 'JobOffer', 'Rejected', 'Ghosted']
    .map(status => ({ cls: `seg-${status.toLowerCase()}`, pct: ((bucket.counts[status] ?? 0) / max) * 100 }))
    .filter(segment => segment.pct > 0);
}

export interface SankeyNode {
  x: number; y: number; h: number; w: number;
  color: string; label: string; count: number;
  labelX: number; countY: number; labelY: number; anchor: 'start' | 'end';
}
export interface SankeyRibbon { d: string; color: string; }
export interface SankeyLayout { nodes: SankeyNode[]; ribbons: SankeyRibbon[]; height: number; width: number; }

interface FlowNode { id: string; label: string; color: string; fixedValue?: number; }
interface FlowLink { source: string; target: string; value: number; color: string; }

export function sankeyLayout(jobs: ChartJob[], interviewRounds = 3): SankeyLayout {
  const width = 760;
  const height = 340;
  const empty: SankeyLayout = { nodes: [], ribbons: [], width, height };
  if (!jobs.length) return empty;

  const roundOf = (job: ChartJob) => Math.max(0, Math.min(10, job.interviewRound ?? 0));
  const maxRound = Math.min(10, Math.max(interviewRounds, ...jobs.map(roundOf), 0));
  const reached = (stage: number) => jobs.filter(job => roundOf(job) >= stage).length;
  const ended = (status: JobStatus, stage: number) => jobs.filter(job => job.status === status && roundOf(job) === stage).length;

  const nodes: FlowNode[] = [{ id: 'applied', label: 'Applied', color: STATUS_COLORS['Applied'], fixedValue: jobs.length }];
  for (let stage = 1; stage <= maxRound; stage++) {
    if (reached(stage) > 0) nodes.push({ id: `i${stage}`, label: `Interview ${stage}`, color: STATUS_COLORS['Interview'] });
  }
  const terminals: FlowNode[] = [
    { id: 'offer', label: 'Offer', color: STATUS_COLORS['JobOffer'] },
    { id: 'rejected', label: 'Rejected', color: STATUS_COLORS['Rejected'] },
    { id: 'ghosted', label: 'Ghosted', color: STATUS_COLORS['Ghosted'] }
  ];

  const links: FlowLink[] = [];
  const add = (source: string, target: string, value: number, color: string) => { if (value > 0) links.push({ source, target, value, color }); };
  add('applied', 'i1', reached(1), STATUS_COLORS['Interview']);
  add('applied', 'offer', ended('JobOffer', 0), STATUS_COLORS['JobOffer']);
  add('applied', 'rejected', ended('Rejected', 0), STATUS_COLORS['Rejected']);
  add('applied', 'ghosted', ended('Ghosted', 0), STATUS_COLORS['Ghosted']);
  for (let stage = 1; stage <= maxRound; stage++) {
    const id = `i${stage}`;
    if (stage < maxRound) add(id, `i${stage + 1}`, reached(stage + 1), STATUS_COLORS['Interview']);
    add(id, 'offer', ended('JobOffer', stage), STATUS_COLORS['JobOffer']);
    add(id, 'rejected', ended('Rejected', stage), STATUS_COLORS['Rejected']);
    add(id, 'ghosted', ended('Ghosted', stage), STATUS_COLORS['Ghosted']);
  }

  const used = new Set(links.flatMap(link => [link.source, link.target]));
  const graphNodes = nodes.concat(terminals.filter(node => used.has(node.id))).filter(node => used.has(node.id) || node.id === 'applied');
  if (!links.length) {
    const bar = height - 32;
    return { nodes: [{ x: 108, y: 16, w: 18, h: bar, color: STATUS_COLORS['Applied'], label: 'Applied', count: jobs.length, labelX: 96, countY: 16 + bar / 2 - 2, labelY: 16 + bar / 2 + 14, anchor: 'end' }], ribbons: [], width, height };
  }

  const graph = sankey<FlowNode, FlowLink>()
    .nodeId(node => node.id)
    .nodeWidth(18)
    .nodePadding(18)
    .nodeAlign(sankeyJustify)
    .extent([[108, 20], [width - 108, height - 20]])
    .iterations(32)({
      nodes: graphNodes.map(node => ({ ...node })),
      links: links.map(link => ({ ...link }))
    });

  const leftEdge = Math.min(...graph.nodes.map(node => node.x0 ?? 0));
  const laidNodes: SankeyNode[] = graph.nodes.map(node => {
    const x0 = node.x0 ?? 0; const x1 = node.x1 ?? 18; const y0 = node.y0 ?? 0; const y1 = node.y1 ?? 0;
    const left = x0 <= leftEdge + 0.5;
    const cy = (y0 + y1) / 2;
    return {
      x: round(x0), y: round(y0), w: round(x1 - x0), h: Math.max(1, round(y1 - y0)),
      color: node.color, label: node.label, count: Math.round(node.fixedValue ?? node.value ?? 0),
      labelX: round(left ? x0 - 10 : x1 + 10), countY: round(cy - 2), labelY: round(cy + 14),
      anchor: left ? 'end' : 'start'
    };
  });

  const ribbons: SankeyRibbon[] = graph.links.map(link => {
    const source = link.source as FlowNode & { x1?: number };
    const target = link.target as FlowNode & { x0?: number };
    const x0 = source.x1 ?? 0; const x1 = target.x0 ?? 0;
    const half = (link.width ?? 0) / 2;
    const y0 = (link.y0 ?? 0); const y1 = (link.y1 ?? 0);
    const mid = (x0 + x1) / 2;
    const d = `M ${round(x0)},${round(y0 - half)} C ${round(mid)},${round(y0 - half)} ${round(mid)},${round(y1 - half)} ${round(x1)},${round(y1 - half)} L ${round(x1)},${round(y1 + half)} C ${round(mid)},${round(y1 + half)} ${round(mid)},${round(y0 + half)} ${round(x0)},${round(y0 + half)} Z`;
    return { d, color: link.color };
  });

  return { nodes: laidNodes, ribbons, width, height };
}

function round(value: number): number { return Math.round(value * 100) / 100; }
function startOfDay(time: number): number { const date = new Date(time); date.setHours(0, 0, 0, 0); return date.getTime(); }
function startOfWeek(time: number): number { const date = new Date(time); return startOfDay(date.getTime()) - ((date.getDay() + 6) % 7) * 86400000; }
function monthKey(date: Date): string { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`; }

