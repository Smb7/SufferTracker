import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Preferences } from './models';
import { tap } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class PreferencesService {
  private readonly endpoint = 'http://localhost:8080/api/preferences';
  constructor(private readonly http: HttpClient) {}
  get() { return this.http.get<Preferences>(this.endpoint); }
  update(preferences: Preferences) { return this.http.put<Preferences>(this.endpoint, preferences).pipe(tap(value => this.applyTheme(value.darkMode))); }
  applyTheme(dark: boolean): void { document.documentElement.classList.toggle('light', !dark); }
}
