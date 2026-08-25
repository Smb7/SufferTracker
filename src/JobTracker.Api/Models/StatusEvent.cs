namespace JobTracker.Api.Models;

public sealed class StatusEvent
{
    public JobStatus Status { get; set; }
    public DateTime OccurredAtUtc { get; set; } = DateTime.UtcNow;
}
