using System.Net;
using System.Net.Sockets;

namespace JobTracker.Api.Services;

public static class ClientIp
{
    public static string From(HttpContext http)
    {
        var forwarded = http.Request.Headers["X-Forwarded-For"].FirstOrDefault();
        if (!string.IsNullOrWhiteSpace(forwarded))
            return forwarded.Split(',', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries)[0];
        return http.Connection.RemoteIpAddress?.ToString() ?? "unknown";
    }

    public static bool IsPublic(string ip)
    {
        if (!IPAddress.TryParse(ip, out var address)) return false;
        if (address.IsIPv4MappedToIPv6) address = address.MapToIPv4();
        if (IPAddress.IsLoopback(address)) return false;
        if (address.AddressFamily == AddressFamily.InterNetwork)
        {
            var bytes = address.GetAddressBytes();
            return bytes[0] is not (0 or 10 or 127)
                && !(bytes[0] == 169 && bytes[1] == 254)
                && !(bytes[0] == 172 && bytes[1] is >= 16 and <= 31)
                && !(bytes[0] == 192 && bytes[1] == 168);
        }
        var first = address.GetAddressBytes()[0];
        return !address.IsIPv6LinkLocal && first is not (0x00 or 0xfc or 0xfd);
    }
}
