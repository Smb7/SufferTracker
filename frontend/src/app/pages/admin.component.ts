import { Component, OnInit } from '@angular/core';
import { DatePipe, NgFor, NgIf } from '@angular/common';
import { AdminService } from '../core/admin.service';
import { AuthService } from '../core/auth.service';
import { AdminUser, LoginEvent } from '../core/models';
import { SignInMapComponent } from './signin-map.component';

@Component({
  standalone: true,
  imports: [NgFor, NgIf, DatePipe, SignInMapComponent],
  template: `
    <header class="page-header"><div><div class="eyebrow">Operators</div><h1>Admin</h1><p class="subtle">Accounts, MFA, and every sign-in attempt.</p></div></header>
    <section class="panel visualizer-panel">
      <div class="panel-heading"><div><div class="eyebrow">Accounts</div><h2>Users</h2></div><span class="subtle">{{ users.length }} total</span></div>
      <div class="admin-table-wrap">
        <div class="admin-head"><span>Username</span><span>MFA</span><span>Status</span><span></span></div>
        <div class="admin-row" *ngFor="let user of users">
          <div><strong>{{ user.email }}</strong><p>{{ user.displayName }}<span *ngIf="user.isAdmin"> · admin</span></p></div>
          <span class="status-badge" [class.joboffer]="user.mfaEnabled" [class.ghosted]="!user.mfaEnabled">{{ user.mfaEnabled ? 'true' : 'false' }}</span>
          <span class="status-badge" [class.rejected]="user.isLocked" [class.joboffer]="!user.isLocked">{{ user.isLocked ? 'Locked' : 'Active' }}</span>
          <span class="row-actions">
            <button class="secondary-button" *ngIf="!user.isLocked && user.id !== selfId" (click)="lock(user)">Lock</button>
            <button class="secondary-button" *ngIf="user.isLocked" (click)="unlock(user)">Unlock</button>
            <button class="danger-button" *ngIf="user.mfaEnabled" (click)="resetMfa(user)">Reset MFA</button>
          </span>
        </div>
        <div class="empty-state" *ngIf="!users.length">No users yet.</div>
      </div>
      <p class="form-error" *ngIf="message">{{ message }}</p>
    </section>
    <section class="panel visualizer-panel">
      <div class="panel-heading"><div><div class="eyebrow">Geography</div><h2>Sign-in map</h2></div><span class="subtle">{{ mapped.length }} plotted · private IPs stay in the log</span></div>
      <st-signin-map *ngIf="mapped.length" [events]="mapped"></st-signin-map>
      <div class="empty-state" *ngIf="loaded && !mapped.length">No public IPs to plot yet. Local sign-ins still appear in the log below.</div>
    </section>
    <section class="panel visualizer-panel">
      <div class="panel-heading"><div><div class="eyebrow">Audit</div><h2>Sign-in log</h2></div></div>
      <div class="admin-table-wrap">
        <div class="log-head"><span>Username</span><span>MFA</span><span>IP</span><span>Result</span><span>When</span></div>
        <div class="log-row" *ngFor="let event of logins">
          <div><strong>{{ event.username }}</strong><p *ngIf="event.city || event.country">{{ event.city }}<span *ngIf="event.city && event.country">, </span>{{ event.country }}</p></div>
          <span>{{ event.mfaEnabled ? 'true' : 'false' }}</span>
          <span class="mono">{{ event.ipAddress }}</span>
          <span class="status-badge" [class.joboffer]="event.succeeded" [class.rejected]="!event.succeeded">{{ event.succeeded ? 'Success' : 'Failed' }}</span>
          <time>{{ event.occurredAtUtc | date:'MMM d, y HH:mm' }}</time>
        </div>
        <div class="empty-state" *ngIf="loaded && !logins.length">No sign-in attempts recorded.</div>
      </div>
    </section>
  `
})
export class AdminComponent implements OnInit {
  users: AdminUser[] = []; logins: LoginEvent[] = []; message = ''; loaded = false;
  constructor(private readonly admin: AdminService, private readonly auth: AuthService) {}
  get selfId(): string { return this.auth.user()?.userId ?? ''; }
  get mapped(): LoginEvent[] { return this.logins.filter(event => event.latitude != null && event.longitude != null); }
  ngOnInit(): void {
    this.admin.users().subscribe({ next: users => this.users = users, error: () => this.message = 'Could not load users.' });
    this.admin.logins().subscribe({ next: logins => { this.logins = logins; this.loaded = true; }, error: () => this.loaded = true });
  }
  lock(user: AdminUser): void {
    this.admin.lock(user.id).subscribe({ next: updated => Object.assign(user, updated), error: error => this.message = error.error?.message ?? 'Could not lock that account.' });
  }
  unlock(user: AdminUser): void {
    this.admin.unlock(user.id).subscribe({ next: updated => Object.assign(user, updated), error: error => this.message = error.error?.message ?? 'Could not unlock that account.' });
  }
  resetMfa(user: AdminUser): void {
    this.admin.resetMfa(user.id).subscribe({ next: updated => Object.assign(user, updated), error: error => this.message = error.error?.message ?? 'Could not reset MFA.' });
  }
}
