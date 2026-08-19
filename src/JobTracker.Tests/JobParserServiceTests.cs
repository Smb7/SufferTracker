using JobTracker.Api.Services;
using Microsoft.Extensions.Logging.Abstractions;
using Xunit;

namespace JobTracker.Tests;

public sealed class JobParserServiceTests
{
    private static JobParserService CreateParser() => new(new HttpClient(), NullLogger<JobParserService>.Instance);

    [Fact]
    public void ParseText_ReadsLabeledFieldsAndKnownSkills()
    {
        var result = CreateParser().ParseText("Senior API Engineer\nCompany: Acme Labs\nLocation: Remote\nSalary: $130k\nSkills: C#, PostgreSQL\nBuild APIs with .NET and Docker.");

        Assert.Equal("Acme Labs", result.Company);
        Assert.Equal("Senior API Engineer", result.Title);
        Assert.Equal("Remote", result.Location);
        Assert.Equal("$130k", result.Pay);
        Assert.Equal("C#, PostgreSQL", result.Skills);
    }

    [Fact]
    public void ParseText_UsesSafeDefaultsForMissingFields()
    {
        var result = CreateParser().ParseText("A thoughtful description for a new role.");

        Assert.Equal("A thoughtful description for a new role.", result.Title);
        Assert.Equal("Unknown company", result.Company);
        Assert.Equal("Pay not specified", result.Pay);
    }

    [Fact]
    public void ParseText_RejectsEmptyInput()
    {
        Assert.Throws<ArgumentException>(() => CreateParser().ParseText("  "));
    }

    [Fact]
    public void ParseScreenshot_ReturnsExplicitOcrNotice()
    {
        var result = CreateParser().ParseScreenshot("posting.png");

        Assert.Contains("OCR", result.Notice);
        Assert.Equal("OCR pending", result.Company);
    }
}
