import { Component } from '@angular/core';
import { NgFor, NgIf } from '@angular/common';
import { RouterLink } from '@angular/router';
import {
  bucketSegments, ChartJob, cumulativeSeries, funnelSteps, jobsInColumn, kanbanColumns,
  pipelineStats, sankeyLayout, stackBuckets, STATUS_COLORS
} from '../core/chart-data';

const COMPANIES = [
  'Acme Robotics', 'Nova Systems', 'Vertex Labs', 'Copperline', 'Northwind Data', 'Bluepeak Media',
  'Ironwood Health', 'Lumen Analytics', 'Quill & Co', 'Harborlight', 'Summit Fintech', 'Driftwood Studio',
  'Kestrel AI', 'Maple & Main', 'Solstice Energy', 'Pinewood Games', 'Atlas Freight', 'Juniper Labs',
  'Redshift Optics', 'Fern & Field'
];
const TITLES = [
  'Senior Backend Engineer', 'Frontend Developer II', 'Full-Stack Engineer', 'Data Analyst',
  'DevOps Engineer', 'Product Designer', 'QA Automation Lead', 'Mobile Engineer', 'ML Engineer',
  'Solutions Architect', 'Engineering Manager', 'Platform Engineer', 'Security Analyst',
  'Site Reliability Engineer', 'Technical Program Manager'
];

/** Fixed status mix so every visit tells the same story: 100 applications, realistic outcomes. */
const STATUS_MIX: { status: ChartJob['status']; count: number }[] = [
  { status: 'Applied', count: 30 },
  { status: 'Interview', count: 24 },
  { status: 'JobOffer', count: 6 },
  { status: 'Rejected', count: 29 },
  { status: 'Ghosted', count: 11 }
];

