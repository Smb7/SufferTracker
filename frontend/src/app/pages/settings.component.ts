import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { NgIf } from '@angular/common';
import { AuthService } from '../core/auth.service';
import { PreferencesService } from '../core/preferences.service';
import { MfaSetup, Preferences } from '../core/models';

@Component({ standalone: true, imports: [FormsModule, NgIf], template: `
  <header class="page-header"><div><div class="eyebrow">Workspace controls</div><h1>Settings</h1><p class="subtle">Make SufferTracker work like you do.</p></div></header>
  <div class="settings-layout"><nav class="settings-nav"><button *ngFor="let section of sections" [class.active]="activeSection === section.id" (click)="scrollTo(section.id)">{{ section.label }}</button></nav><section class="settings-content"><div class="panel settings-panel" id="settings-profile"><div class="panel-heading"><div><div class="eyebrow">Profile</div><h2>Your details</h2></div></div><label>Display name<input [(ngModel)]="displayName"></label><label>Email address<input [(ngModel)]="email" type="email"></label><label>New password <small>Leave blank to keep your current password.</small><input [(ngModel)]="password" type="password"></label><button class="primary-button" (click)="saveProfile()">Save profile</button><span class="save-message" *ngIf="message">{{ message }}</span></div><div class="panel settings-panel" id="settings-preferences"><div class="panel-heading"><div><div class="eyebrow">Preferences</div><h2>How you see the hunt</h2></div></div><div class="setting-line"><div><strong>Dark mode</strong><p>Keep the interface easy on your eyes. Saves instantly.</p></div><button class="toggle" [class.on]="preferences.darkMode" (click)="toggleDarkMode()"><span></span></button></div><label>Default dashboard view<select [(ngModel)]="preferences.defaultView"><option value="pulse">Pulse overview</option><option value="kanban">Kanban board</option><option value="sankey">Sankey flow</option><option value="funnel">Funnel chart</option><option value="line">Cumulative line</option><option value="bar">Stacked bar</option></select></label><label>Interview rounds <strong class="range-value">{{ preferences.interviewRounds }}</strong><input type="range" min="1" max="10" [(ngModel)]="preferences.interviewRounds"></label><button class="secondary-button" (click)="savePreferences()">Save preferences</button></div><div class="panel settings-panel" id="settings-security"><div class="panel-heading"><div><div class="eyebrow">Security</div><h2>Multi-factor authentication</h2></div></div><ng-container *ngIf="!mfaSetup && !mfaEnabled; else mfaActive"><div class="setting-line"><div><strong>MFA is off</strong><p>Add a one-time code from an authenticator app such as Google Authenticator or 1Password at every sign-in.</p></div><button class="primary-button" (click)="startMfa()" [disabled]="mfaBusy">{{ mfaBusy ? 'Preparing...' : 'Set up MFA' }}</button></div></ng-container><ng-template #mfaActive><ng-container *ngIf="!mfaSetup"><div class="setting-line"><div><strong>MFA is on</strong><p>Your account requires an authenticator code when signing in.</p></div><button class="danger-button" (click)="disableMode = !disableMode">{{ disableMode ? 'Cancel' : 'Turn off' }}</button></div><div class="mfa-code-row" *ngIf="disableMode"><label>Confirm with an authenticator code<input inputmode="numeric" maxlength="7" [(ngModel)]="code" placeholder="123456"></label><button class="danger-button" (click)="disableMfa()" [disabled]="mfaBusy || !code">Turn off MFA</button></div></ng-container></ng-template><ng-container *ngIf="mfaSetup"><ol class="mfa-steps"><li>Add the account to your authenticator app using the key below, or open the one-tap link.</li><li>Type the current 6-digit code to finish enabling MFA.</li></ol><div class="mfa-secret"><code>{{ mfaSetup.secret }}</code><button class="secondary-button" type="button" (click)="copySecret()">{{ copied ? 'Copied!' : 'Copy key' }}</button></div><p class="subtle mfa-uri">One-tap link: <a [href]="mfaSetup.otpauthUri">{{ mfaSetup.otpauthUri }}</a></p><div class="mfa-code-row"><label>Authenticator code<input inputmode="numeric" autocomplete="one-time-code" maxlength="7" [(ngModel)]="code" placeholder="123456"></label><button class="primary-button" (click)="enableMfa()" [disabled]="mfaBusy || !code">{{ mfaBusy ? 'Verifying...' : 'Enable MFA' }}</button></div><div class="form-error" *ngIf="message">{{ message }}</div></ng-container></div><div class="panel danger-panel" id="settings-danger"><div><div class="eyebrow">Danger zone</div><h2>Delete account</h2><p>This permanently removes your profile and every application.</p></div><button class="danger-button" (click)="deleteAccount()">Delete account</button></div></section></div>` })
