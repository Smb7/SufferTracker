import { Component, OnInit } from '@angular/core';
import { DatePipe, NgFor, NgIf } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Job, JobStatus, Preferences } from '../core/models';
import { JobsService } from '../core/jobs.service';
import { AuthService } from '../core/auth.service';
import { PreferencesService } from '../core/preferences.service';

interface KanbanColumn { label: string; status: JobStatus; round?: number; }
interface StackBucket { label: string; counts: Record<string, number>; total: number; }
interface SankeyNode { x: number; y: number; h: number; color: string; label: string; count: number; }
interface SankeyRibbon { d: string; color: string; }

const STATUS_COLORS: Record<string, string> = { Waiting: '#ed6b3f', Interview: '#8d7de1', JobOffer: '#72aa77', Rejected: '#bbb9b1', Ghosted: '#8b8780' };

@Component({ standalone: true, imports: [NgFor, NgIf, DatePipe, RouterLink], template: `
  <header class="page-header"><div><div class="eyebrow">{{ today | date:'EEEE, MMMM d' }}</div><h1>Good {{ greeting }}, {{ firstName }}.</h1><p class="subtle">Here is the shape of your search right now.</p></div><a routerLink="/jobs" class="primary-button">+ Add application</a></header>
  <section class="stat-grid"><div class="stat-card accent"><span class="stat-label">Active pipeline</span><strong>{{ activeCount }}</strong><span class="trend">↑ {{ activeCount ? '12' : '0' }}% <small>vs last month</small></span></div><div class="stat-card"><span class="stat-label">Interviews</span><strong>{{ interviewCount }}</strong><span class="stat-note">{{ interviewCount ? 'Keep the momentum' : 'Your next one is waiting' }}</span></div><div class="stat-card"><span class="stat-label">Response rate</span><strong>{{ responseRate }}<small>%</small></strong><span class="stat-note">Across all applications</span></div><div class="stat-card"><span class="stat-label">Offers</span><strong>{{ offerCount }}</strong><span class="stat-note">The finish line is visible</span></div></section>
  <div class="view-switch"><button *ngFor="let view of views" [class.selected]="visualizer === view.key" (click)="selectView(view.key)">{{ view.label }}</button></div>
  <div class="dashboard-grid" *ngIf="visualizer === 'pulse'">
    <section class="panel pipeline-panel"><div class="panel-heading"><div><div class="eyebrow">Pipeline pulse</div><h2>Applications by stage</h2></div><a routerLink="/jobs" class="text-link">View all →</a></div><div class="pipeline-bars"><div class="pipeline-row" *ngFor="let item of pipeline"><div class="row-meta"><span>{{ item.label }}</span><b>{{ item.count }}</b></div><div class="bar-track"><div class="bar-fill" [style.width.%]="item.width" [class]="item.color"></div></div></div></div></section>
    <section class="panel activity-panel"><div class="panel-heading"><div><div class="eyebrow">Recent activity</div><h2>Latest updates</h2></div></div><ng-container *ngIf="jobs.length; else emptyActivity"><div class="activity" *ngFor="let job of recentJobs"><span class="activity-dot"></span><div><strong>{{ job.company }}</strong><p>{{ job.title }}</p></div><time>{{ job.updatedAtUtc | date:'MMM d' }}</time></div></ng-container><ng-template #emptyActivity><div class="empty-state">Add your first application to see activity here.</div></ng-template></section>
  </div>
  <ng-template #noJobs><section class="panel visualizer-panel"><div class="empty-state">Add applications to unlock this visualizer.</div></section></ng-template>
  <ng-container *ngIf="jobs.length; else noJobs">
    <section class="panel visualizer-panel kanban-panel" *ngIf="visualizer === 'kanban'"><div class="panel-heading"><div><div class="eyebrow">Drag-ready pipeline</div><h2>Kanban board</h2></div><span class="subtle">Drag cards between columns to update a status.</span></div><div class="kanban"><div class="kanban-column" *ngFor="let column of columns" (dragover)="onDragOver($event)" (dragenter)="dragOver = columnLabel(column)" (dragleave)="clearDragOver(column)" (drop)="onDrop(column, $event)" [class.drag-over]="dragOver === columnLabel(column)"><div class="row-meta"><span>{{ column.label }}</span><b>{{ jobsIn(column).length }}</b></div><div class="kanban-card" *ngFor="let job of jobsIn(column)" draggable="true" (dragstart)="onDragStart(job, $event)" (dragend)="draggingId = null"><strong>{{ job.company }}</strong><span>{{ job.title }}<em class="kanban-round" *ngIf="job.status === 'Interview' && job.interviewRound"> R{{ job.interviewRound }}</em></span></div><div class="kanban-empty" *ngIf="!jobsIn(column).length">Drop here</div></div></div></section>
    <section class="panel visualizer-panel" *ngIf="visualizer === 'sankey'"><div class="panel-heading"><div><div class="eyebrow">Flow of the hunt</div><h2>Applied to outcome</h2></div></div><svg class="sankey-figure" [attr.viewBox]="'0 0 640 ' + sankey.height" role="img" aria-label="Application flow sankey diagram"><path *ngFor="let ribbon of sankey.ribbons" [attr.d]="ribbon.d" [attr.fill]="ribbon.color" opacity=".3"/><g *ngFor="let node of sankey.nodes"><rect [attr.x]="node.x" [attr.y]="node.y" width="110" [attr.height]="node.h" rx="6" [attr.fill]="node.color" opacity=".85"/><text [attr.x]="sankeyTextX(node.x)" [attr.y]="node.y + node.h / 2 - 2" text-anchor="middle" class="sankey-label">{{ node.label }}</text><text [attr.x]="sankeyTextX(node.x)" [attr.y]="node.y + node.h / 2 + 13" text-anchor="middle" class="sankey-count">{{ node.count }}</text></g></svg><p class="subtle flow-footnote">Band thickness follows how many applications ended in each outcome.</p></section>
    <section class="panel visualizer-panel" *ngIf="visualizer === 'funnel'"><div class="panel-heading"><div><div class="eyebrow">Conversion health</div><h2>Application funnel</h2></div></div><div class="funnel"><div class="funnel-step one"><span>Applied</span><b>{{ jobs.length }}</b><i class="funnel-rate">100%</i></div><div class="funnel-step two"><span>Responded</span><b>{{ respondedCount }}</b><i class="funnel-rate">{{ rateOf(respondedCount, jobs.length) }}</i></div><div class="funnel-step three"><span>Interviewed</span><b>{{ interviewCount }}</b><i class="funnel-rate">{{ rateOf(interviewCount, jobs.length) }}</i></div><div class="funnel-step four"><span>Offer</span><b>{{ offerCount }}</b><i class="funnel-rate">{{ rateOf(offerCount, jobs.length) }}</i></div></div></section>
    <section class="panel visualizer-panel chart-figure" *ngIf="visualizer === 'line'"><div class="panel-heading"><div><div class="eyebrow">Momentum</div><h2>Cumulative applications · last 8 weeks</h2></div><span class="period-pill">Total {{ jobs.length }}</span></div><svg class="sankey-figure" [attr.viewBox]="'0 0 640 200'" role="img" aria-label="Cumulative applications over time"><line x1="28" y1="170" x2="632" y2="170" class="axis-line"/><line x1="28" y1="10" x2="28" y2="170" class="axis-line"/><path [attr.d]="cumulative.area" fill="#ed6b3f" opacity=".14"/><polyline [attr.points]="cumulative.points" fill="none" stroke="#ed6b3f" stroke-width="2.5" stroke-linejoin="round"/><circle *ngFor="let point of cumulative.dots" [attr.cx]="point.x" [attr.cy]="point.y" r="3" fill="#ed6b3f"/><text x="24" y="18" text-anchor="end" class="axis-text">{{ cumulative.max }}</text><text x="24" y="172" text-anchor="end" class="axis-text">0</text><text x="30" y="190" class="axis-text">{{ cumulative.firstLabel }}</text><text x="330" y="190" text-anchor="middle" class="axis-text">{{ cumulative.midLabel }}</text><text x="630" y="190" text-anchor="end" class="axis-text">{{ cumulative.lastLabel }}</text></svg></section>
    <section class="panel visualizer-panel" *ngIf="visualizer === 'bar'"><div class="panel-heading"><div><div class="eyebrow">Search rhythm</div><h2>Application outcomes</h2></div><div class="view-switch inline-switch"><button [class.selected]="stackMode === 'week'" (click)="stackMode = 'week'">Weekly</button><button [class.selected]="stackMode === 'month'" (click)="stackMode = 'month'">Monthly</button></div></div><div class="stack-wrap"><div class="stack-cols"><div class="stack-col" *ngFor="let bucket of stackBuckets" [title]="bucket.label + ': ' + bucket.total"><div class="stack-seg" *ngFor="let seg of bucketSegments(bucket)" [style.height.%]="seg.pct" [class]="seg.cls"></div></div></div><div class="stack-labels"><span class="stack-label" *ngFor="let bucket of stackBuckets">{{ bucket.label }}</span></div><div class="legend-row"><span class="legend-chip" *ngFor="let item of legend"><i class="legend-swatch" [style.background]="item.color"></i>{{ item.label }}</span></div></div></section>
  </ng-container>
  <section class="panel chart-panel" *ngIf="visualizer === 'pulse'"><div class="panel-heading"><div><div class="eyebrow">Search rhythm</div><h2>Cumulative momentum</h2></div><span class="period-pill">Last 8 weeks · All statuses</span></div><div class="chart" *ngIf="jobs.length; else emptyPulse"><div class="y-axis"><span>{{ cumulative.max }}</span><span>4</span><span>2</span><span>0</span></div><div class="chart-area"><div class="grid-line" *ngFor="let line of [1,2,3,4]"></div><div class="columns"><div class="column" *ngFor="let point of cumulative.weekBars"><div class="column-fill" [style.height.%]="point"></div></div></div></div></div><ng-template #emptyPulse><div class="empty-state">Add applications to see your momentum curve.</div></ng-template></section>` })
