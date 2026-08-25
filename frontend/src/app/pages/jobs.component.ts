import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DatePipe, NgFor, NgIf } from '@angular/common';
import { Job, JobStatus, ParsedJob } from '../core/models';
import { JobsService } from '../core/jobs.service';
import { PreferencesService } from '../core/preferences.service';

interface EditModel {
  company: string; title: string; description: string; skills: string; pay: string;
  location: string; nickname: string; status: JobStatus; interviewRound: number; appliedDate: string;
}

@Component({ standalone: true, imports: [FormsModule, NgFor, NgIf, DatePipe], template: `
  <header class="page-header"><div><div class="eyebrow">Your workspace</div><h1>Applications</h1><p class="subtle">Turn every opportunity into a next step.</p></div><button class="primary-button" (click)="showCapture = !showCapture">+ Capture job</button></header>
  <section class="capture panel" *ngIf="showCapture"><div class="capture-intro"><div class="eyebrow">New application</div><h2>Start with the messy bit.</h2><p>Paste a link, drop in the description text, or upload a screenshot. We will pull out the useful parts for you to review.</p></div><div class="capture-body"><div class="capture-tabs"><button [class.selected]="captureMode === 'text'" (click)="captureMode = 'text'">Paste text</button><button [class.selected]="captureMode === 'link'" (click)="captureMode = 'link'">Job link</button><button [class.selected]="captureMode === 'screenshot'" (click)="captureMode = 'screenshot'">Screenshot OCR</button></div><textarea *ngIf="captureMode === 'text'" [(ngModel)]="rawText" placeholder="Paste job description text here..."></textarea><input *ngIf="captureMode === 'link'" class="link-input" [(ngModel)]="jobUrl" placeholder="https://www.linkedin.com/jobs/view/..."><label class="file-picker" *ngIf="captureMode === 'screenshot'">Choose a screenshot<input type="file" accept="image/png,image/jpeg,image/webp" (change)="selectImage($event)"><small>{{ screenshot?.name || 'PNG, JPG, or WebP · 10 MB max' }}</small></label><button class="primary-button" (click)="parse()" [disabled]="parsing">{{ parsing ? 'Reading...' : 'Parse details →' }}</button></div><div class="form-error" *ngIf="message">{{ message }}</div><div class="parsed-card" *ngIf="parsed"><div class="eyebrow">Review extracted details</div><h3>{{ parsed.title }} <span>at {{ parsed.company }}</span></h3><p>{{ parsed.location }} · {{ parsed.pay }}</p><label>Nickname <small>Optional, for quick filtering.</small><input [(ngModel)]="parsedNickname" placeholder="e.g. Dream gig"></label><button class="secondary-button" (click)="saveParsed()">Save application</button></div></section>
  <div class="filter-row"><div class="filter-tabs"><button *ngFor="let filter of filters" [class.selected]="activeFilter === filter" (click)="activeFilter = filter">{{ filter }} <small>{{ filterCount(filter) }}</small></button></div><input class="search-input" [(ngModel)]="search" placeholder="⌕  Search applications"></div>
  <section class="job-list panel"><div class="list-head"><span>Company / role</span><span>Stage</span><span>Applied</span><span></span></div><div class="job-row" *ngFor="let job of visibleJobs"><div class="company-cell"><span class="company-logo">{{ job.company[0] }}</span><div><strong>{{ job.company }}</strong><p>{{ job.title }}<span *ngIf="job.nickname"> · {{ job.nickname }}</span></p></div></div><select class="status-select" [class]="job.status.toLowerCase()" [ngModel]="job.status" (ngModelChange)="changeStatus(job, $event)" [attr.aria-label]="'Status for ' + job.company"><option *ngFor="let status of statuses" [value]="status">{{ label(status) }}<ng-container *ngIf="status === 'Interview' && job.interviewRound"> {{ job.interviewRound }}</ng-container></option></select><time>{{ job.appliedAtUtc | date:'MMM d, y' }}</time><span class="row-actions"><button class="icon-button" title="Edit application" (click)="openEdit(job)">✎</button><button class="icon-button" title="Delete application" (click)="remove(job)">×</button></span></div><div class="empty-state" *ngIf="!visibleJobs.length">No applications match this view.</div></section>
  <div class="modal-backdrop" *ngIf="editing" (click)="closeEdit()">
    <div class="modal-panel panel" (click)="$event.stopPropagation()">
      <div class="panel-heading"><div><div class="eyebrow">Edit application</div><h2>{{ editing.company }}</h2></div><button class="icon-button" title="Close" (click)="closeEdit()">×</button></div>
      <div class="edit-grid">
        <label>Company<input [(ngModel)]="editModel.company"></label>
        <label>Job title<input [(ngModel)]="editModel.title"></label>
        <label>Nickname <small>Optional, for quick filtering.</small><input [(ngModel)]="editModel.nickname" placeholder="e.g. Dream gig"></label>
        <label>Status<select [(ngModel)]="editModel.status"><option *ngFor="let status of statuses" [value]="status">{{ label(status) }}</option></select></label>
        <label *ngIf="editModel.status === 'Interview'">Interview round<strong class="range-value">{{ editModel.interviewRound }}</strong><select [(ngModel)]="editModel.interviewRound"><option *ngFor="let n of rounds" [ngValue]="n">{{ n }}</option></select></label>
        <label>Pay<input [(ngModel)]="editModel.pay" placeholder="e.g. $120k"></label>
        <label>Location<input [(ngModel)]="editModel.location" placeholder="e.g. Remote"></label>
        <label>Applied date<input type="date" [(ngModel)]="editModel.appliedDate"></label>
      </div>
      <label>Description<textarea [(ngModel)]="editModel.description"></textarea></label>
      <label>Skills<textarea [(ngModel)]="editModel.skills" placeholder="Comma separated skills"></textarea></label>
      <button class="primary-button" (click)="saveEdit()">Save changes</button>
      <span class="save-message" *ngIf="message">{{ message }}</span>
    </div>
  </div>` })
