import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DatePipe, NgFor, NgIf } from '@angular/common';
import { Job, JobStatus, ParsedJob } from '../core/models';
import { JobsService } from '../core/jobs.service';

@Component({ standalone: true, imports: [FormsModule, NgFor, NgIf, DatePipe], template: `
  <header class="page-header"><div><div class="eyebrow">Your workspace</div><h1>Applications</h1><p class="subtle">Turn every opportunity into a next step.</p></div><button class="primary-button" (click)="showCapture = !showCapture">+ Capture job</button></header>
  <section class="capture panel" *ngIf="showCapture"><div class="capture-intro"><div class="eyebrow">New application</div><h2>Start with the messy bit.</h2><p>Paste a job description and we will pull out the useful parts for you to review.</p></div><div class="capture-body"><textarea [(ngModel)]="rawText" placeholder="Paste job description text here..."></textarea><button class="primary-button" (click)="parse()" [disabled]="parsing">{{ parsing ? 'Reading...' : 'Parse details →' }}</button></div><div class="form-error" *ngIf="message">{{ message }}</div><div class="parsed-card" *ngIf="parsed"><div class="eyebrow">Review extracted details</div><h3>{{ parsed.title }} <span>at {{ parsed.company }}</span></h3><p>{{ parsed.location }} · {{ parsed.pay }}</p><button class="secondary-button" (click)="saveParsed()">Save application</button></div></section>
  <div class="filter-row"><div class="filter-tabs"><button *ngFor="let filter of filters" [class.selected]="activeFilter === filter" (click)="activeFilter = filter">{{ filter }} <small>{{ filterCount(filter) }}</small></button></div><input class="search-input" [(ngModel)]="search" placeholder="⌕  Search applications"></div>
  <section class="job-list panel"><div class="list-head"><span>Company / role</span><span>Stage</span><span>Applied</span><span></span></div><div class="job-row" *ngFor="let job of visibleJobs"><div class="company-cell"><span class="company-logo">{{ job.company[0] }}</span><div><strong>{{ job.company }}</strong><p>{{ job.title }}<span *ngIf="job.nickname"> · {{ job.nickname }}</span></p></div></div><span class="status-badge" [class]="job.status.toLowerCase()">{{ label(job.status) }}<small *ngIf="job.interviewRound"> {{ job.interviewRound }}</small></span><time>{{ job.appliedAtUtc | date:'MMM d, y' }}</time><button class="icon-button" (click)="remove(job)">×</button></div><div class="empty-state" *ngIf="!visibleJobs.length">No applications match this view.</div></section>` })
export class JobsComponent implements OnInit {
  jobs: Job[] = []; rawText = ''; parsed: ParsedJob | null = null; parsing = false; showCapture = false; message = ''; search = ''; activeFilter = 'All'; filters = ['All', 'Waiting', 'Interview', 'Job offer', 'Rejected'];
  constructor(private readonly service: JobsService) {}
  ngOnInit(): void { this.refresh(); }
  get visibleJobs(): Job[] { return this.jobs.filter(job => (this.activeFilter === 'All' || this.label(job.status) === this.activeFilter) && `${job.company} ${job.title}`.toLowerCase().includes(this.search.toLowerCase())); }
  parse(): void { if (!this.rawText.trim()) { this.message = 'Paste some job description text first.'; return; } this.parsing = true; this.message = ''; this.service.parseText(this.rawText).subscribe({ next: value => { this.parsed = value; this.parsing = false; }, error: () => { this.message = 'Parsing failed. You can still add the details manually.'; this.parsing = false; } }); }
  saveParsed(): void { if (!this.parsed) return; this.service.create({ ...this.parsed, status: 'Waiting' }).subscribe({ next: () => { this.parsed = null; this.rawText = ''; this.showCapture = false; this.refresh(); }, error: () => this.message = 'Could not save this application.' }); }
  remove(job: Job): void { this.service.delete(job.id).subscribe({ next: () => this.jobs = this.jobs.filter(item => item.id !== job.id) }); }
  refresh(): void { this.service.list().subscribe({ next: jobs => this.jobs = jobs }); }
  filterCount(filter: string): number { return filter === 'All' ? this.jobs.length : this.jobs.filter(job => this.label(job.status) === filter).length; }
  label(status: JobStatus): string { return status === 'JobOffer' ? 'Job offer' : status; }
}
