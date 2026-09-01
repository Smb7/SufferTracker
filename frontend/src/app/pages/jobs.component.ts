import { Component, HostListener, OnInit } from '@angular/core';
import { createWorker } from 'tesseract.js';
import { firstValueFrom } from 'rxjs';
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
  <section class="capture panel" *ngIf="showCapture"><div class="capture-intro"><div class="eyebrow">New application</div><h2>Start with the messy bit.</h2><p>Paste a link, drop in the description text, or upload a screenshot. We will pull out the useful parts for you to review.</p></div><div class="capture-body"><div class="capture-tabs"><button [class.selected]="captureMode === 'text'" (click)="captureMode = 'text'">Paste text</button><button [class.selected]="captureMode === 'link'" (click)="captureMode = 'link'">Job link</button><button [class.selected]="captureMode === 'screenshot'" (click)="captureMode = 'screenshot'">Screenshot OCR</button></div><textarea *ngIf="captureMode === 'text'" [(ngModel)]="rawText" placeholder="Paste job description text here..."></textarea><input *ngIf="captureMode === 'link'" class="link-input" [(ngModel)]="jobUrl" placeholder="https://www.linkedin.com/jobs/view/..."><label class="file-picker" *ngIf="captureMode === 'screenshot'">Choose a screenshot or press ⌘/Ctrl+V<input type="file" accept="image/png,image/jpeg,image/webp" (change)="selectImage($event)"><small>{{ screenshot ? screenshot.name : 'PNG, JPG, or WebP · 10 MB max · paste supported' }}</small></label><div class="ocr-progress" *ngIf="ocrProgress !== null"><div class="bar-track"><div class="bar-fill orange" [style.width.%]="ocrProgress"></div></div><small>Reading image locally… {{ ocrProgress }}%</small></div><button class="primary-button" (click)="parse()" [disabled]="parsing">{{ parsing ? 'Reading...' : 'Parse details →' }}</button></div><div class="form-error" *ngIf="message">{{ message }}</div><div class="parsed-card" *ngIf="parsed"><div class="eyebrow">Review extracted details</div><h3>{{ parsed.title }} <span>at {{ parsed.company }}</span></h3><p>{{ parsed.location }} · {{ parsed.pay }}</p><label>Nickname <small>Optional, for quick filtering.</small><input [(ngModel)]="parsedNickname" placeholder="e.g. Dream gig"></label><button class="secondary-button" (click)="saveParsed()">Save application</button></div></section>
  <div class="filter-row"><div class="filter-tabs"><button *ngFor="let filter of filters" [class.selected]="activeFilter === filter" (click)="activeFilter = filter">{{ filter }} <small>{{ filterCount(filter) }}</small></button></div><input class="search-input" [(ngModel)]="search" placeholder="⌕  Search applications"></div>
  <section class="job-list panel"><div class="list-head"><span>Company / role</span><span>Stage</span><span>Applied</span><span></span></div><div class="job-row" *ngFor="let job of visibleJobs"><div class="company-cell"><span class="company-logo" [style.background]="logoStyle(job.company).background" [style.color]="logoStyle(job.company).color">{{ logoInitial(job.company) }}</span><div><strong>{{ job.company }}</strong><p>{{ job.title }}<span *ngIf="job.nickname"> · {{ job.nickname }}</span></p></div></div><div class="stage-tracker"><button type="button" class="stage-step applied" [class.active]="!interviewing(job) && !outcomeValue(job)" title="Return to Applied" (click)="markApplied(job)">Applied</button><span class="stage-rail" [class.filled]="interviewing(job) || !!outcomeValue(job)"></span><div class="stage-group" *ngIf="!interviewing(job)"><button type="button" class="stage-step entry" (click)="markRound(job, 1)" [disabled]="!!outcomeValue(job)">Interview</button></div><div class="stage-group" *ngIf="interviewing(job)"><button type="button" class="stage-step round" *ngFor="let r of rounds" [class.done]="r <= (job.interviewRound ?? 0)" [class.current]="job.status === 'Interview' && r === (job.interviewRound ?? 0)" (click)="markRound(job, r)" [attr.aria-label]="'Interview round ' + r + (r === (job.interviewRound ?? 0) ? ', click to clear' : '')" [title]="r === (job.interviewRound ?? 0) ? 'Clear this round' : 'Mark round ' + r">{{ r }}</button></div><span class="stage-rail" [class.filled]="!!outcomeValue(job)"></span><div class="stage-group outcomes"><button type="button" class="stage-step offer" [class.active]="job.status === 'JobOffer'" [disabled]="!offerUnlocked(job)" (click)="toggleOutcome(job, 'JobOffer')">Offer</button><button type="button" class="stage-step rejected" [class.active]="job.status === 'Rejected'" (click)="toggleOutcome(job, 'Rejected')">Rejected</button><button type="button" class="stage-step ghosted" [class.active]="job.status === 'Ghosted'" (click)="toggleOutcome(job, 'Ghosted')">Ghosted</button></div></div><time>{{ job.appliedAtUtc | date:'MMM d, y' }}</time><span class="row-actions"><button class="icon-button edit" title="Edit application" (click)="openEdit(job)">edit</button><button class="icon-button delete" title="Delete application" (click)="remove(job)">delete</button></span></div><div class="empty-state" *ngIf="!visibleJobs.length">No applications match this view.</div></section>
  <div class="modal-backdrop" *ngIf="editing" (mousedown)="onBackdropPointer($event, 'down')" (mouseup)="onBackdropPointer($event, 'up')" (click)="onBackdropClick($event)">
    <div class="modal-panel panel" (mousedown)="$event.stopPropagation()" (click)="$event.stopPropagation()">
      <div class="panel-heading"><div><div class="eyebrow">Edit application</div><h2>{{ editing.company }}</h2></div><button class="icon-button" title="Close" (click)="closeEdit()">×</button></div>
      <div class="timeline-chips" *ngIf="editing?.statusEvents?.length"><div class="eyebrow">Progression</div><span class="chip" *ngFor="let event of editing.statusEvents">{{ label(event.status) }}</span></div>
      <div class="edit-grid">
        <label>Company<input [(ngModel)]="editModel.company"></label>
        <label>Job title<input [(ngModel)]="editModel.title"></label>
        <label>Nickname <small>Optional, for quick filtering.</small><input [(ngModel)]="editModel.nickname" placeholder="e.g. Dream gig"></label>
        <label>Status <small *ngIf="!offerUnlocked(editing)">Record an interview to unlock 'Job offer'.</small><select [(ngModel)]="editModel.status"><option *ngFor="let status of statuses" [value]="status" [disabled]="status === 'JobOffer' && !offerUnlocked(editing)">{{ label(status) }}</option></select></label>
        <div class="interview-rounds" *ngIf="editModel.status === 'Interview'"><div class="eyebrow">Interview rounds · {{ roundsDoneLabel }}</div><label class="round-check" *ngFor="let r of rounds; let i = index" [class.checked]="editRoundsDone[i]" (click)="markEditRound(i)">Round {{ r }}</label></div>
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
  filters = ['All', 'Applied', 'Interview', 'Job offer', 'Ghosted', 'Rejected'];
  statuses: JobStatus[] = ['Applied', 'Interview', 'JobOffer', 'Ghosted', 'Rejected'];
  rounds: number[] = Array.from({ length: 10 }, (_, index) => index + 1);
  editing: Job | null = null; editModel!: EditModel; editRoundsDone: boolean[] = []; ocrProgress: number | null = null;
  constructor(private readonly service: JobsService, private readonly preferences: PreferencesService) {}
  ngOnInit(): void { this.refresh(); this.preferences.get().subscribe(value => this.rounds = Array.from({ length: value.interviewRounds }, (_, index) => index + 1)); }
  get visibleJobs(): Job[] { return this.jobs.filter(job => (this.activeFilter === 'All' || this.label(job.status) === this.activeFilter) && `${job.company} ${job.title} ${job.nickname}`.toLowerCase().includes(this.search.toLowerCase())); }
  selectImage(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;
    if (file) void this.recognizeLocally(file);
  }

  /** Runs Tesseract.js in the browser; falls back to the server OCR endpoint on failure. */
  async recognizeLocally(file: File): Promise<void> {
    this.ocrProgress = 0;
    try {
      const worker = await createWorker('eng', 1, {
        workerPath: 'https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/worker.min.js',
        corePath: 'https://cdn.jsdelivr.net/npm/tesseract.js-core@5.1.1',
        langPath: 'https://tessdata.projectnaptha.com/4.0.0',
        logger: message => { if (message.status === 'recognizing text') this.ocrProgress = Math.round(message.progress * 100); }
      });
      const result = await worker.recognize(file);
      await worker.terminate();
      const text = result.data.text.trim();
      if (!text) throw new Error('empty');
      this.rawText = text;
      this.captureMode = 'text';
      this.ocrProgress = null;
      this.parse();
    } catch {
      this.ocrProgress = null;
      this.message = 'Local OCR unavailable — sending the image to the server instead.';
      this.parsing = true;
      this.service.parseScreenshot(file).subscribe({
        next: value => { this.parsed = value; this.parsing = false; },
        error: () => { this.parsing = false; this.message = 'OCR failed. Check the image and provider configuration.'; }
      });
    }
  }
  @HostListener('document:paste', ['$event'])
  onPaste(event: ClipboardEvent): void {
    if (!this.showCapture) return;
    const target = event.target as HTMLElement | null;
    if (target && /^(input|textarea)$/i.test(target.tagName)) return;
    const imageItem = [...(event.clipboardData?.items ?? [])].find(item => /^image\/(png|jpeg|webp)$/i.test(item.type));
    const file = imageItem?.getAsFile();
    if (!file || !imageItem) return;
    event.preventDefault();
    const extension = imageItem.type.split('/')[1]?.toLowerCase() ?? 'png';
    this.screenshot = new File([file], file.name || `pasted-screenshot.${extension}`, { type: imageItem.type });
    this.showCapture = true;
    this.message = '';
    void this.recognizeLocally(this.screenshot);
  }
  parse(): void {
    if (this.captureMode === 'link') {
      if (!/^https?:\/\//i.test(this.jobUrl.trim())) { this.message = 'Enter a full URL starting with http:// or https://.'; return; }
      this.parsing = true; this.message = '';
      (async () => { try { const value = await this.service.parseLinkSmart(this.jobUrl.trim()); this.parsed = value; this.parsing = false; } catch { this.message = 'Could not read that link. Try pasting the text instead.'; this.parsing = false; } })();
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
  changeStatus(job: Job, status: JobStatus, round?: number): void {
    const interviewRound = status === 'Interview'
      ? Math.max(1, round ?? job.interviewRound ?? 1)
      : (status === 'Applied' || status === 'Waiting') ? 0 : (round ?? job.interviewRound ?? 0);
    try {
      this.service.update(job.id, { ...toPayload(job), statusEvents: job.statusEvents ?? [], status, interviewRound }).subscribe({ next: updated => Object.assign(job, updated), error: error => this.message = error.error?.message ?? 'Could not update the status.' });
    } catch (error) {
      this.message = (error as Error).message;
    }
  }
  interviewing(job: Job): boolean { return job.status === 'Interview' || (job.interviewRound ?? 0) > 0; }
  outcomeValue(job: Job): JobStatus | '' { return ['JobOffer', 'Rejected', 'Ghosted'].includes(job.status) ? job.status : ''; }
  markApplied(job: Job): void {
    if (job.status === 'Applied' || job.status === 'Waiting') return;
    this.changeStatus(job, 'Applied');
  }
  markRound(job: Job, round: number): void {
    if (['JobOffer', 'Rejected', 'Ghosted'].includes(job.status)) return;
    const current = job.interviewRound ?? 0;
    if (round === current) {
      if (round <= 1) { this.changeStatus(job, 'Applied'); return; }
      this.changeStatus(job, 'Interview', round - 1);
      return;
    }
    this.changeStatus(job, 'Interview', round);
  }
  toggleOutcome(job: Job, status: JobStatus): void {
    if (this.outcomeValue(job) === status) {
      const round = job.interviewRound ?? 0;
      this.changeStatus(job, round > 0 ? 'Interview' : 'Applied', round);
      return;
    }
    this.changeStatus(job, status);
  }
  openEdit(job: Job): void {
    this.editing = job; this.message = '';
    this.editModel = { company: job.company, title: job.title, description: job.description, skills: job.skills, pay: job.pay, location: job.location, nickname: job.nickname, status: job.status, interviewRound: job.interviewRound ?? 1, appliedDate: job.appliedAtUtc.slice(0, 10) };
    const reached = job.interviewRound ?? 0;
    this.editRoundsDone = this.rounds.map((_, index) => index < reached);
  }
  markEditRound(index: number): void {
    if (this.editRoundsDone.length !== this.rounds.length) this.editRoundsDone = this.rounds.map(() => false);
    const count = this.editRoundsDone.filter(Boolean).length;
    if (index + 1 === count) { this.editRoundsDone[index] = false; return; }
    for (let k = 0; k < this.editRoundsDone.length; k++) this.editRoundsDone[k] = k <= index;
  }
  get roundsDoneLabel(): string {
    const count = this.editRoundsDone.filter(Boolean).length;
    return count === 0 ? 'None recorded' : `Round ${count}`;
  }
  private backdropDown = false;
  private backdropUp = false;
  onBackdropPointer(event: MouseEvent, phase: 'down' | 'up'): void {
    const onBackdrop = event.target === event.currentTarget;
    if (phase === 'down') this.backdropDown = onBackdrop;
    else this.backdropUp = onBackdrop;
  }
  onBackdropClick(event: MouseEvent): void {
    if (this.backdropDown && this.backdropUp && event.target === event.currentTarget) this.closeEdit();
    this.backdropDown = false;
    this.backdropUp = false;
  }
  closeEdit(): void { this.editing = null; this.message = ''; this.backdropDown = false; this.backdropUp = false; }
  saveEdit(): void {
    const target = this.editing;
    if (!target) return;
    if (!this.editModel.company.trim() || !this.editModel.title.trim()) { this.message = 'Company and title are required.'; return; }
    const round = this.editRoundsDone.filter(Boolean).length;
    let status = this.editModel.status;
    let interviewRound = round;
    if (status === 'Interview') {
      if (round === 0) { status = 'Applied'; interviewRound = 0; }
    } else if (status === 'Applied' || status === 'Waiting') {
      interviewRound = 0;
    } else {
      interviewRound = Math.max(round, target.interviewRound ?? 0);
    }
    const payload = { ...this.editModel, status, statusEvents: target.statusEvents ?? [], interviewRound, appliedAtUtc: this.editModel.appliedDate ? new Date(`${this.editModel.appliedDate}T00:00:00Z`).toISOString() : undefined };
    try {
      this.service.update(target.id, payload).subscribe({ next: updated => { Object.assign(target, updated); this.closeEdit(); }, error: error => this.message = error.error?.message ?? 'Could not save changes.' });
    } catch (error) {
      this.message = (error as Error).message;
    }
  }
  remove(job: Job): void { this.service.delete(job.id).subscribe({ next: () => this.jobs = this.jobs.filter(item => item.id !== job.id) }); }
  refresh(): void { this.service.list().subscribe({ next: jobs => this.jobs = jobs }); }
  filterCount(filter: string): number { return filter === 'All' ? this.jobs.length : this.jobs.filter(job => this.label(job.status) === filter).length; }
  label(status: JobStatus): string { if (status === 'JobOffer') return 'Job offer'; if (status === 'Waiting') return 'Applied'; return status; }
  offerUnlocked(job: Job | null): boolean { return !!job && (job.status === 'Interview' || job.status === 'JobOffer' || (job.interviewRound ?? 0) > 0 || !!job.statusEvents?.some(event => event.status === 'Interview')); }
  logoInitial(name: string): string {
    const match = (name ?? '').trim().match(/[A-Za-z0-9]/);
    return (match?.[0] ?? '?').toUpperCase();
  }
  logoStyle(name: string): { background: string; color: string } {
    const tones = [
      { background: 'var(--tint-warn-bg)', color: 'var(--tint-warn-fg)' },
      { background: 'var(--tint-green-bg)', color: 'var(--tint-green-fg)' },
      { background: 'var(--tint-violet-bg)', color: 'var(--tint-violet-fg)' },
      { background: 'var(--tint-yellow-bg)', color: 'var(--tint-yellow-fg)' }
    ];
    const source = (name ?? '').trim().toUpperCase();
    let hash = 0;
    for (let i = 0; i < source.length; i++) hash = (hash * 33 + source.charCodeAt(i)) >>> 0;
    return tones[hash % tones.length];
  }
}

function toPayload(job: Job) {
  return { company: job.company, title: job.title, description: job.description, skills: job.skills, pay: job.pay, location: job.location, nickname: job.nickname, statusEvents: job.statusEvents ?? [] };
}
