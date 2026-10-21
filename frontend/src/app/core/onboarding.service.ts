import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CareerContext, OnboardingState } from './models';

@Injectable({ providedIn: 'root' })
export class OnboardingService {
  private readonly endpoint = '/api/onboarding';
  constructor(private readonly http: HttpClient) {}
  state() { return this.http.get<OnboardingState>(this.endpoint); }
  context() { return this.http.get<CareerContext>(`${this.endpoint}/context`); }
  send(content: string) { return this.http.post<OnboardingState>(`${this.endpoint}/messages`, { content }); }
  update(body: Partial<CareerContext>) { return this.http.put<CareerContext>(`${this.endpoint}/context`, body); }
  complete() { return this.http.post<OnboardingState>(`${this.endpoint}/complete`, {}); }
  reopen() { return this.http.post<CareerContext>(`${this.endpoint}/reopen`, {}); }
  reset() { return this.http.post<OnboardingState>(`${this.endpoint}/reset`, {}); }
}
