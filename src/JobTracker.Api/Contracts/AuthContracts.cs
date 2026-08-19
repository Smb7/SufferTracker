namespace JobTracker.Api.Contracts;

public sealed record RegisterRequest(string Email, string Password, string DisplayName);
public sealed record LoginRequest(string Email, string Password);
public sealed record AuthResponse(string Token, Guid UserId, string Email, string DisplayName);
public sealed record UpdateProfileRequest(string DisplayName, string Email, string? NewPassword);
