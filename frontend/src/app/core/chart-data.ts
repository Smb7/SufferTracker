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

export interface SankeyNode { x: number; y: number; h: number; color: string; label: string; count: number; }
export interface SankeyRibbon { d: string; color: string; }
export interface SankeyLayout { nodes: SankeyNode[]; ribbons: SankeyRibbon[]; height: number; }

export function sankeyLayout(jobs: ChartJob[]): SankeyLayout {
  const height = 220; const width = 640; const nodeWidth = 110; const leftX = 16; const rightX = width - nodeWidth - 16;
  const outcomes = [
    { label: 'Applied', count: countOf(jobs, 'Applied'), color: STATUS_COLORS['Applied'] },
    { label: 'Interview', count: countOf(jobs, 'Interview'), color: STATUS_COLORS['Interview'] },
    { label: 'Offer', count: countOf(jobs, 'JobOffer'), color: STATUS_COLORS['JobOffer'] },
    { label: 'Rejected', count: countOf(jobs, 'Rejected'), color: STATUS_COLORS['Rejected'] },
    { label: 'Ghosted', count: countOf(jobs, 'Ghosted'), color: STATUS_COLORS['Ghosted'] }
  ];
  const total = Math.max(1, jobs.length);
  const available = height - (outcomes.length - 1) * 10;
  const rawHeights = outcomes.map(outcome => (outcome.count / total) * available);
  const scaled = scaleWithMinimum(rawHeights, 16, available);

  let offsetRight = 0;
  const nodes: SankeyNode[] = [];
  const slices: { top: number; bottom: number }[] = [];
  outcomes.forEach((outcome, index) => {
    nodes.push({ x: rightX, y: offsetRight, h: scaled[index], color: outcome.color, label: outcome.label, count: outcome.count });
    slices.push({ top: offsetRight, bottom: offsetRight + scaled[index] });
    offsetRight += scaled[index] + 10;
  });

  const stackHeight = Math.max(1, offsetRight - 10);
  const leftNodeHeight = Math.max(48, stackHeight);
  const leftY = Math.max(0, (height - leftNodeHeight) / 2);
  nodes.unshift({ x: leftX, y: leftY, h: leftNodeHeight, color: '#20201f', label: 'Applied', count: jobs.length });

  const ribbons: SankeyRibbon[] = outcomes.map((_, index) => {
    const share = ((slices[index].bottom - slices[index].top) / stackHeight) * leftNodeHeight;
    const sliceTop = slices.slice(0, index).reduce((sum, slice) => sum + (slice.bottom - slice.top), 0) / stackHeight * leftNodeHeight;
    const midX = (leftX + nodeWidth + rightX) / 2;
    const d = `M ${leftX + nodeWidth},${round(sliceTop)} C ${midX},${round(sliceTop)} ${midX},${round(slices[index].top)} ${rightX},${round(slices[index].top)} L ${rightX},${round(slices[index].bottom)} C ${midX},${round(slices[index].bottom)} ${midX},${round(sliceTop + share)} ${leftX + nodeWidth},${round(sliceTop + share)} Z`;
    return { d, color: outcomes[index].color };
  });
  return { nodes, ribbons, height };
}

function round(value: number): number { return Math.round(value * 100) / 100; }
function startOfDay(time: number): number { const date = new Date(time); date.setHours(0, 0, 0, 0); return date.getTime(); }
function startOfWeek(time: number): number { const date = new Date(time); return startOfDay(date.getTime()) - ((date.getDay() + 6) % 7) * 86400000; }
function monthKey(date: Date): string { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`; }
function scaleWithMinimum(raw: number[], minimum: number, available: number): number[] {
  const clamped = raw.map(value => Math.max(minimum, value));
  let overflow = clamped.reduce((sum, value) => sum + value, 0) - available;
  if (overflow <= 0) return clamped;
  const flexible = clamped.map((value, index) => ({ value, index })).filter(item => item.value > minimum + 1);
  const flexTotal = flexible.reduce((sum, item) => sum + item.value, 0);
  for (const item of flexible) {
    const cut = Math.min(clamped[item.index] - minimum, overflow * (clamped[item.index] / Math.max(1, flexTotal)));
    clamped[item.index] -= cut;
    overflow -= cut;
  }
  return clamped;
}