export class DashboardComponent implements OnInit {
  jobs: Job[] = []; prefs: Preferences | null = null;
  visualizer = 'pulse'; stackMode: 'week' | 'month' = 'week'; dragOver = ''; draggingId: string | null = null;
  views = [{ key: 'pulse', label: 'Pulse' }, { key: 'kanban', label: 'Kanban' }, { key: 'sankey', label: 'Sankey flow' }, { key: 'funnel', label: 'Funnel' }, { key: 'line', label: 'Cumulative' }, { key: 'bar', label: 'Stacked bar' }];
  today = new Date();
  constructor(private readonly jobsService: JobsService, private readonly auth: AuthService, private readonly preferences: PreferencesService) {}
  ngOnInit(): void {
    this.jobsService.list().subscribe(jobs => this.jobs = jobs);
    this.preferences.get().subscribe(prefs => { this.prefs = prefs; if (this.views.some(view => view.key === prefs.defaultView)) this.visualizer = prefs.defaultView; });
  }
  selectView(key: string): void {
    this.visualizer = key;
    if (!this.prefs || this.prefs.defaultView === key) return;
    const updated = { ...this.prefs, defaultView: key };
    this.preferences.update(updated).subscribe(value => this.prefs = value);
  }
  get greeting(): string { const hour = new Date().getHours(); return hour < 12 ? 'morning' : hour < 18 ? 'afternoon' : 'evening'; }
  get firstName(): string { return this.auth.user()?.displayName.split(' ')[0] || 'there'; }
  get activeCount(): number { return this.jobs.filter(job => !['Rejected', 'Ghosted', 'JobOffer'].includes(job.status)).length; }
  get interviewCount(): number { return this.jobs.filter(job => job.status === 'Interview').length; }
  get offerCount(): number { return this.jobs.filter(job => job.status === 'JobOffer').length; }
  get rejectedCount(): number { return this.jobs.filter(job => job.status === 'Rejected').length; }
  get ghostedCount(): number { return this.jobs.filter(job => job.status === 'Ghosted').length; }
  get waitingCount(): number { return this.jobs.filter(job => job.status === 'Waiting').length; }
  get respondedCount(): number { return this.interviewCount + this.offerCount + this.rejectedCount; }
  get responseRate(): number { return this.rateNumber(this.respondedCount, this.jobs.length); }
  get recentJobs(): Job[] { return [...this.jobs].sort((a, b) => b.updatedAtUtc.localeCompare(a.updatedAtUtc)).slice(0, 5); }
  get pipeline(): { label: string; status: JobStatus; count: number; width: number; color: string }[] { const values = [{ label: 'Waiting', status: 'Waiting' as JobStatus, color: 'orange' }, { label: 'Interview', status: 'Interview' as JobStatus, color: 'purple' }, { label: 'Job offer', status: 'JobOffer' as JobStatus, color: 'green' }, { label: 'Rejected', status: 'Rejected' as JobStatus, color: 'gray' }]; const max = Math.max(1, ...values.map(value => this.countOf(value.status))); return values.map(value => ({ ...value, count: this.countOf(value.status), width: (this.countOf(value.status) / max) * 100 })); }
  get columns(): KanbanColumn[] {
    const rounds = Math.min(10, Math.max(1, this.prefs?.interviewRounds ?? 3));
    const interview: KanbanColumn[] = rounds > 1
      ? Array.from({ length: rounds }, (_, index) => ({ label: `Interview ${index + 1}`, status: 'Interview' as JobStatus, round: index + 1 }))
      : [{ label: 'Interview', status: 'Interview' }];
    return [{ label: 'Waiting', status: 'Waiting' }, ...interview, { label: 'Job offer', status: 'JobOffer' }, { label: 'Ghosted', status: 'Ghosted' }, { label: 'Rejected', status: 'Rejected' }];
  }
  get legend(): { label: string; color: string }[] { return Object.keys(STATUS_COLORS).map(status => ({ label: this.labelOf(status), color: STATUS_COLORS[status] })); }
  get cumulative(): { points: string; area: string; dots: { x: number; y: number }[]; max: number; firstLabel: string; midLabel: string; lastLabel: string; weekBars: number[] } {
    const empty = { points: '', area: '', dots: [] as { x: number; y: number }[], max: 0, firstLabel: '', midLabel: '', lastLabel: '', weekBars: [] as number[] };
    if (!this.jobs.length) return empty;
    const days = 56; const dayMs = 86400000;
    const end = startOfDay(Date.now()) + dayMs;
    const start = end - days * dayMs;
    const sorted = [...this.jobs].sort((a, b) => a.appliedAtUtc.localeCompare(b.appliedAtUtc));
    let running = sorted.filter(job => Date.parse(job.appliedAtUtc) < start).length;
    const series: number[] = [];
    for (let index = 0; index < days; index++) {
      const dayStart = start + index * dayMs;
      const dayEnd = start + (index + 1) * dayMs;
      running += sorted.filter(job => { const time = Date.parse(job.appliedAtUtc); return time >= dayStart && time < dayEnd; }).length;
      series.push(running);
    }
    const max = Math.max(1, ...series);
    const left = 34; const top = 12; const bottom = 168; const width = 596;
    const dots = series.map((value, index) => ({ x: left + (index / (days - 1)) * width, y: bottom - (value / max) * (bottom - top) }));
    const points = dots.map(point => `${round(point.x)},${round(point.y)}`).join(' ');
    const area = `M ${round(dots[0].x)},${bottom} L ${points.split(' ').join(' L ')} L ${round(dots[dots.length - 1].x)},${bottom} Z`;
    const fmt = (time: number) => new Date(time).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    const weekBars = series.slice().reverse().filter((_, index) => index % 7 === 0).reverse().map((value, _, all) => all.length ? (value / Math.max(1, ...all)) * 100 : 0);
    return { points, area, dots, max, firstLabel: fmt(start), midLabel: fmt(start + (days / 2) * dayMs), lastLabel: fmt(end - dayMs), weekBars };
  }
  get stackBuckets(): StackBucket[] {
    const buckets = new Map<string, StackBucket>();
    const now = new Date();
    if (this.stackMode === 'month') {
      for (let index = 5; index >= 0; index--) { const date = new Date(now.getFullYear(), now.getMonth() - index, 1); buckets.set(monthKey(date), { label: date.toLocaleDateString(undefined, { month: 'short' }), counts: {}, total: 0 }); }
    } else {
      const monday = startOfDay(now.getTime()) - ((now.getDay() + 6) % 7) * 86400000;
      for (let index = 7; index >= 0; index--) { const time = monday - index * 7 * 86400000; buckets.set(weekKey(time), { label: new Date(time).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }), counts: {}, total: 0 }); }
    }
    for (const job of this.jobs) {
      const key = this.stackMode === 'month' ? monthKey(new Date(job.appliedAtUtc)) : weekKey(startOfWeek(Date.parse(job.appliedAtUtc)));
      const bucket = buckets.get(key);
      if (!bucket) continue;
      bucket.counts[job.status] = (bucket.counts[job.status] ?? 0) + 1;
      bucket.total++;
    }
    return [...buckets.values()];
  }
  bucketSegments(bucket: StackBucket): { cls: string; pct: number }[] {
    const max = Math.max(1, ...this.stackBuckets.map(item => item.total));
    return ['Waiting', 'Interview', 'JobOffer', 'Rejected', 'Ghosted'].map(status => ({ cls: `seg-${status.toLowerCase()}`, pct: ((bucket.counts[status] ?? 0) / max) * 100 })).filter(segment => segment.pct > 0);
  }
  get sankey(): { nodes: SankeyNode[]; ribbons: SankeyRibbon[]; height: number } {
    const height = 220; const width = 640; const nodeWidth = 110; const leftX = 16; const rightX = width - nodeWidth - 16;
    const outcomes = [
      { label: 'Waiting', count: this.waitingCount, color: STATUS_COLORS['Waiting'] },
      { label: 'Interview', count: this.interviewCount, color: STATUS_COLORS['Interview'] },
      { label: 'Offer', count: this.offerCount, color: STATUS_COLORS['JobOffer'] },
      { label: 'Rejected', count: this.rejectedCount, color: STATUS_COLORS['Rejected'] },
      { label: 'Ghosted', count: this.ghostedCount, color: STATUS_COLORS['Ghosted'] }
    ];
    const total = Math.max(1, this.jobs.length);
    const available = height - (outcomes.length - 1) * 10;
    let offsetRight = 0;
    const nodes: SankeyNode[] = [];
    const slices: { yTop: number; yBottom: number }[] = [];
    const rawHeights = outcomes.map(outcome => (outcome.count / total) * available);
    const scaled = scaleWithMinimum(rawHeights, 16, available);
    outcomes.forEach((outcome, index) => {
      const nodeHeight = scaled[index];
      const y = offsetRight;
      nodes.push({ x: rightX, y, h: nodeHeight, color: outcome.color, label: outcome.label, count: outcome.count });
      slices.push({ yTop: y, yBottom: y + nodeHeight });
      offsetRight += nodeHeight + 10;
    });
    const leftNodeHeight = Math.max(48, offsetRight - 10);
    const leftY = Math.max(0, (height - leftNodeHeight) / 2);
    nodes.unshift({ x: leftX, y: leftY, h: leftNodeHeight, color: '#20201f', label: 'Applied', count: this.jobs.length });
    const ribbons: SankeyRibbon[] = outcomes.map((_, index) => {
      const share = ((slices[index].yBottom - slices[index].yTop) / Math.max(1, offsetRight - 10)) * leftNodeHeight;
      const sliceTop = leftY + slices.slice(0, index).reduce((sum, slice) => sum + (slice.yBottom - slice.yTop), 0) / Math.max(1, offsetRight - 10) * leftNodeHeight;
      const midX = (leftX + nodeWidth + rightX) / 2;
      const d = `M ${leftX + nodeWidth},${round(sliceTop)} C ${midX},${round(sliceTop)} ${midX},${round(slices[index].yTop)} ${rightX},${round(slices[index].yTop)} L ${rightX},${round(slices[index].yBottom)} C ${midX},${round(slices[index].yBottom)} ${midX},${round(sliceTop + share)} ${leftX + nodeWidth},${round(sliceTop + share)} Z`;
      return { d, color: outcomes[index].color };
    });
    return { nodes, ribbons, height };
  }
  sankeyTextX(x: number): number { return x + 55; }
  jobsIn(column: KanbanColumn): Job[] {
    return this.jobs.filter(job => {
      if (job.status !== column.status) return false;
      if (column.status !== 'Interview') return true;
      if (!column.round) return true;
      return (job.interviewRound ?? 1) === column.round;
    });
  }
  onDragStart(job: Job, event: DragEvent): void { this.draggingId = job.id; event.dataTransfer?.setData('text/plain', job.id); }
  onDragOver(event: DragEvent): void { event.preventDefault(); if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'; }
  clearDragOver(_column: KanbanColumn): void { this.dragOver = ''; }
  onDrop(column: KanbanColumn, event: DragEvent): void {
    event.preventDefault(); this.dragOver = '';
    const id = event.dataTransfer?.getData('text/plain') || this.draggingId;
    const job = this.jobs.find(item => item.id === id);
    this.draggingId = null;
    if (!job || (job.status === column.status && (job.interviewRound ?? 1) === (column.round ?? 1))) return;
    const interviewRound = column.status === 'Interview' ? (column.round ?? job.interviewRound ?? 1) : undefined;
    this.jobsService.update(job.id, { company: job.company, title: job.title, description: job.description, skills: job.skills, pay: job.pay, location: job.location, nickname: job.nickname, status: column.status, interviewRound }).subscribe({ next: updated => Object.assign(job, updated), error: () => {} });
  }
  jobsFor(status: JobStatus): Job[] { return this.jobs.filter(job => job.status === status); }
  countOf(status: JobStatus): number { return this.jobs.filter(job => job.status === status).length; }
  rateOf(part: number, whole: number): string { return `${this.rateNumber(part, whole)}%`; }
  rateNumber(part: number, whole: number): number { return whole ? Math.round((part / whole) * 100) : 0; }
  labelOf(status: string): string { return status === 'JobOffer' ? 'Job offer' : status; }
  columnLabel(column: KanbanColumn): string { return column.round ? `${column.status}-${column.round}` : column.label; }
}

function round(value: number): number { return Math.round(value * 100) / 100; }
function startOfDay(time: number): number { const date = new Date(time); date.setHours(0, 0, 0, 0); return date.getTime(); }
function startOfWeek(time: number): number { const date = new Date(time); return startOfDay(date.getTime()) - ((date.getDay() + 6) % 7) * 86400000; }
function weekKey(time: number): string { return new Date(time).toISOString().slice(0, 10); }
function monthKey(date: Date): string { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`; }
function scaleWithMinimum(raw: number[], minimum: number, available: number): number[] {
  let clamped = raw.map(value => Math.max(minimum, value));
  let overflow = clamped.reduce((sum, value) => sum + value, 0) - available;
  if (overflow <= 0) return clamped;
  const flexible = raw.map((value, index) => ({ value, index })).filter(item => clamped[item.index] > minimum + 1);
  const flexTotal = flexible.reduce((sum, item) => sum + clamped[item.index], 0);
  for (const item of flexible) { const cut = Math.min(clamped[item.index] - minimum, overflow * (clamped[item.index] / Math.max(1, flexTotal))); clamped[item.index] -= cut; overflow -= cut; }
  return clamped;
}
