import { Component, OnInit } from '@angular/core';
import { DatePipe, NgFor, NgIf } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Job, JobStatus, Preferences } from '../core/models';
import { JobsService } from '../core/jobs.service';
import { AuthService } from '../core/auth.service';
import { PreferencesService } from '../core/preferences.service';
import {
  bucketSegments, cumulativeSeries, funnelSteps, jobsInColumn, KanbanColumnDef, kanbanColumns,
  pipelineStats, rateNumber, sankeyLayout, stackBuckets, STATUS_COLORS
} from '../core/chart-data';

@Component({ standalone: true, imports: [NgFor, NgIf, DatePipe, RouterLink], template: `
  <header class="page-header"><div><div class="eyebrow">{{ today | date:'EEEE, MMMM d' }}</div><h1>Good {{ greeting }}, {{ firstName }}.</h1><p class="subtle">Here is the shape of your search right now.</p></div><a routerLink="/jobs" class="primary-button">+ Add application</a></header>
  <section class="stat-grid"><div class="stat-card accent"><span class="stat-label">Active pipeline</span><strong>{{ activeCount }}</strong><span class="trend">{{ monthTrend }} <small>applications vs last month</small></span></div><div class="stat-card"><span class="stat-label">Interviews</span><strong>{{ interviewCount }}</strong><span class="stat-note">{{ interviewCount ? 'Keep the momentum' : 'Your next one is waiting' }}</span></div><div class="stat-card"><span class="stat-label">Response rate</span><strong>{{ responseRate }}<small>%</small></strong><span class="stat-note">Across all applications</span></div><div class="stat-card"><span class="stat-label">Offers</span><strong>{{ offerCount }}</strong><span class="stat-note">The finish line is visible</span></div></section>
  <div class="view-switch" *ngIf="loaded"><button *ngFor="let view of views" [class.selected]="visualizer === view.key" (click)="selectView(view.key)">{{ view.label }}</button></div>
  <div class="dashboard-grid" *ngIf="loaded && visualizer === 'pulse'">
    <section class="panel pipeline-panel"><div class="panel-heading"><div><div class="eyebrow">Pipeline pulse</div><h2>Applications by stage</h2></div><a routerLink="/jobs" class="text-link">View all →</a></div><div class="pipeline-bars"><div class="pipeline-row" *ngFor="let item of pipeline"><div class="row-meta"><span>{{ item.label }}</span><b>{{ item.count }}</b></div><div class="bar-track"><div class="bar-fill" [style.width.%]="item.width" [class]="item.color"></div></div></div></div></section>
    <section class="panel activity-panel"><div class="panel-heading"><div><div class="eyebrow">Recent activity</div><h2>Latest updates</h2></div></div><ng-container *ngIf="jobs.length; else emptyActivity"><div class="activity" *ngFor="let job of recentJobs"><span class="activity-dot"></span><div><strong>{{ job.company }}</strong><p>{{ job.title }}</p></div><time>{{ job.updatedAtUtc | date:'MMM d' }}</time></div></ng-container><ng-template #emptyActivity><div class="empty-state">Add your first application to see activity here.</div></ng-template></section>
  </div>
  <ng-template #noJobs><section class="panel visualizer-panel"><div class="empty-state">Add applications to unlock this visualizer.</div></section></ng-template>
  <ng-container *ngIf="loaded && jobs.length; else noJobs">
    <section class="panel visualizer-panel kanban-panel" *ngIf="visualizer === 'kanban'"><div class="panel-heading"><div><div class="eyebrow">Drag-ready pipeline</div><h2>Kanban board</h2></div><span class="subtle">Drag cards between columns to update a status.</span><span class="form-error" *ngIf="dragError">{{ dragError }}</span></div><div class="kanban"><div class="kanban-column" *ngFor="let column of columns" (dragover)="onDragOver($event)" (dragenter)="dragOver = columnKey(column)" (dragleave)="dragOver = ''" (drop)="onDrop(column, $event)" [class.drag-over]="dragOver === columnKey(column)"><div class="row-meta"><span>{{ column.label }}</span><b>{{ jobsIn(column).length }}</b></div><div class="kanban-card" *ngFor="let job of jobsIn(column)" draggable="true" (dragstart)="onDragStart(job, $event)" (dragend)="draggingId = null"><strong>{{ job.company }}</strong><span>{{ job.title }}<em class="kanban-round" *ngIf="job.status === 'Interview' && job.interviewRound"> R{{ job.interviewRound }}</em></span></div><div class="kanban-empty" *ngIf="!jobsIn(column).length">Drop here</div></div></div></section>
    <section class="panel visualizer-panel" *ngIf="visualizer === 'sankey'"><div class="panel-heading"><div><div class="eyebrow">Flow of the hunt</div><h2>Applied to outcome</h2></div></div><svg class="sankey-figure" [attr.viewBox]="'0 0 ' + sankey.width + ' ' + sankey.height" role="img" aria-label="Application flow sankey diagram"><path *ngFor="let ribbon of sankey.ribbons" [attr.d]="ribbon.d" [attr.fill]="ribbon.color" opacity=".3"/><g *ngFor="let node of sankey.nodes"><rect [attr.x]="node.x" [attr.y]="node.y" width="110" [attr.height]="node.h" rx="6" [attr.fill]="node.color" opacity=".85"/><text [attr.x]="node.x + 55" [attr.y]="node.y + node.h / 2 - 2" text-anchor="middle" class="sankey-label">{{ node.label }}</text><text [attr.x]="node.x + 55" [attr.y]="node.y + node.h / 2 + 13" text-anchor="middle" class="sankey-count">{{ node.count }}</text></g></svg><p class="subtle flow-footnote">Band thickness follows how many applications ended in each outcome.</p></section>
    <section class="panel visualizer-panel" *ngIf="visualizer === 'funnel'"><div class="panel-heading"><div><div class="eyebrow">Conversion health</div><h2>Application funnel</h2></div></div><div class="funnel"><div class="funnel-step" *ngFor="let step of funnel" [class]="'funnel-step ' + step.stepClass"><span>{{ step.label }}</span><b>{{ step.count }}</b><i class="funnel-rate">{{ step.pct }}%</i></div></div></section>
    <section class="panel visualizer-panel chart-figure" *ngIf="visualizer === 'line'"><div class="panel-heading"><div><div class="eyebrow">Momentum</div><h2>Cumulative applications · last 8 weeks</h2></div><span class="period-pill">Total {{ jobs.length }}</span></div><svg class="sankey-figure" [attr.viewBox]="'0 0 640 200'" role="img" aria-label="Cumulative applications over time"><line x1="28" y1="170" x2="632" y2="170" class="axis-line"/><line x1="28" y1="10" x2="28" y2="170" class="axis-line"/><path [attr.d]="cumulative.area" fill="#ed6b3f" opacity=".14"/><polyline [attr.points]="cumulative.points" fill="none" stroke="#ed6b3f" stroke-width="2.5" stroke-linejoin="round"/><circle *ngFor="let point of cumulative.dots" [attr.cx]="point.x" [attr.cy]="point.y" r="3" fill="#ed6b3f"/><text x="24" y="18" text-anchor="end" class="axis-text">{{ cumulative.max }}</text><text x="24" y="172" text-anchor="end" class="axis-text">0</text><text x="30" y="190" class="axis-text">{{ cumulative.firstLabel }}</text><text x="330" y="190" text-anchor="middle" class="axis-text">{{ cumulative.midLabel }}</text><text x="630" y="190" text-anchor="end" class="axis-text">{{ cumulative.lastLabel }}</text></svg></section>
    <section class="panel visualizer-panel" *ngIf="visualizer === 'bar'"><div class="panel-heading"><div><div class="eyebrow">Search rhythm</div><h2>Application outcomes</h2></div><div class="view-switch inline-switch"><button [class.selected]="stackMode === 'week'" (click)="stackMode = 'week'">Weekly</button><button [class.selected]="stackMode === 'month'" (click)="stackMode = 'month'">Monthly</button></div></div><div class="stack-wrap"><div class="stack-cols"><div class="stack-col" *ngFor="let bucket of buckets" [title]="bucket.label + ': ' + bucket.total"><div class="stack-seg" *ngFor="let seg of segments(bucket)" [style.height.%]="seg.pct" [class]="seg.cls"></div></div></div><div class="stack-labels"><span class="stack-label" *ngFor="let bucket of buckets">{{ bucket.label }}</span></div><div class="legend-row"><span class="legend-chip" *ngFor="let item of legend"><i class="legend-swatch" [style.background]="item.color"></i>{{ item.label }}</span></div></div></section>
  </ng-container>
  <section class="panel chart-panel" *ngIf="loaded && visualizer === 'pulse' && jobs.length"><div class="panel-heading"><div><div class="eyebrow">Search rhythm</div><h2>Cumulative momentum</h2></div><span class="period-pill">Last 8 weeks · All statuses</span></div><div class="chart"><div class="y-axis"><span>{{ cumulative.max }}</span><span>4</span><span>2</span><span>0</span></div><div class="chart-area"><div class="grid-line" *ngFor="let line of [1,2,3,4]"></div><div class="columns"><div class="column" *ngFor="let point of cumulative.weekBars"><div class="column-fill" [style.height.%]="point"></div></div></div></div></div></section>` })
