namespace JobTracker.Api.Contracts;

public sealed record UpdatePreferencesRequest(bool DarkMode, string DefaultView, int InterviewRounds, bool MfaEnabled);
public sealed record PreferencesResponse(bool DarkMode, string DefaultView, int InterviewRounds, bool MfaEnabled);
