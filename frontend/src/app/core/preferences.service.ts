import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Preferences } from './models';
import { switchMap, tap } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class PreferencesService {
  private readonly endpoint = '/api/preferences';
  constructor(private readonly http: HttpClient) {}
  get() { return this.http.get<Preferences>(this.endpoint); }
  update(preferences: Preferences) { return this.http.put<Preferences>(this.endpoint, preferences).pipe(tap(value => this.applyTheme(value.darkMode))); }
  /** Persists only the dashboard layout choice against freshly read server state, leaving darkMode/interviewRounds untouched. */
  updateDefaultView(defaultView: string) {
    return this.get().pipe(switchMap(current => this.http.put<Preferences>(this.endpoint, { ...current, defaultView }).pipe(tap(() => this.applyTheme(current.darkMode)))));
  }
  readonly theme = signal<'dark' | 'light'>('light');
  applyTheme(dark: boolean): void { document.documentElement.classList.toggle('dark', dark); this.theme.set(dark ? 'dark' : 'light'); }
  /** Fetches the saved preference and applies the theme to <html>. Safe to call at startup and after sign-in. */
  loadTheme(): void { this.get().subscribe({ next: preferences => this.applyTheme(preferences.darkMode), error: () => {} }); }
}
