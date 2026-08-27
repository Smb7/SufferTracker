using System.Net.Http.Json;
using System.Text.Json.Serialization;

namespace JobTracker.Api.Services;

public sealed class GeoIpLookup(IHttpClientFactory httpFactory) : IGeoIpLookup
{
    public async Task<GeoIpResult?> LookupAsync(string ip, CancellationToken cancellationToken)
    {
        if (!ClientIp.IsPublic(ip)) return null;
        try
        {
            var client = httpFactory.CreateClient("geoip");
            var payload = await client.GetFromJsonAsync<IpApiResponse>($"/json/{ip}?fields=status,lat,lon,city,country", cancellationToken);
            if (payload is null || !string.Equals(payload.Status, "success", StringComparison.OrdinalIgnoreCase)) return null;
            return new GeoIpResult(payload.Lat, payload.Lon, payload.City, payload.Country);
        }
        catch
        {
            return null;
        }
    }

    private sealed class IpApiResponse
    {
        [JsonPropertyName("status")] public string Status { get; set; } = "";
        [JsonPropertyName("lat")] public double Lat { get; set; }
        [JsonPropertyName("lon")] public double Lon { get; set; }
        [JsonPropertyName("city")] public string? City { get; set; }
        [JsonPropertyName("country")] public string? Country { get; set; }
    }
}
