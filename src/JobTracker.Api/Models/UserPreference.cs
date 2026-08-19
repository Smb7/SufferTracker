namespace JobTracker.Api.Models;

public sealed class UserPreference
{
    public Guid UserId { get; set; }
    public bool DarkMode { get; set; } = true;
    public string DefaultView { get; set; } = "kanban";
    public int InterviewRounds { get; set; } = 3;
    public bool MfaEnabled { get; set; }
    public User? User { get; set; }
}
