namespace JobTracker.Api.Models;

public sealed class JobApplication
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid UserId { get; set; }
    public required string Company { get; set; }
    public required string Title { get; set; }
    public string Description { get; set; } = string.Empty;
    public string Skills { get; set; } = string.Empty;
    public string Pay { get; set; } = string.Empty;
    public string Location { get; set; } = string.Empty;
    public string Nickname { get; set; } = string.Empty;
    public string? SourceUrl { get; set; }
    public JobStatus Status { get; set; } = JobStatus.Waiting;
    public int? InterviewRound { get; set; }
    public DateTime AppliedAtUtc { get; set; } = DateTime.UtcNow;
    public DateTime UpdatedAtUtc { get; set; } = DateTime.UtcNow;
    public User? User { get; set; }
}
