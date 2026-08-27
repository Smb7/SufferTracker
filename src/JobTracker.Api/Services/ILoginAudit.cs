namespace JobTracker.Api.Services;

public interface ILoginAudit
{
    Task RecordAsync(string username, Guid? userId, bool mfaEnabled, bool succeeded, string ip, CancellationToken cancellationToken);
}
