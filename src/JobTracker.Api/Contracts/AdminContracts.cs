namespace JobTracker.Api.Contracts;

public sealed record AdminUserResponse(Guid Id, string Email, string DisplayName, bool MfaEnabled, bool IsLocked, bool IsAdmin, DateTime CreatedAtUtc);
public sealed record LoginEventResponse(Guid Id, string Username, bool MfaEnabled, string IpAddress, bool Succeeded, DateTime OccurredAtUtc, double? Latitude, double? Longitude, string? City, string? Country);
