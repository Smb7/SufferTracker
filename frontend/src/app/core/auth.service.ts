import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { tap } from 'rxjs';
import { AuthResponse, MfaSetup, MfaStatus } from './models';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly endpoint = 'http://localhost:8080/api/auth';
  readonly user = signal<AuthResponse | null>(this.readUser());
  constructor(private readonly http: HttpClient, private readonly router: Router) {}
  get token(): string | null { return localStorage.getItem('st_token'); }
  login(email: string, password: string, code?: string) { return this.http.post<AuthResponse>(`${this.endpoint}/login`, { email, password, code: code || null }).pipe(tap(response => this.store(response))); }
  register(email: string, password: string, displayName: string) { return this.http.post<AuthResponse>(`${this.endpoint}/register`, { email, password, displayName }).pipe(tap(response => this.store(response))); }
  updateProfile(displayName: string, email: string, newPassword: string) { return this.http.put<AuthResponse>(`${this.endpoint}/profile`, { displayName, email, newPassword: newPassword || null }).pipe(tap(response => this.store(response))); }
  deleteAccount() { return this.http.delete(`${this.endpoint}/account`); }
  mfaStatus() { return this.http.get<MfaStatus>(`${this.endpoint}/mfa/status`); }
  startMfaSetup() { return this.http.post<MfaSetup>(`${this.endpoint}/mfa/setup`, {}); }
  enableMfa(code: string) { return this.http.post<MfaStatus>(`${this.endpoint}/mfa/enable`, { code }); }
  disableMfa(code: string) { return this.http.post<MfaStatus>(`${this.endpoint}/mfa/disable`, { code }); }
  logout(): void { localStorage.removeItem('st_token'); localStorage.removeItem('st_user'); this.user.set(null); void this.router.navigate(['/login']); }
  private store(response: AuthResponse): void { localStorage.setItem('st_token', response.token); localStorage.setItem('st_user', JSON.stringify(response)); this.user.set(response); }
  private readUser(): AuthResponse | null { const value = localStorage.getItem('st_user'); try { return value ? JSON.parse(value) as AuthResponse : null; } catch { return null; } }
}
