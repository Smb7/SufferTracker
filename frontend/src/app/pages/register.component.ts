import { Component } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../core/auth.service';

@Component({
  standalone: true, imports: [FormsModule, RouterLink, NgIf],
  template: `
    <main class="auth-page"><section class="auth-art"><a class="brand light-brand" routerLink="/"><span class="brand-mark">S</span><span>Suffer<span class="muted">Tracker</span></span></a><div class="art-copy"><div class="eyebrow">Start in minutes</div><h1>Your pipeline,<br><em>from day one.</em></h1><p>Create an account and capture your first application before your coffee cools.</p></div><div class="art-stat"><strong>Free</strong><span>no card, no trial clock</span></div></section><section class="auth-form-wrap"><div class="auth-form"><div class="eyebrow">Create account</div><h2>Set up your workspace</h2><p class="subtle">One workspace for every application, interview, and outcome.</p><form (ngSubmit)="submit()"><label>Full name<input type="text" name="displayName" [(ngModel)]="displayName" required autocomplete="name" placeholder="Alex Morgan"></label><label>Email address<input type="email" name="email" [(ngModel)]="email" required autocomplete="email" placeholder="you@example.com"></label><label>Password <small>At least 8 characters.</small><input type="password" name="password" [(ngModel)]="password" required minlength="8" autocomplete="new-password" placeholder="8+ characters"></label><label>Confirm password<input type="password" name="confirmPassword" [(ngModel)]="confirmPassword" required minlength="8" autocomplete="new-password" placeholder="Repeat your password"></label><div class="form-error" *ngIf="error">{{ error }}</div><button class="primary-button full" type="submit" [disabled]="loading || !formValid()">{{ loading ? 'Creating account...' : 'Create Account' }} <span>→</span></button></form><p class="auth-switch">Already have a workspace? <a routerLink="/login">Log in</a></p></div><div class="auth-footer">Private by design <span>·</span> Built for the long game</div></section></main>`
})
export class RegisterComponent {
  displayName = ''; email = ''; password = ''; confirmPassword = ''; error = ''; loading = false;
  constructor(private readonly auth: AuthService, private readonly http: HttpClient, private readonly router: Router) {
    this.http.get<{ applicationsThisWeek: number }>('/api/stats/public').subscribe({ error: () => {} });
  }
  formValid(): boolean {
    return this.displayName.trim().length > 0 && this.email.trim().length > 0 && this.password.length >= 8 && this.password === this.confirmPassword;
  }
  submit(): void {
    this.error = '';
    if (!this.formValid()) { this.error = this.password !== this.confirmPassword ? 'Passwords do not match.' : 'Fill every field; passwords need at least 8 characters.'; return; }
    this.loading = true;
    this.auth.register(this.email.trim(), this.password, this.displayName.trim()).subscribe({
      next: () => void this.router.navigate(['/dashboard']),
      error: response => {
        this.error = response?.status === 409 ? (response.error?.message ?? 'An account with that email already exists.') : 'Could not create the account. Check your details.';
        this.loading = false;
      }
    });
  }
}
