namespace JobTracker.Api.Services;

public sealed record GeoIpResult(double Latitude, double Longitude, string? City, string? Country);

public interface IGeoIpLookup
{
    Task<GeoIpResult?> LookupAsync(string ip, CancellationToken cancellationToken);
}
