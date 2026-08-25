import { Component } from '@angular/core';
import { NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../core/auth.service';

@Component({
  standalone: true, imports: [FormsModule, RouterLink, NgIf],
  template: `
    <main class="auth-page"><section class="auth-art"><a class="brand light-brand" routerLink="/"><span class="brand-mark">S</span><span>Suffer<span class="muted">Tracker</span></span></a><div class="art-copy"><div class="eyebrow">Your next chapter</div><h1>Track the hunt.<br><em>Own the outcome.</em></h1><p>A calmer, clearer way to move through the job search.</p></div><div class="art-stat"><strong>14,208</strong><span>applications tracked this week</span></div></section><section class="auth-form-wrap"><div class="auth-form"><ng-container *ngIf="!mfaRequired; else mfaStep"><div class="eyebrow">Welcome back</div><h2>Sign in to your workspace</h2><p class="subtle">Your job search, in one focused place.</p><form (ngSubmit)="submit()"><label>Email address<input type="email" name="email" [(ngModel)]="email" required placeholder="you@example.com"></label><label>Password<input type="password" name="password" [(ngModel)]="password" required placeholder="8+ characters"></label><div class="form-error" *ngIf="error">{{ error }}</div><button class="primary-button full" type="submit" [disabled]="loading">{{ loading ? 'Signing in...' : 'Continue' }} <span>→</span></button></form><p class="auth-switch">New here? <a routerLink="/login" (click)="registerMode = !registerMode">{{ registerMode ? 'Sign in' : 'Create an account' }}</a></p><form *ngIf="registerMode" class="register-form" (ngSubmit)="register()"><label>Your name<input type="text" name="name" [(ngModel)]="displayName" required placeholder="Alex Morgan"></label><button class="secondary-button full" type="submit">Create account</button></form></ng-container><ng-template #mfaStep><div class="eyebrow">Two-factor authentication</div><h2>Enter your code</h2><p class="subtle">Type the 6-digit code from your authenticator app for {{ email }}.</p><form (ngSubmit)="submit()"><label>Authenticator code<input inputmode="numeric" autocomplete="one-time-code" name="code" [(ngModel)]="code" maxlength="7" placeholder="123456" required></label><div class="form-error" *ngIf="error">{{ error }}</div><button class="primary-button full" type="submit" [disabled]="loading">{{ loading ? 'Verifying...' : 'Verify and sign in' }} <span>→</span></button><button class="link-button" type="button" (click)="backToPassword()">Use a different account</button></form></ng-template></div><div class="auth-footer">Private by design <span>·</span> Built for the long game</div></section></main>`
})
export class LoginComponent {
  email = ''; password = ''; displayName = ''; code = ''; error = ''; loading = false; registerMode = false; mfaRequired = false;
  constructor(private readonly auth: AuthService, private readonly router: Router) {}
  submit(): void {
    this.error = ''; this.loading = true;
    this.auth.login(this.email, this.password, this.mfaRequired ? this.code : undefined).subscribe({
      next: () => void this.router.navigate(['/dashboard']),
      error: response => {
        if (response?.error?.mfaRequired) { this.mfaRequired = true; this.error = ''; }
        else this.error = this.mfaRequired ? 'That code did not match. Wait for the next one and try again.' : 'Could not sign in with those details.';
        this.loading = false;
      }
    });
  }
  backToPassword(): void { this.mfaRequired = false; this.code = ''; this.error = ''; this.loading = false; }
  register(): void { this.error = ''; this.auth.register(this.email, this.password, this.displayName).subscribe({ next: () => void this.router.navigate(['/dashboard']), error: () => this.error = 'Could not create the account. Check your details.' }); }
}
