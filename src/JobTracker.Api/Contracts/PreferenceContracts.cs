namespace JobTracker.Api.Contracts;

public sealed record UpdatePreferencesRequest(bool DarkMode, string DefaultView, int InterviewRounds);
public sealed record PreferencesResponse(bool DarkMode, string DefaultView, int InterviewRounds);
