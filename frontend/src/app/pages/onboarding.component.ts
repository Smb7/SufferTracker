import { Component, ElementRef, OnInit, ViewChild } from '@angular/core';
import { NgFor, NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { CareerContext, CareerGoals, OnboardingMessage } from '../core/models';
import { OnboardingService } from '../core/onboarding.service';

@Component({
  standalone: true,
  imports: [NgFor, NgIf, FormsModule, RouterLink],
  template: `
    <header class="page-header">
      <div>
        <div class="eyebrow">Career context</div>
        <h1>{{ context?.status === 'completed' ? 'The coach knows your search.' : 'Tell the coach who you are.' }}</h1>
        <p class="subtle">Experience, education, skills, interests, and the job you want next. Later coaching reads this — not the other way around.</p>
      </div>
      <a routerLink="/dashboard" class="secondary-button">Back to overview</a>
    </header>
    <p class="coach-note" *ngIf="loaded && !providerConfigured">Guided interviewer. <a routerLink="/settings">Connect OpenCode in Settings</a> to use a model — until then, answers stay in SufferTracker.</p>
    <p class="coach-note" *ngIf="loaded && providerConfigured">This conversation is sent to OpenCode, or the server AI provider, so the coach can structure it.</p>
    <ol class="coach-steps" *ngIf="context">
      <li *ngFor="let step of steps" [class.done]="done(step.key)" [class.current]="current(step.key)">{{ step.label }}</li>
    </ol>
    <div class="coach-layout" *ngIf="context as ctx; else loading">
      <section class="panel coach-thread">
        <div class="coach-log" #thread role="log" aria-live="polite">
          <div class="coach-row" *ngFor="let message of messages" [class.user]="message.role === 'user'">
            <span class="coach-mark" *ngIf="message.role === 'assistant'">S</span>
            <div class="coach-bubble" [class.assistant]="message.role === 'assistant'" [class.user]="message.role === 'user'">{{ message.content }}</div>
          </div>
          <div class="coach-row" *ngIf="busy"><span class="coach-mark">S</span><div class="coach-bubble assistant">Reading that…</div></div>
        </div>
        <form class="coach-composer" (ngSubmit)="send()">
          <textarea name="message" [(ngModel)]="draft" [disabled]="busy" maxlength="8000" placeholder="Answer in your own words" (keydown.enter)="onEnter($event)"></textarea>
          <button class="primary-button" type="submit" [disabled]="busy || !draft.trim()">{{ busy ? 'Sending' : 'Send' }}</button>
        </form>
        <p class="coach-note">Enter to send. Shift+Enter for a new line.</p>
        <p class="form-error" *ngIf="error">{{ error }}</p>
        <p class="coach-note" *ngIf="ctx.notice">{{ ctx.notice }}</p>
      </section>
      <aside class="panel coach-context">
        <div class="panel-heading">
          <div><div class="eyebrow">What the coach has</div><h2>{{ ctx.status === 'completed' ? 'Saved context' : 'In progress' }}</h2></div>
          <button class="text-link" type="button" (click)="editing = !editing">{{ editing ? 'Close edit' : 'Edit' }}</button>
        </div>
        <p class="context-summary" *ngIf="ctx.summary">{{ ctx.summary }}</p>
        <div class="context-block">
          <h3>Experience</h3>
          <p class="subtle" *ngIf="!ctx.experience.length">{{ done('experience') ? 'None to record.' : 'Not captured yet.' }}</p>
          <div class="context-item" *ngFor="let role of ctx.experience">
            <strong>{{ roleLabel(role.title, role.company) }}</strong>
            <span *ngIf="role.start"> {{ role.start }}<span *ngIf="role.end">–{{ role.end }}</span></span>
            <p class="context-note">{{ role.highlights }}</p>
          </div>
        </div>
        <div class="context-block">
          <h3>Education</h3>
          <p class="subtle" *ngIf="!ctx.education.length">{{ done('education') ? 'None to record.' : 'Not captured yet.' }}</p>
          <div class="context-item" *ngFor="let school of ctx.education">
            <strong>{{ school.credential || school.institution || 'Education' }}</strong>
            <span *ngIf="school.institution && school.credential"> at {{ school.institution }}</span>
            <p class="context-note" *ngIf="school.notes">{{ school.notes }}</p>
          </div>
        </div>
        <div class="context-block">
          <h3>Skills</h3>
          <p class="subtle" *ngIf="!ctx.skills.length">Not captured yet.</p>
          <div class="chip-row" *ngIf="ctx.skills.length"><span class="coach-chip" *ngFor="let skill of ctx.skills">{{ skill }}</span></div>
        </div>
        <div class="context-block">
          <h3>Interests</h3>
          <p class="subtle" *ngIf="!ctx.interests.length">Not captured yet.</p>
          <div class="chip-row" *ngIf="ctx.interests.length"><span class="coach-chip" *ngFor="let interest of ctx.interests">{{ interest }}</span></div>
        </div>
        <div class="context-block">
          <h3>Next job</h3>
          <p class="subtle" *ngIf="!ctx.goals.narrative && !ctx.goals.targetRoles.length">Not captured yet.</p>
          <div class="chip-row" *ngIf="ctx.goals.targetRoles.length"><span class="coach-chip" *ngFor="let role of ctx.goals.targetRoles">{{ role }}</span></div>
          <p class="context-meta" *ngIf="goalMeta(ctx.goals)">{{ goalMeta(ctx.goals) }}</p>
          <p class="context-note" *ngIf="ctx.goals.narrative">{{ ctx.goals.narrative }}</p>
        </div>
        <form class="coach-edit" *ngIf="editing" (ngSubmit)="saveEdits()">
          <label>Skills <small>Comma-separated.</small><input name="skills" [(ngModel)]="skillsDraft"></label>
          <label>Interests <small>Comma-separated.</small><input name="interests" [(ngModel)]="interestsDraft"></label>
          <label>Target roles<input name="roles" [(ngModel)]="rolesDraft"></label>
          <label>Work style<input name="workStyle" [(ngModel)]="workStyleDraft" placeholder="remote, hybrid, on-site"></label>
          <label>Pay<input name="pay" [(ngModel)]="payDraft"></label>
          <label>Next job, in your words<textarea name="narrative" [(ngModel)]="narrativeDraft"></textarea></label>
          <button class="secondary-button" type="submit" [disabled]="busy">Save edits</button>
        </form>
        <div class="coach-actions">
          <button class="primary-button" type="button" (click)="complete()" [disabled]="busy || ctx.missing.length > 0 || ctx.status === 'completed'">{{ ctx.status === 'completed' ? 'Context saved' : 'Save this context' }}</button>
          <button class="secondary-button" type="button" *ngIf="ctx.status === 'completed'" (click)="reopen()" [disabled]="busy">Update</button>
          <button class="text-link" type="button" (click)="reset()">Start over</button>
        </div>
        <p class="coach-note" *ngIf="ctx.missing.length">Still need {{ missingLabels(ctx) }}.</p>
      </aside>
    </div>
    <ng-template #loading><section class="panel"><p class="subtle">Loading the coach…</p></section></ng-template>
  `
})
export class OnboardingComponent implements OnInit {
  @ViewChild('thread') thread?: ElementRef<HTMLElement>;
  context: CareerContext | null = null;
  messages: OnboardingMessage[] = [];
  providerConfigured = false;
  draft = '';
  error = '';
  busy = false;
  loaded = false;
  editing = false;
  skillsDraft = '';
  interestsDraft = '';
  rolesDraft = '';
  workStyleDraft = '';
  payDraft = '';
  narrativeDraft = '';
  steps = [
    { key: 'experience', label: 'Experience' },
    { key: 'education', label: 'Education' },
    { key: 'skills', label: 'Skills' },
    { key: 'interests', label: 'Interests' },
    { key: 'goals', label: 'Goals' }
  ];
  constructor(private readonly onboarding: OnboardingService) {}
  ngOnInit(): void { this.onboarding.state().subscribe({ next: state => this.apply(state), error: () => this.fail('Could not load the coach.') }); }
  done(key: string): boolean { return !!this.context && !this.context.missing.includes(key); }
  current(key: string): boolean { return this.context?.missing[0] === key; }
  roleLabel(title: string, company: string): string { return [title, company].filter(Boolean).join(' at ') || 'Work history'; }
  goalMeta(goals: CareerGoals): string { return [goals.workStyle, goals.compensation, goals.locations.join(', ')].filter(Boolean).join(' · '); }
  missingLabels(ctx: CareerContext): string { return this.steps.filter(step => ctx.missing.includes(step.key)).map(step => step.label.toLowerCase()).join(', '); }
  onEnter(event: Event): void {
    const keyboard = event as KeyboardEvent;
    if (keyboard.shiftKey) return;
    keyboard.preventDefault();
    this.send();
  }
  send(): void {
    const content = this.draft.trim();
    if (!content || this.busy) return;
    this.busy = true;
    this.error = '';
    this.onboarding.send(content).subscribe({
      next: state => { this.draft = ''; this.apply(state); },
      error: response => this.fail(response?.error?.message ?? 'Could not send that.')
    });
  }
  saveEdits(): void {
    if (!this.context || this.busy) return;
    this.busy = true;
    this.error = '';
    const goals: CareerGoals = {
      ...this.context.goals,
      targetRoles: this.split(this.rolesDraft),
      workStyle: this.workStyleDraft.trim(),
      compensation: this.payDraft.trim(),
      narrative: this.narrativeDraft.trim()
    };
    this.onboarding.update({ skills: this.split(this.skillsDraft), interests: this.split(this.interestsDraft), goals }).subscribe({
      next: context => { this.context = context; this.editing = false; this.busy = false; this.fillDrafts(context); },
      error: response => this.fail(response?.error?.message ?? 'Could not save those edits.')
    });
  }
  complete(): void {
    if (this.busy) return;
    this.busy = true;
    this.error = '';
    this.onboarding.complete().subscribe({
      next: state => this.apply(state),
      error: response => this.fail(response?.error?.message ?? 'Context is not ready to save yet.')
    });
  }
  reopen(): void {
    this.busy = true;
    this.error = '';
    this.onboarding.reopen().subscribe({
      next: context => { this.context = context; this.busy = false; },
      error: () => this.fail('Could not reopen onboarding.')
    });
  }
  reset(): void {
    if (!confirm('Clear this conversation and the saved career context?')) return;
    this.busy = true;
    this.error = '';
    this.onboarding.reset().subscribe({
      next: state => { this.draft = ''; this.editing = false; this.apply(state); },
      error: () => this.fail('Could not start over.')
    });
  }
  private apply(state: { context: CareerContext; messages: OnboardingMessage[]; providerConfigured: boolean }): void {
    this.context = state.context;
    this.messages = state.messages;
    this.providerConfigured = state.providerConfigured;
    this.loaded = true;
    this.busy = false;
    if (!this.editing) this.fillDrafts(state.context);
    setTimeout(() => { const el = this.thread?.nativeElement; if (el) el.scrollTop = el.scrollHeight; });
  }
  private fillDrafts(context: CareerContext): void {
    this.skillsDraft = context.skills.join(', ');
    this.interestsDraft = context.interests.join(', ');
    this.rolesDraft = context.goals.targetRoles.join(', ');
    this.workStyleDraft = context.goals.workStyle;
    this.payDraft = context.goals.compensation;
    this.narrativeDraft = context.goals.narrative;
  }
  private split(value: string): string[] {
    const seen = new Set<string>();
    const items: string[] = [];
    for (const part of value.split(/[,;\n]/)) {
      const item = part.trim();
      if (item.length < 2 || seen.has(item.toLowerCase())) continue;
      seen.add(item.toLowerCase());
      items.push(item);
    }
    return items;
  }
  private fail(message: string): void { this.error = message; this.busy = false; this.loaded = true; }
}
