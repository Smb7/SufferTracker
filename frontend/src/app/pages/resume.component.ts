import { Component, OnInit } from '@angular/core';
import { NgFor, NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { JobResume, ResumeSections } from '../core/models';
import { JobsService } from '../core/jobs.service';

@Component({
  standalone: true,
  imports: [NgFor, NgIf, FormsModule, RouterLink],
  template: `
    <header class="page-header">
      <div>
        <div class="eyebrow">Review draft</div>
        <h1>{{ resume?.title || 'Resume' }}</h1>
        <p class="subtle" *ngIf="resume?.company">For {{ resume?.company }}. Nothing is downloaded or sent to the employer.</p>
        <p class="fit-note">If OpenCode is connected in Settings, or a server AI provider is configured, the draft and the evidence it cites are sent there to rewrite wording. The server still rejects employers, dates, tools, and degrees that are not in your evidence.</p>
      </div>
      <a routerLink="/jobs" class="secondary-button">Back to applications</a>
    </header>
    <p class="form-error" *ngIf="message">{{ message }}</p>
    <section class="panel resume-blocked" *ngIf="resume?.blockedReason">
      <p>{{ resume?.blockedReason }}</p>
      <a *ngIf="resume?.profileBlocked" routerLink="/onboarding">Finish onboarding</a>
    </section>
    <section class="resume-layout" *ngIf="resume?.sections as sections">
      <div class="panel resume-score">
        <div class="eyebrow">Fit at draft</div>
        <strong class="fit-score" *ngIf="resume?.score !== null">{{ resume?.score }}<small>/100</small></strong>
        <p class="fit-note">The server owns this number. Editing wording does not change it.</p>
        <div class="eyebrow">Gaps</div>
        <div class="fit-chips" *ngIf="resume?.missing?.length; else noGaps">
          <span class="fit-chip gap" *ngFor="let gap of resume?.missing">{{ gap }}</span>
        </div>
        <ng-template #noGaps><p class="fit-note">No required or preferred gaps.</p></ng-template>
        <p class="fit-note">Gaps stay gaps. This draft will not invent them.</p>
        <button class="secondary-button" type="button" (click)="draft()" [disabled]="busy">Regenerate</button>
      </div>
      <form class="panel resume-sheet" (ngSubmit)="save(sections)">
        <label>Summary
          <textarea [(ngModel)]="sections.summary" name="summary"></textarea>
        </label>
        <div class="eyebrow">Skills</div>
        <label *ngFor="let skill of sections.skills; let i = index">
          <input [(ngModel)]="skill.text" [name]="'skill' + i">
        </label>
        <div class="eyebrow">Experience</div>
        <article class="resume-role" *ngFor="let role of sections.experience; let ri = index">
          <h2>{{ role.title || 'Role' }} <span *ngIf="role.company">at {{ role.company }}</span></h2>
          <p class="fit-note" *ngIf="role.start || role.end">{{ role.start }} – {{ role.end }}</p>
          <label *ngFor="let bullet of role.bullets; let bi = index">
            <textarea [(ngModel)]="bullet.text" [name]="'bullet' + ri + '-' + bi"></textarea>
          </label>
          <p class="fit-note" *ngIf="!role.bullets.length">No highlight was recorded for this role.</p>
        </article>
        <div class="eyebrow" *ngIf="sections.education.length">Education</div>
        <article class="resume-role" *ngFor="let item of sections.education; let ei = index">
          <h2>{{ item.credential || 'Education' }} <span *ngIf="item.institution">at {{ item.institution }}</span></h2>
          <p class="fit-note">{{ item.field }} <span *ngIf="item.year">· {{ item.year }}</span></p>
          <label>
            <textarea [(ngModel)]="item.text" [name]="'education' + ei"></textarea>
          </label>
        </article>
        <button class="primary-button" type="submit" [disabled]="busy">Save review</button>
        <span class="save-message" *ngIf="saved">Saved. Still not sent anywhere.</span>
      </form>
    </section>
  `
})
export class ResumeComponent implements OnInit {
  resume: JobResume | null = null;
  message = '';
  saved = false;
  busy = false;
  private jobId = '';

  constructor(private readonly route: ActivatedRoute, private readonly jobs: JobsService) {}

  ngOnInit(): void {
    this.jobId = this.route.snapshot.paramMap.get('id') || '';
    if (!this.jobId) {
      this.message = 'Missing job.';
      return;
    }
    this.load();
  }

  load(): void {
    this.busy = true;
    this.jobs.resume(this.jobId).subscribe({
      next: value => this.apply(value),
      error: err => {
        if (err.status === 404) this.draft();
        else this.fail(err, 'Could not load this resume.');
      }
    });
  }

  draft(): void {
    this.busy = true;
    this.saved = false;
    this.jobs.draftResume(this.jobId).subscribe({
      next: value => {
        if (value.blockedReason && !value.sections && this.resume?.sections) {
          this.busy = false;
          this.message = value.blockedReason;
          return;
        }
        this.message = '';
        this.apply(value);
      },
      error: err => this.fail(err, 'Could not draft this resume.')
    });
  }

  save(sections: ResumeSections): void {
    this.busy = true;
    this.saved = false;
    this.jobs.saveResume(this.jobId, sections).subscribe({
      next: value => {
        this.apply(value);
        this.saved = !value.blockedReason;
      },
      error: err => this.fail(err, 'Could not save this resume.')
    });
  }

  private apply(value: JobResume): void {
    this.resume = value;
    this.busy = false;
    this.message = value.blockedReason && !value.sections ? '' : this.message;
    if (value.blockedReason && !value.sections) this.message = '';
  }

  private fail(err: { error?: { message?: string } }, fallback: string): void {
    this.busy = false;
    this.message = err?.error?.message || fallback;
  }
}
