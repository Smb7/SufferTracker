import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Job, JobStatus, ParsedJob } from './models';

/** Builds the progressive status timeline for a target status. 'Applied' always comes first;
 *  interviews append one event per recorded round; Job Offer requires at least one interview. */
export function timelineFor(status: JobStatus, interviewRound?: number | null): JobStatus[] {
  const timeline: JobStatus[] = ['Applied'];
  switch (status) {
    case 'Waiting':
      break;
    case 'Interview': {
      const rounds = Math.min(10, Math.max(1, interviewRound ?? 1));
      for (let round = 1; round <= rounds; round++) timeline.push('Interview');
      break;
    }
    case 'JobOffer':
      timeline.push('Interview');
      timeline.push('JobOffer');
      break;
    default:
      timeline.push(status);
      break;
  }
  return timeline;
}

@Injectable({ providedIn: 'root' })
export class JobsService {
  private readonly endpoint = '/api/jobs';
  constructor(private readonly http: HttpClient) {}
  list() { return this.http.get<Job[]>(this.endpoint); }
  parseText(text: string) { const body = new FormData(); body.set('inputType', 'Text'); body.set('text', text); return this.http.post<ParsedJob>(`${this.endpoint}/parse`, body); }
  parseLink(url: string) { const body = new FormData(); body.set('inputType', 'Link'); body.set('url', url); return this.http.post<ParsedJob>(`${this.endpoint}/parse`, body); }
  parseScreenshot(image: File) { const body = new FormData(); body.set('inputType', 'Screenshot'); body.append('image', image, image.name); return this.http.post<ParsedJob>(`${this.endpoint}/parse`, body); }
  create(job: Partial<Job> & { company: string; title: string }) {
    const status = job.status ?? 'Applied';
    const timeline = timelineFor(status, job.interviewRound);
    return this.http.post<Job>(this.endpoint, { ...job, status: timeline[timeline.length - 1], timeline });
  }
  /** Throws when moving to 'JobOffer' without any recorded interview stage. */
  update(id: string, job: Partial<Job> & { status?: JobStatus }) {
    const status = job.status ?? 'Applied';
    const hasInterview = job.statusEvents?.some(event => event.status === 'Interview')
      || job.status === 'Interview'
      || (job.interviewRound ?? 0) > 0;
    if (status === 'JobOffer' && !hasInterview)
      throw new Error('Record at least one interview stage before marking a job offer.');
    const timeline = timelineFor(status, status === 'Interview' ? Math.max(1, job.interviewRound ?? 1) : undefined);
    return this.http.put<Job>(`${this.endpoint}/${id}`, { ...job, status: timeline[timeline.length - 1], timeline });
  }
  delete(id: string) { return this.http.delete(`${this.endpoint}/${id}`); }
}
