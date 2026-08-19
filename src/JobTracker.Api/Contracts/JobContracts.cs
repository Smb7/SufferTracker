using JobTracker.Api.Models;

namespace JobTracker.Api.Contracts;

public sealed record ParseJobRequest(InputType InputType, string? Text, string? Url);
public sealed record ParsedJobResponse(string Company, string Title, string Description, string Skills, string Pay, string Location, string? SourceUrl, string? Notice);
public sealed record CreateJobRequest(string Company, string Title, string? Description, string? Skills, string? Pay, string? Location, string? Nickname, string? SourceUrl, JobStatus Status, int? InterviewRound, DateTime? AppliedAtUtc);
public sealed record UpdateJobRequest(string Company, string Title, string? Description, string? Skills, string? Pay, string? Location, string? Nickname, JobStatus Status, int? InterviewRound, DateTime? AppliedAtUtc);
public sealed record JobResponse(Guid Id, string Company, string Title, string Description, string Skills, string Pay, string Location, string Nickname, string? SourceUrl, JobStatus Status, int? InterviewRound, DateTime AppliedAtUtc, DateTime UpdatedAtUtc);
