namespace JobTracker.Api.Models;

public sealed class User
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public required string Email { get; set; }
    public required string PasswordHash { get; set; }
    public string DisplayName { get; set; } = string.Empty;
    public bool MfaEnabled { get; set; }
    public string? MfaSecret { get; set; }
    public bool IsAdmin { get; set; }
    public bool IsLocked { get; set; }
    public DateTime CreatedAtUtc { get; set; } = DateTime.UtcNow;
    public ICollection<JobApplication> Jobs { get; set; } = new List<JobApplication>();
    public UserPreference? Preferences { get; set; }
}
