namespace JobTracker.Api.Contracts;

public sealed record RegisterRequest(string Email, string Password, string DisplayName);
public sealed record LoginRequest(string Email, string Password, string? Code = null);
public sealed record AuthResponse(string Token, Guid UserId, string Email, string DisplayName, bool IsAdmin);
public sealed record UpdateProfileRequest(string DisplayName, string Email, string? NewPassword);
public sealed record MfaSetupResponse(string Secret, string OtpauthUri);
public sealed record MfaStatusResponse(bool Enabled);
public sealed record MfaCodeRequest(string Code);
