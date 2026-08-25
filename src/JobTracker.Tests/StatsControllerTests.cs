using System.Globalization;
using JobTracker.Api.Controllers;
using Xunit;

namespace JobTracker.Tests;

public sealed class StatsControllerTests
{
    [Theory]
    [InlineData("2026-08-25T15:30:00Z", "2026-08-24T00:00:00Z")] // Tuesday -> Monday 00:00
    [InlineData("2026-08-24T00:00:01Z", "2026-08-24T00:00:00Z")] // Monday early morning
    [InlineData("2026-08-30T23:59:59Z", "2026-08-24T00:00:00Z")] // Sunday still belongs to the same week
    public void WeekStart_ReturnsMondayOfCurrentUtcWeek(string now, string expected)
    {
        var start = StatsController.WeekStart(DateTimeOffset.Parse(now, CultureInfo.InvariantCulture));

        Assert.Equal(DateTimeOffset.Parse(expected, CultureInfo.InvariantCulture), start);
    }
}