export class JobsComponent implements OnInit {
  jobs: Job[] = []; rawText = ''; jobUrl = ''; parsedNickname = ''; screenshot: File | null = null;
  captureMode: 'text' | 'link' | 'screenshot' = 'text'; parsed: ParsedJob | null = null; parsing = false; showCapture = false; message = ''; search = ''; activeFilter = 'All';
  filters = ['All', 'Waiting', 'Interview', 'Job offer', 'Ghosted', 'Rejected'];
  statuses: JobStatus[] = ['Waiting', 'Interview', 'JobOffer', 'Ghosted', 'Rejected'];
  rounds: number[] = Array.from({ length: 10 }, (_, index) => index + 1);
  editing: Job | null = null; editModel!: EditModel;
  constructor(private readonly service: JobsService, private readonly preferences: PreferencesService) {}
  ngOnInit(): void { this.refresh(); this.preferences.get().subscribe(value => this.rounds = Array.from({ length: value.interviewRounds }, (_, index) => index + 1)); }
  get visibleJobs(): Job[] { return this.jobs.filter(job => (this.activeFilter === 'All' || this.label(job.status) === this.activeFilter) && `${job.company} ${job.title} ${job.nickname}`.toLowerCase().includes(this.search.toLowerCase())); }
  selectImage(event: Event): void { const input = event.target as HTMLInputElement; this.screenshot = input.files?.[0] ?? null; this.message = ''; }
  parse(): void {
    if (this.captureMode === 'link') {
      if (!/^https?:\/\//i.test(this.jobUrl.trim())) { this.message = 'Enter a full URL starting with http:// or https://.'; return; }
      this.parsing = true; this.message = '';
      this.service.parseLink(this.jobUrl.trim()).subscribe({ next: value => { this.parsed = value; this.parsing = false; }, error: () => { this.message = 'Could not read that link. Try pasting the text instead.'; this.parsing = false; } });
      return;
    }
    if (this.captureMode === 'screenshot') {
      if (!this.screenshot) { this.message = 'Choose a screenshot first.'; return; }
      this.parsing = true; this.message = '';
      this.service.parseScreenshot(this.screenshot).subscribe({ next: value => { this.parsed = value; this.parsing = false; }, error: () => { this.message = 'OCR failed. Check the image and provider configuration.'; this.parsing = false; } });
      return;
    }
    if (!this.rawText.trim()) { this.message = 'Paste some job description text first.'; return; }
    this.parsing = true; this.message = '';
    this.service.parseText(this.rawText).subscribe({ next: value => { this.parsed = value; this.parsing = false; }, error: () => { this.message = 'Parsing failed. You can still add the details manually.'; this.parsing = false; } });
  }
  saveParsed(): void {
    if (!this.parsed) return;
    this.service.create({ ...this.parsed, nickname: this.parsedNickname, status: 'Waiting' }).subscribe({ next: () => { this.parsed = null; this.rawText = ''; this.jobUrl = ''; this.parsedNickname = ''; this.showCapture = false; this.refresh(); }, error: () => this.message = 'Could not save this application.' });
  }
  changeStatus(job: Job, status: JobStatus): void {
    const interviewRound = status === 'Interview' ? (job.interviewRound ?? 1) : undefined;
    this.service.update(job.id, { ...toPayload(job), status, interviewRound }).subscribe({ next: updated => Object.assign(job, updated), error: () => this.message = 'Could not update the status.' });
  }
  openEdit(job: Job): void {
    this.editing = job; this.message = '';
    this.editModel = { company: job.company, title: job.title, description: job.description, skills: job.skills, pay: job.pay, location: job.location, nickname: job.nickname, status: job.status, interviewRound: job.interviewRound ?? 1, appliedDate: job.appliedAtUtc.slice(0, 10) };
  }
  closeEdit(): void { this.editing = null; this.message = ''; }
  saveEdit(): void {
    if (!this.editing) return;
    if (!this.editModel.company.trim() || !this.editModel.title.trim()) { this.message = 'Company and title are required.'; return; }
    const payload = { ...this.editModel, interviewRound: this.editModel.status === 'Interview' ? Number(this.editModel.interviewRound || 1) : undefined, appliedAtUtc: this.editModel.appliedDate ? new Date(`${this.editModel.appliedDate}T00:00:00Z`).toISOString() : undefined };
    this.service.update(this.editing.id, payload).subscribe({ next: updated => { Object.assign(this.editing!, updated); this.closeEdit(); }, error: () => this.message = 'Could not save changes.' });
  }
  remove(job: Job): void { this.service.delete(job.id).subscribe({ next: () => this.jobs = this.jobs.filter(item => item.id !== job.id) }); }
  refresh(): void { this.service.list().subscribe({ next: jobs => this.jobs = jobs }); }
  filterCount(filter: string): number { return filter === 'All' ? this.jobs.length : this.jobs.filter(job => this.label(job.status) === filter).length; }
  label(status: JobStatus): string { return status === 'JobOffer' ? 'Job offer' : status; }
}

function toPayload(job: Job) {
  return { company: job.company, title: job.title, description: job.description, skills: job.skills, pay: job.pay, location: job.location, nickname: job.nickname };
}
