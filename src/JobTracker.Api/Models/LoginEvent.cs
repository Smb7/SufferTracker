namespace JobTracker.Api.Models;

public sealed class LoginEvent
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid? UserId { get; set; }
    public required string Username { get; set; }
    public bool MfaEnabled { get; set; }
    public required string IpAddress { get; set; }
    public bool Succeeded { get; set; }
    public DateTime OccurredAtUtc { get; set; } = DateTime.UtcNow;
    public double? Latitude { get; set; }
    public double? Longitude { get; set; }
    public string? City { get; set; }
    public string? Country { get; set; }
}