export class SettingsComponent implements OnInit {
  email = ''; displayName = ''; password = ''; message = '';
  preferences: Preferences = { darkMode: true, defaultView: 'kanban', interviewRounds: 3 };
  mfaEnabled = false; mfaSetup: MfaSetup | null = null; disableMode = false; mfaBusy = false; code = ''; copied = false;
  sections = [
    { id: 'profile', label: 'Profile' },
    { id: 'preferences', label: 'Preferences' },
    { id: 'security', label: 'Security' },
    { id: 'danger', label: 'Danger zone' }
  ];
  activeSection = 'profile';
  constructor(private readonly auth: AuthService, private readonly preferenceService: PreferencesService) {
    this.preferences.darkMode = preferenceService.theme() === 'dark';
  }
  ngOnInit(): void {
    const user = this.auth.user();
    if (user) { this.email = user.email; this.displayName = user.displayName; }
    this.preferenceService.get().subscribe({ next: value => this.preferences = value });
    this.auth.mfaStatus().subscribe({ next: status => this.mfaEnabled = status.enabled });
  }
  scrollTo(sectionId: string): void {
    this.activeSection = sectionId;
    document.getElementById(`settings-${sectionId}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  applyTheme(): void { this.preferenceService.applyTheme(this.preferences.darkMode); }
  toggleDarkMode(): void {
    this.preferences.darkMode = !this.preferences.darkMode;
    this.applyTheme();
    this.preferenceService.update(this.preferences).subscribe({ next: () => this.message = 'Dark mode saved.', error: () => this.message = 'Could not save dark mode.' });
  }
  saveProfile(): void { this.auth.updateProfile(this.displayName, this.email, this.password).subscribe({ next: () => { this.password = ''; this.message = 'Profile saved.'; }, error: () => this.message = 'Could not save profile.' }); }
  savePreferences(): void { this.preferenceService.update(this.preferences).subscribe({ next: () => this.message = 'Preferences saved.' }); }
  startMfa(): void {
    this.mfaBusy = true; this.message = '';
    this.auth.startMfaSetup().subscribe({ next: setup => { this.mfaSetup = setup; this.code = ''; this.mfaBusy = false; }, error: () => { this.message = 'Could not start MFA setup.'; this.mfaBusy = false; } });
  }
  enableMfa(): void {
    if (!this.mfaSetup) return;
    this.mfaBusy = true; this.message = '';
    this.auth.enableMfa(this.code).subscribe({ next: () => { this.mfaEnabled = true; this.mfaSetup = null; this.code = ''; this.message = 'MFA enabled. You will need a code at next sign-in.'; this.mfaBusy = false; }, error: () => { this.message = 'That code was not valid. Try the newest one.'; this.mfaBusy = false; } });
  }
  disableMfa(): void {
    this.mfaBusy = true; this.message = '';
    this.auth.disableMfa(this.code).subscribe({ next: () => { this.mfaEnabled = false; this.disableMode = false; this.code = ''; this.message = 'MFA disabled.'; this.mfaBusy = false; }, error: () => { this.message = 'That code was not valid. MFA is still on.'; this.mfaBusy = false; } });
  }
  copySecret(): void { if (!this.mfaSetup) return; void navigator.clipboard?.writeText(this.mfaSetup.secret); this.copied = true; setTimeout(() => this.copied = false, 2000); }
  deleteAccount(): void { if (confirm('Permanently delete your account and applications?')) this.auth.deleteAccount().subscribe({ next: () => this.auth.logout() }); }
}
