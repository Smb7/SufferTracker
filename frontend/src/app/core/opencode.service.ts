import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { OpenCodeModel, OpenCodeStatus, OpenCodeTest } from './models';

@Injectable({ providedIn: 'root' })
export class OpenCodeService {
  private readonly endpoint = '/api/integrations/opencode';
  constructor(private readonly http: HttpClient) {}
  status() { return this.http.get<OpenCodeStatus>(this.endpoint); }
  models() { return this.http.get<OpenCodeModel[]>(`${this.endpoint}/models`); }
  save(apiKey: string, modelId: string) { return this.http.put<OpenCodeStatus>(this.endpoint, { apiKey, modelId }); }
  test() { return this.http.post<OpenCodeTest>(`${this.endpoint}/test`, {}); }
  disconnect() { return this.http.delete(this.endpoint); }
}
