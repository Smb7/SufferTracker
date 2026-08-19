export type JobStatus = 'Waiting' | 'Interview' | 'JobOffer' | 'Ghosted' | 'Rejected';
export interface AuthResponse { token: string; userId: string; email: string; displayName: string; }
export interface Job { id: string; company: string; title: string; description: string; skills: string; pay: string; location: string; nickname: string; sourceUrl?: string; status: JobStatus; interviewRound?: number; appliedAtUtc: string; updatedAtUtc: string; }
export interface ParsedJob { company: string; title: string; description: string; skills: string; pay: string; location: string; sourceUrl?: string; notice?: string; }
export interface Preferences { darkMode: boolean; defaultView: string; interviewRounds: number; mfaEnabled: boolean; }
