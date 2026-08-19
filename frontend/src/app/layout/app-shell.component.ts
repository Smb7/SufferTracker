import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from '../core/auth.service';

@Component({
  standalone: true, imports: [RouterLink, RouterLinkActive, RouterOutlet],
  template: `
    <div class="app-frame">
      <aside class="sidebar">
        <a class="brand" routerLink="/dashboard"><span class="brand-mark">S</span><span>Suffer<span class="muted">Tracker</span></span></a>
        <div class="eyebrow side-label">Workspace</div>
        <nav>
          <a routerLink="/dashboard" routerLinkActive="active"><span class="nav-icon">◈</span> Overview</a>
          <a routerLink="/jobs" routerLinkActive="active"><span class="nav-icon">□</span> Applications</a>
          <a routerLink="/settings" routerLinkActive="active"><span class="nav-icon">⚙</span> Settings</a>
        </nav>
        <div class="sidebar-bottom">
          <div class="mini-tip"><span class="tip-dot"></span><div><strong>Keep moving</strong><small>Every no is data.</small></div></div>
          <button class="profile-button" (click)="logout()"><span class="avatar">{{ initials }}</span><span class="profile-name">{{ auth.user()?.displayName || 'My account' }}<small>Sign out</small></span><span class="logout">↗</span></button>
        </div>
      </aside>
      <main class="main-content"><router-outlet /></main>
    </div>`
})
export class AppShellComponent {
  constructor(public readonly auth: AuthService) {}
  get initials(): string { return (this.auth.user()?.displayName || 'ST').split(' ').map(part => part[0]).join('').slice(0, 2).toUpperCase(); }
  logout(): void { this.auth.logout(); }
}
