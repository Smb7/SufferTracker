using System.Text;
using JobTracker.Api.Services;
using Xunit;

namespace JobTracker.Tests;

public sealed class JobParserServiceTests
{
    private static JobParserService CreateParser(IOcrService? ocr = null) => new(new HttpClient(), ocr ?? new StubOcrService(string.Empty, "OCR provider is not configured."));

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
    public async Task ParseScreenshot_MapsOcrTextIntoStructuredFields()
    {
        var ocr = new StubOcrService("Backend Engineer\nCompany: Acme Labs\nLocation: Remote\nSalary: $140k\nSkills: C#, Docker", "OCR extracted details.");
        await using var image = new MemoryStream(Encoding.UTF8.GetBytes("fake image"));

        var result = await CreateParser(ocr).ParseScreenshotAsync(image, "posting.png", "image/png", CancellationToken.None);

        Assert.Equal("Acme Labs", result.Company);
        Assert.Equal("Backend Engineer", result.Title);
        Assert.Equal("Remote", result.Location);
        Assert.Contains("OCR", result.Notice);
    }

    [Fact]
    public async Task ParseScreenshot_ReturnsPendingStateWhenProviderIsNotConfigured()
    {
        await using var image = new MemoryStream(Encoding.UTF8.GetBytes("fake image"));

        var result = await CreateParser().ParseScreenshotAsync(image, "posting.png", "image/png", CancellationToken.None);

        Assert.Contains("OCR", result.Notice);
        Assert.Equal("OCR pending", result.Company);
    }

    private sealed class StubOcrService(string text, string notice) : IOcrService
    {
        public Task<OcrResult> ExtractTextAsync(Stream image, string fileName, string contentType, CancellationToken cancellationToken) =>
            Task.FromResult(new OcrResult(text, !string.IsNullOrWhiteSpace(text), notice));
    }
}
