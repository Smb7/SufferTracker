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

    [Fact]
    public void ParseText_ExtractsCompanyLocationAndPayFromUnlabeledPosting()
    {
        const string text = """
            Senior Backend Engineer
            Acme Robotics is hiring in Austin, TX (Hybrid).
            We are looking for a senior .NET developer to build APIs.
            $140,000 - $180,000 per year
            Requirements: C#, PostgreSQL, Docker, Azure
            """;

        var result = CreateParser().ParseText(text);

        Assert.Equal("Senior Backend Engineer", result.Title);
        Assert.Equal("Acme Robotics", result.Company);
        Assert.Equal("Austin, TX", result.Location);
        Assert.Equal("$140,000 - $180,000 per year", result.Pay);
        Assert.Contains("C#", result.Skills);
    }

    [Fact]
    public void ParseText_DetectsRemoteWhenNoCityPresent()
    {
        var result = CreateParser().ParseText("Platform Engineer\nFully remote, work from home anywhere.\n$120k - $150k");

        Assert.Equal("Remote", result.Location);
        Assert.Equal("$120,000 - $150,000 per year", result.Pay);
    }

    [Theory]
    [InlineData("$45 - $60 per hour", "$45 - $60/hour")]
    [InlineData("$95,000 a year", "$95,000 per year")]
    [InlineData("€55/hr", "€55/hour")]
    public void ParseText_NormalizesPayFormats(string input, string expected)
    {
        var result = CreateParser().ParseText($"QA Analyst\n{input}\nRequirements: attention to detail");

        Assert.Equal(expected, result.Pay);
    }

    [Fact]
    public void ParseText_TrimsPipeAndAtSuffixesFromTitle()
    {
        var piped = CreateParser().ParseText("Staff .NET Engineer | Nova Systems\nRemote\n");
        Assert.Equal("Staff .NET Engineer", piped.Title);

        var atStyle = CreateParser().ParseText("Principal Engineer at Orion Labs\nDenver, CO\n");
        Assert.Equal("Principal Engineer", atStyle.Title);
    }

    [Fact]
    public void ParseText_ExtractsCompanyFromJoinAndAboutLines()
    {
        var join = CreateParser().ParseText("Join Vertex Labs as a data analyst!\nRemote\n");
        Assert.Equal("Vertex Labs", join.Company);

        var about = CreateParser().ParseText("Data Analyst\nAbout Copperline: we build mapping software.\n");
        Assert.Equal("Copperline", about.Company);
    }

    [Fact]
    public void ParseText_KeepsSafeDefaultsWhenHeuristicsFindNothing()
    {
        var result = CreateParser().ParseText("We are looking for someone great.");

        Assert.Equal("We are looking for someone great.", result.Title);
        Assert.Equal("Unknown company", result.Company);
        Assert.Equal("Location not specified", result.Location);
        Assert.Equal("Pay not specified", result.Pay);
    }

    [Fact]
    public void BuildParsedFromHtml_StripsScriptsStylesAndComments()
    {
        const string html = """
            <html><head>
              <style>.job-card { color: red; } @media print { body {} }</style>
              <script src="https://cdn.example.com/polyfill.js"></script>
            </head><body>
              <!-- analytics bootstrap -->
              <script>var trackingId = "abc"; function boot() { return 1; }</script>
              <h1>Senior Backend Engineer</h1>
              <p>Acme Robotics is hiring in Austin, TX.</p>
              <p>$140,000 - $180,000 per year. Requirements: C#, PostgreSQL, Docker.</p>
              <noscript>Please enable JavaScript.</noscript>
            </body></html>
            """;

        var result = JobParserService.BuildParsedFromHtml(html);

        Assert.DoesNotContain("trackingId", result.Description);
        Assert.DoesNotContain("polyfill", result.Description);
        Assert.DoesNotContain(".job-card", result.Description);
        Assert.DoesNotContain("enable JavaScript", result.Description);
        Assert.Equal("Senior Backend Engineer", result.Title);
        Assert.Equal("Acme Robotics", result.Company);
        Assert.Equal("Austin, TX", result.Location);
        Assert.Equal("$140,000 - $180,000 per year", result.Pay);
    }

    [Fact]
    public void BuildParsedFromHtml_PrefersJsonLdJobPostingFields()
    {
        const string html = """
            <html><body>
              <script type="application/ld+json">
                {"@context":"http://schema.org/","@type":"JobPosting",
                 "title":"Staff Platform Engineer",
                 "hiringOrganization":{"@type":"Organization","name":"Northwind Data"},
                 "baseSalary":{"@type":"MonetaryAmount","currency":"USD",
                   "value":{"@type":"QuantitativeValue","minValue":180000,"maxValue":220000,"unitText":"YEAR"}},
                 "jobLocation":{"@type":"Place","address":{"@type":"PostalAddress","addressLocality":"Seattle","addressRegion":"WA"}},
                 "description":"<p>Build the platform. <b>Kubernetes required.</b></p>"}
              </script>
              <div class="serp">Indeed boilerplate noise</div>
            </body></html>
            """;

        var result = JobParserService.BuildParsedFromHtml(html);

        Assert.Equal("Staff Platform Engineer", result.Title);
        Assert.Equal("Northwind Data", result.Company);
        Assert.Equal("$180,000 - $220,000 per year", result.Pay);
        Assert.Equal("Seattle, WA", result.Location);
        Assert.Contains("Kubernetes", result.Skills);
    }

    [Fact]
    public void TryExtractJobPosting_IgnoresMalformedJsonLd()
    {
        const string html = """<script type="application/ld+json">{ not valid json !!! }</script><body>Fallback text only.</body>""";

        var structured = JobParserService.TryExtractJobPosting(html);

        Assert.Null(structured);
    }

    private sealed class StubOcrService(string text, string notice) : IOcrService
    {
        public Task<OcrResult> ExtractTextAsync(Stream image, string fileName, string contentType, CancellationToken cancellationToken) =>
            Task.FromResult(new OcrResult(text, !string.IsNullOrWhiteSpace(text), notice));
    }
}
