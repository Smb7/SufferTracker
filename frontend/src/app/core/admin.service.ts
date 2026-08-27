import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { AdminUser, LoginEvent } from './models';

@Injectable({ providedIn: 'root' })
export class AdminService {
  private readonly endpoint = '/api/admin';
  constructor(private readonly http: HttpClient) {}
  users() { return this.http.get<AdminUser[]>(`${this.endpoint}/users`); }
  logins() { return this.http.get<LoginEvent[]>(`${this.endpoint}/logins`); }
  lock(id: string) { return this.http.post<AdminUser>(`${this.endpoint}/users/${id}/lock`, {}); }
  unlock(id: string) { return this.http.post<AdminUser>(`${this.endpoint}/users/${id}/unlock`, {}); }
  resetMfa(id: string) { return this.http.post<AdminUser>(`${this.endpoint}/users/${id}/reset-mfa`, {}); }
}