function mulberry32(seed: number): () => number {
  return () => {
    seed |= 0; seed = seed + 0x6D2B79F5 | 0;
    let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

interface DemoJob extends ChartJob { company: string; title: string; }

function generateSampleJobs(): DemoJob[] {
  const random = mulberry32(20260825);
  const statuses: ChartJob['status'][] = [];
  for (const entry of STATUS_MIX)
    for (let i = 0; i < entry.count; i++) statuses.push(entry.status);
  for (let i = statuses.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [statuses[i], statuses[j]] = [statuses[j], statuses[i]];
  }
  const now = Date.now();
  return statuses.map((status, index) => {
    const applied = new Date(now - Math.floor(random() * 69) * 86400000 - Math.floor(random() * 20) * 3600000);
    return {
      status,
      interviewRound: status === 'Interview' ? 1 + Math.floor(random() * 3) : undefined,
      appliedAtUtc: applied.toISOString(),
      company: COMPANIES[Math.floor(random() * COMPANIES.length)],
      title: TITLES[(index * 7 + Math.floor(random() * 3)) % TITLES.length]
    };
  });
}

@Component({
  standalone: true,
  selector: 'st-demo-showcase',
  imports: [NgFor, NgIf],
  template: `
    <section class="demo-showcase panel">
      <div class="panel-heading">
        <div><div class="eyebrow">Live product tour · sample data</div><h2>Smoke's workspace — 100 applications</h2></div>
        <div class="view-switch inline-switch"><button *ngFor="let view of views" [class.selected]="view === selected" (click)="selected = view">{{ view }}</button></div>
      </div>

      @switch (selected) {
        @case ('Pulse') {
          <div class="dashboard-grid tour-grid">
            <div class="pipeline-bars">
              @for (item of pipeline; track item.label) {
                <div class="pipeline-row"><div class="row-meta"><span>{{ item.label }}</span><b>{{ item.count }}</b></div><div class="bar-track"><div class="bar-fill" [style.width.%]="item.width" [class]="item.color"></div></div></div>
              }
            </div>
            <div class="stack-wrap">
              <div class="stat-mini-row"><span>Active</span><b>{{ activeCount }}</b><span>Response rate</span><b>{{ responseRate }}%</b><span>Offers</span><b>{{ offerCount }}</b></div>
              <p class="subtle">Pulse is the landing view: stage counts, response health, and momentum at a glance.</p>
            </div>
          </div>
        }
        @case ('Kanban') {
          <div class="kanban">
            @for (column of columns; track columnKey(column)) {
              <div class="kanban-column">
                <div class="row-meta"><span>{{ column.label }}</span><b>{{ jobsIn(column).length }}</b></div>
                @for (job of first(jobsIn(column), 3); track $index) {
                  <div class="kanban-card"><strong>{{ job.company }}</strong><span>{{ job.title }}<em class="kanban-round" *ngIf="job.status === 'Interview' && job.interviewRound"> R{{ job.interviewRound }}</em></span></div>
                }
                <div class="kanban-empty" *ngIf="jobsIn(column).length > 3">+ {{ jobsIn(column).length - 3 }} more in the app</div>
                <div class="kanban-empty" *ngIf="!jobsIn(column).length">Nothing here yet</div>
              </div>
            }
          </div>
          <p class="subtle flow-footnote">Drag cards between columns to update a status. Interview splits into configurable rounds.</p>
        }
        @case ('Sankey flow') {
          <svg class="sankey-figure" [attr.viewBox]="'0 0 ' + sankey.width + ' ' + sankey.height" role="img" aria-label="Sample application flow sankey diagram">
            <path *ngFor="let ribbon of sankey.ribbons" [attr.d]="ribbon.d" [attr.fill]="ribbon.color" opacity=".3"/>
            <g *ngFor="let node of sankey.nodes">
              <rect [attr.x]="node.x" [attr.y]="node.y" width="110" [attr.height]="node.h" rx="6" [attr.fill]="node.color" opacity=".85"/>
              <text [attr.x]="node.x + node.w / 2" [attr.y]="node.y + node.h / 2 - 2" text-anchor="middle" class="sankey-label">{{ node.label }}</text>
              <text [attr.x]="node.x + node.w / 2" [attr.y]="node.y + node.h / 2 + 13" text-anchor="middle" class="sankey-count">{{ node.count }}</text>
            </g>
          </svg>
        }
        @case ('Funnel') {
          <div class="funnel">
            @for (step of funnel; track step.label) {
              <div class="funnel-step" [class]="'funnel-step ' + step.stepClass"><span>{{ step.label }}</span><b>{{ step.count }}</b><i class="funnel-rate">{{ step.pct }}%</i></div>
            }
          </div>
        }
        @case ('Cumulative') {
          <svg class="sankey-figure" viewBox="0 0 640 200" role="img" aria-label="Sample cumulative applications over time">
            <line x1="28" y1="170" x2="632" y2="170" class="axis-line"/><line x1="28" y1="10" x2="28" y2="170" class="axis-line"/>
            <path [attr.d]="cumulative.area" fill="#ed6b3f" opacity=".14"/>
            <polyline [attr.points]="cumulative.points" fill="none" stroke="#ed6b3f" stroke-width="2.5" stroke-linejoin="round"/>
            <circle *ngFor="let point of cumulative.dots" [attr.cx]="point.x" [attr.cy]="point.y" r="3" fill="#ed6b3f"/>
            <text x="24" y="18" text-anchor="end" class="axis-text">{{ cumulative.max }}</text>
            <text x="24" y="172" text-anchor="end" class="axis-text">0</text>
            <text x="30" y="190" class="axis-text">{{ cumulative.firstLabel }}</text>
            <text x="330" y="190" text-anchor="middle" class="axis-text">{{ cumulative.midLabel }}</text>
            <text x="630" y="190" text-anchor="end" class="axis-text">{{ cumulative.lastLabel }}</text>
          </svg>
        }
        @case ('Stacked bar') {
          <div class="stack-wrap">
            <div class="stack-cols">
              @for (bucket of buckets; track bucket.label) {
                <div class="stack-col" [title]="bucket.label + ': ' + bucket.total"><div class="stack-seg" *ngFor="let seg of segments(bucket)" [style.height.%]="seg.pct" [class]="seg.cls"></div></div>
              }
            </div>
            <div class="stack-labels"><span class="stack-label" *ngFor="let bucket of buckets">{{ bucket.label }}</span></div>
            <div class="legend-row"><span class="legend-chip" *ngFor="let item of legend"><i class="legend-swatch" [style.background]="item.color"></i>{{ item.label }}</span></div>
          </div>
        }
      }
    </section>
    <p class="subtle demo-showcase-note">This is the real interface running on a sample workspace — create an account and your board starts empty, ready for your own hunt.</p>
  `
})
export class DemoShowcaseComponent {
  readonly views = ['Pulse', 'Kanban', 'Sankey flow', 'Funnel', 'Cumulative', 'Stacked bar'] as const;
  selected: (typeof this.views)[number] = 'Pulse';
  readonly sampleJobs: DemoJob[] = generateSampleJobs();

  get pipeline() { return pipelineStats(this.sampleJobs); }
  get activeCount(): number { return this.sampleJobs.filter(job => !['Rejected', 'Ghosted', 'JobOffer'].includes(job.status)).length; }
  get offerCount(): number { return this.sampleJobs.filter(job => job.status === 'JobOffer').length; }
  get responseRate(): number {
    const responded = this.sampleJobs.filter(job => ['Interview', 'JobOffer', 'Rejected'].includes(job.status)).length;
    return this.sampleJobs.length ? Math.round((responded / this.sampleJobs.length) * 100) : 0;
  }
  get columns() { return kanbanColumns(3); }
  jobsIn(column: ReturnType<typeof kanbanColumns>[number]) { return jobsInColumn(this.sampleJobs, column); }
  first<T>(items: T[], count: number): T[] { return items.slice(0, count); }
  columnKey(column: ReturnType<typeof kanbanColumns>[number]): string { return column.round ? `${column.status}-${column.round}` : column.label; }
  get funnel() { return funnelSteps(this.sampleJobs); }
  get cumulative() { return cumulativeSeries(this.sampleJobs); }
  get buckets() { return stackBuckets(this.sampleJobs, 'week'); }
  segments(bucket: ReturnType<typeof stackBuckets>[number]) { return bucketSegments(this.buckets, bucket); }
  get sankey() { return sankeyLayout(this.sampleJobs, 3); }
  get legend() { return Object.keys(STATUS_COLORS).map(status => ({ label: status === 'JobOffer' ? 'Job offer' : status, color: STATUS_COLORS[status] })); }
}
