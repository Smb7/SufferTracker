using JobTracker.Api.Data;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace JobTracker.Api.Controllers;

public sealed record PublicStatsResponse(int ApplicationsThisWeek);

[ApiController, Route("api/stats")]
public sealed class StatsController(AppDbContext db) : ControllerBase
{
    [HttpGet("public")]
    public async Task<IActionResult> GetPublicStats(CancellationToken cancellationToken)
    {
        var weekStart = WeekStart(DateTimeOffset.UtcNow);
        var applicationsThisWeek = await db.JobApplications.CountAsync(job => job.AppliedAtUtc >= weekStart, cancellationToken);
        return Ok(new PublicStatsResponse(applicationsThisWeek));
    }

    internal static DateTimeOffset WeekStart(DateTimeOffset now)
    {
        var daysSinceMonday = ((int)now.DayOfWeek + 6) % 7;
        return new DateTimeOffset(now.Year, now.Month, now.Day, 0, 0, 0, now.Offset).AddDays(-daysSinceMonday);
    }
}
