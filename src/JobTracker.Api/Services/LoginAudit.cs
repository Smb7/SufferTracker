using JobTracker.Api.Data;
using JobTracker.Api.Models;

namespace JobTracker.Api.Services;

public sealed class LoginAudit(AppDbContext db, IGeoIpLookup geo) : ILoginAudit
{
    public async Task RecordAsync(string username, Guid? userId, bool mfaEnabled, bool succeeded, string ip, CancellationToken cancellationToken)
    {
        try
        {
            var place = await geo.LookupAsync(ip, cancellationToken);
            db.LoginEvents.Add(new LoginEvent
            {
                UserId = userId,
                Username = username.Trim().ToLowerInvariant(),
                MfaEnabled = mfaEnabled,
                IpAddress = ip,
                Succeeded = succeeded,
                Latitude = place?.Latitude,
                Longitude = place?.Longitude,
                City = place?.City,
                Country = place?.Country
            });
            await db.SaveChangesAsync(cancellationToken);
        }
        catch
        {
        }
    }
}
