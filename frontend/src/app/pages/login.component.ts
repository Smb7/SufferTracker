import { Component } from '@angular/core';
import { NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../core/auth.service';

@Component({
  standalone: true, imports: [FormsModule, RouterLink, NgIf],
  template: `
    <main class="auth-page"><section class="auth-art"><a class="brand light-brand" routerLink="/"><span class="brand-mark">S</span><span>Suffer<span class="muted">Tracker</span></span></a><div class="art-copy"><div class="eyebrow">Your next chapter</div><h1>Track the hunt.<br><em>Own the outcome.</em></h1><p>A calmer, clearer way to move through the job search.</p></div><div class="art-stat"><strong>14,208</strong><span>applications tracked this week</span></div></section><section class="auth-form-wrap"><div class="auth-form"><div class="eyebrow">Welcome back</div><h2>Sign in to your workspace</h2><p class="subtle">Your job search, in one focused place.</p><form (ngSubmit)="submit()"><label>Email address<input type="email" name="email" [(ngModel)]="email" required placeholder="you@example.com"></label><label>Password<input type="password" name="password" [(ngModel)]="password" required placeholder="8+ characters"></label><div class="form-error" *ngIf="error">{{ error }}</div><button class="primary-button full" type="submit" [disabled]="loading">{{ loading ? 'Signing in...' : 'Continue' }} <span>→</span></button></form><p class="auth-switch">New here? <a routerLink="/login" (click)="registerMode = !registerMode">{{ registerMode ? 'Sign in' : 'Create an account' }}</a></p><form *ngIf="registerMode" class="register-form" (ngSubmit)="register()"><label>Your name<input type="text" name="name" [(ngModel)]="displayName" required placeholder="Alex Morgan"></label><button class="secondary-button full" type="submit">Create account</button></form></div><div class="auth-footer">Private by design <span>·</span> Built for the long game</div></section></main>`
})
export class LoginComponent {
  email = ''; password = ''; displayName = ''; error = ''; loading = false; registerMode = false;
  constructor(private readonly auth: AuthService, private readonly router: Router) {}
  submit(): void { this.error = ''; this.loading = true; this.auth.login(this.email, this.password).subscribe({ next: () => void this.router.navigate(['/dashboard']), error: () => { this.error = 'Could not sign in with those details.'; this.loading = false; } }); }
  register(): void { this.error = ''; this.auth.register(this.email, this.password, this.displayName).subscribe({ next: () => void this.router.navigate(['/dashboard']), error: () => this.error = 'Could not create the account. Check your details.' }); }
}
