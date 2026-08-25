using System.Net;
using System.Net.Sockets;

namespace JobTracker.Api.Services;

public static class UrlGuard
{
    public static async Task<Uri> ValidatePublicHttpUrlAsync(string? url, CancellationToken cancellationToken)
    {
        if (!Uri.TryCreate(url?.Trim(), UriKind.Absolute, out var uri) || uri.Scheme is not ("http" or "https"))
            throw new ArgumentException("A valid HTTP or HTTPS URL is required.", nameof(url));
        if (!string.IsNullOrEmpty(uri.UserInfo))
            throw new ArgumentException("URLs containing embedded credentials are not allowed.", nameof(url));

        var host = uri.HostNameType == UriHostNameType.IPv6 ? uri.Host.Trim('[', ']') : uri.Host;
        if (string.IsNullOrWhiteSpace(host)) throw InvalidHostName();

        if (IPAddress.TryParse(host, out var literal))
        {
            EnsurePublic(literal);
            return uri;
        }

        try
        {
            var addresses = await Dns.GetHostAddressesAsync(host, cancellationToken);
            if (addresses.Length == 0) throw InvalidHostName();
            foreach (var address in addresses) EnsurePublic(address);
        }
        catch (SocketException exception)
        {
            throw InvalidHostName(exception);
        }
        return uri;
    }

    private static void EnsurePublic(IPAddress address)
    {
        var candidate = address.IsIPv4MappedToIPv6 ? address.MapToIPv4() : address;
        var blocked = IPAddress.IsLoopback(candidate)
            || candidate.Equals(IPAddress.None) || candidate.Equals(IPAddress.IPv6None) || candidate.Equals(IPAddress.IPv6Loopback)
            || candidate.IsIPv6LinkLocal || candidate.IsIPv6SiteLocal
            || (candidate.AddressFamily == AddressFamily.InterNetwork && IsNonPublicV4(candidate));
        if (blocked)
            throw new ArgumentException("Requests to private or internal network addresses are not allowed.");
    }

    private static bool IsNonPublicV4(IPAddress address)
    {
        var octets = address.GetAddressBytes();
        return octets[0] is 0 or 10 or 127
            || (octets[0] == 100 && octets[1] >= 64 && octets[1] <= 127)
            || (octets[0] == 169 && octets[1] == 254)
            || (octets[0] == 172 && octets[1] >= 16 && octets[1] <= 31)
            || (octets[0] == 192 && octets[1] == 168);
    }

    private static ArgumentException InvalidHostName(Exception? inner = null) =>
        new("The URL host could not be resolved to a public address.", "url", inner);
}