export class DashboardComponent implements OnInit {
  jobs: Job[] = []; prefs: Preferences | null = null; loaded = false;
  visualizer = 'pulse'; stackMode: 'week' | 'month' = 'week'; dragOver = ''; draggingId: string | null = null; dragError = '';
  views = [{ key: 'pulse', label: 'Pulse' }, { key: 'kanban', label: 'Kanban' }, { key: 'sankey', label: 'Sankey flow' }, { key: 'funnel', label: 'Funnel' }, { key: 'line', label: 'Cumulative' }, { key: 'bar', label: 'Stacked bar' }];
  today = new Date();
  constructor(private readonly jobsService: JobsService, private readonly auth: AuthService, private readonly preferences: PreferencesService) {}
  ngOnInit(): void {
    this.jobsService.list().subscribe(jobs => this.jobs = jobs);
    this.preferences.get().subscribe(prefs => {
      this.prefs = prefs;
      this.visualizer = this.views.some(view => view.key === prefs.defaultView) ? prefs.defaultView : 'pulse';
      this.loaded = true;
    });
  }
  selectView(key: string): void {
    this.visualizer = key;
    if (this.prefs?.defaultView === key) return;
    this.preferences.updateDefaultView(key).subscribe({ next: value => this.prefs = value, error: () => {} });
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
  get responseRate(): number { return rateNumber(this.respondedCount, this.jobs.length); }
  get recentJobs(): Job[] { return [...this.jobs].sort((a, b) => b.updatedAtUtc.localeCompare(a.updatedAtUtc)).slice(0, 5); }
  get monthTrend(): string {
    const now = new Date();
    const thisMonth = this.jobs.filter(job => sameMonth(new Date(job.appliedAtUtc), now)).length;
    const lastMonthDate = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    const lastMonth = this.jobs.filter(job => sameMonth(new Date(job.appliedAtUtc), lastMonthDate)).length;
    if (!lastMonth) return thisMonth ? `↑ ${thisMonth} new` : 'No activity';
    const change = Math.round(((thisMonth - lastMonth) / lastMonth) * 100);
    return change >= 0 ? `↑ ${change}%` : `↓ ${Math.abs(change)}%`;
  }
  get pipeline() { return pipelineStats(this.jobs); }
  get columns(): KanbanColumnDef[] { return kanbanColumns(this.prefs?.interviewRounds ?? 3); }
  get legend() { return Object.keys(STATUS_COLORS).map(status => ({ label: status === 'JobOffer' ? 'Job offer' : status, color: STATUS_COLORS[status] })); }
  get cumulative() { return cumulativeSeries(this.jobs); }
  get buckets() { return stackBuckets(this.jobs, this.stackMode); }
  get funnel() { return funnelSteps(this.jobs); }
  get sankey() { return sankeyLayout(this.jobs, this.prefs?.interviewRounds ?? 3); }
  segments(bucket: ReturnType<typeof stackBuckets>[number]) { return bucketSegments(this.buckets, bucket); }
  jobsIn(column: KanbanColumnDef): Job[] { return jobsInColumn(this.jobs, column); }
  onDragStart(job: Job, event: DragEvent): void { this.draggingId = job.id; event.dataTransfer?.setData('text/plain', job.id); }
  onDragOver(event: DragEvent): void { event.preventDefault(); if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'; }
  onDrop(column: KanbanColumnDef, event: DragEvent): void {
    event.preventDefault(); this.dragOver = '';
    const id = event.dataTransfer?.getData('text/plain') || this.draggingId;
    const job = this.jobs.find(item => item.id === id);
    this.draggingId = null;
    if (!job || (job.status === column.status && (job.interviewRound ?? 1) === (column.round ?? 1))) return;
    const interviewRound = column.status === 'Interview' ? (column.round ?? job.interviewRound ?? 1) : undefined;
    try {
      this.jobsService.update(job.id, { company: job.company, title: job.title, description: job.description, skills: job.skills, pay: job.pay, location: job.location, nickname: job.nickname, statusEvents: job.statusEvents ?? [], status: column.status, interviewRound })
        .subscribe({ next: updated => { Object.assign(job, updated); this.dragError = ''; }, error: error => this.dragError = error.error?.message ?? 'Could not update the status.' });
    } catch (error) {
      this.dragError = (error as Error).message;
    }
  }
  columnKey(column: KanbanColumnDef): string { return column.round ? `${column.status}-${column.round}` : column.label; }
}

function sameMonth(date: Date, reference: Date): boolean { return date.getFullYear() === reference.getFullYear() && date.getMonth() === reference.getMonth(); }
