export type JobStatus = 'Waiting' | 'Interview' | 'JobOffer' | 'Ghosted' | 'Rejected' | 'Applied';
export interface AuthResponse { token: string; userId: string; email: string; displayName: string; isAdmin?: boolean; }
export interface AdminUser { id: string; email: string; displayName: string; mfaEnabled: boolean; isLocked: boolean; isAdmin: boolean; createdAtUtc: string; }
export interface LoginEvent { id: string; username: string; mfaEnabled: boolean; ipAddress: string; succeeded: boolean; occurredAtUtc: string; latitude?: number | null; longitude?: number | null; city?: string | null; country?: string | null; }
export interface Job { id: string; company: string; title: string; description: string; skills: string; pay: string; location: string; nickname: string; sourceUrl?: string; status: JobStatus; interviewRound?: number; statusEvents?: { status: JobStatus }[]; appliedAtUtc: string; updatedAtUtc: string; }
export interface ParsedJob { company: string; title: string; description: string; skills: string; pay: string; location: string; sourceUrl?: string; notice?: string; }
export interface Preferences { darkMode: boolean; defaultView: string; interviewRounds: number; }
export interface MfaSetup { secret: string; otpauthUri: string; }
export interface MfaStatus { enabled: boolean; }
export interface ExperienceItem { title: string; company: string; start: string; end: string; highlights: string; }
export interface EducationItem { institution: string; credential: string; field: string; year: string; notes: string; }
export interface CareerGoals { targetRoles: string[]; industries: string[]; locations: string[]; workStyle: string; compensation: string; timeline: string; narrative: string; constraints: string; }
export interface CareerContext { status: 'not_started' | 'in_progress' | 'completed'; summary: string; experience: ExperienceItem[]; education: EducationItem[]; skills: string[]; interests: string[]; goals: CareerGoals; missing: string[]; provider: string; notice: string; updatedAtUtc: string; }
export interface OnboardingMessage { id: string; role: 'assistant' | 'user' | string; content: string; createdAtUtc: string; }
export interface OnboardingState { context: CareerContext; messages: OnboardingMessage[]; providerConfigured: boolean; }
