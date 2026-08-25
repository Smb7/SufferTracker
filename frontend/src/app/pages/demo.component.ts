import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { NgIf } from '@angular/common';
import { RouterLink } from '@angular/router';
import { DemoShowcaseComponent } from './demo-showcase.component';

@Component({
  standalone: true,
  imports: [RouterLink, NgIf, DemoShowcaseComponent],
  template: `
    <main class="demo-page">
      <header class="demo-nav">
        <a class="brand light-brand" routerLink="/"><span class="brand-mark">S</span><span>Suffer<span class="muted">Tracker</span></span></a>
        <nav><a routerLink="/login" class="ghost-link">Log in</a><a routerLink="/register" class="primary-button small">Create account</a></nav>
      </header>

      <section class="demo-hero">
        <div class="eyebrow">Built for the long game</div>
        <h1>Every application.<br><em>One clear picture.</em></h1>
        <p class="subtle">Stop losing track of where you applied, what they said, and which door is still open. SufferTracker turns scattered applications into a pipeline you can actually read.</p>
        <div class="hero-actions">
          <a routerLink="/register" class="primary-button">Start tracking free <span>→</span></a>
          <a routerLink="/login" class="secondary-button">Log in</a>
        </div>
        <div class="hero-stat" *ngIf="applicationsThisWeek !== null"><strong>{{ applicationsThisWeek.toLocaleString() }}</strong><span>applications tracked this week</span></div>
      </section>

      <section class="demo-showcase-section">
        <div class="demo-showcase-heading"><div class="eyebrow">See the product</div><h2>Six ways to read your search</h2></div>
        <st-demo-showcase />
      </section>

      <section class="demo-grid">
        <article class="demo-card"><h3>Capture any way</h3><p>Paste a link, drop in raw text, or upload — even paste — a screenshot. The parser pulls out company, title, pay, and location.</p></article>
        <article class="demo-card"><h3>A pipeline you drag</h3><p>Kanban columns for every stage, including configurable interview rounds one through ten. Drag a card, status updated.</p></article>
        <article class="demo-card"><h3>See the flow</h3><p>Sankey, funnel, and cumulative charts answer the only question that matters: is this search moving?</p></article>
        <article class="demo-card"><h3>Nicknames &amp; notes</h3><p>Name roles whatever helps you remember them — "the dream gig", "that startup" — then filter in one keystroke.</p></article>
        <article class="demo-card"><h3>Private by design</h3><p>Your data stays yours: JWT auth, optional multi-factor, and hard delete whenever you want out.</p></article>
        <article class="demo-card"><h3>Easy on the eyes</h3><p>A calm dark mode for late-night applying, saved to your account across devices.</p></article>
      </section>

      <section class="demo-steps">
        <div class="step"><span>1</span><div><h3>Capture</h3><p>Add a job in seconds from wherever you found it.</p></div></div>
        <div class="step"><span>2</span><div><h3>Track</h3><p>Drag it through interviews, offers, ghosting, and rejections.</p></div></div>
        <div class="step"><span>3</span><div><h3>Learn</h3><p>Read your funnel and double down on what works.</p></div></div>
      </section>

      <section class="demo-band">
        <h2>Your next offer is already out there.<br>Keep score until it lands.</h2>
        <div class="hero-actions center">
          <a routerLink="/register" class="primary-button">Create your account <span>→</span></a>
          <a routerLink="/login" class="ghost-link">Already tracking? Log in</a>
        </div>
      </section>

      <footer class="demo-footer">SufferTracker · Every no is data.</footer>
    </main>
  `
})
export class DemoComponent implements OnInit {
  applicationsThisWeek: number | null = null;
  constructor(private readonly http: HttpClient) {}
  ngOnInit(): void {
    this.http.get<{ applicationsThisWeek: number }>('/api/stats/public').subscribe({
      next: stats => this.applicationsThisWeek = stats.applicationsThisWeek > 0 ? stats.applicationsThisWeek : null,
      error: () => this.applicationsThisWeek = null
    });
  }
}
