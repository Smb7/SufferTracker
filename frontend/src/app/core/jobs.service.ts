import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Job, JobStatus, ParsedJob } from './models';

@Injectable({ providedIn: 'root' })
export class JobsService {
  private readonly endpoint = '/api/jobs';
  constructor(private readonly http: HttpClient) {}
  list() { return this.http.get<Job[]>(this.endpoint); }
  parseText(text: string) { const body = new FormData(); body.set('inputType', 'Text'); body.set('text', text); return this.http.post<ParsedJob>(`${this.endpoint}/parse`, body); }
  parseLink(url: string) { const body = new FormData(); body.set('inputType', 'Link'); body.set('url', url); return this.http.post<ParsedJob>(`${this.endpoint}/parse`, body); }
  parseScreenshot(image: File) { const body = new FormData(); body.set('inputType', 'Screenshot'); body.append('image', image, image.name); return this.http.post<ParsedJob>(`${this.endpoint}/parse`, body); }
  create(job: Partial<Job> & { company: string; title: string }) { return this.http.post<Job>(this.endpoint, { ...job, status: job.status ?? 'Waiting' as JobStatus }); }
  update(id: string, job: Partial<Job>) { return this.http.put<Job>(`${this.endpoint}/${id}`, job); }
  delete(id: string) { return this.http.delete(`${this.endpoint}/${id}`); }
}
