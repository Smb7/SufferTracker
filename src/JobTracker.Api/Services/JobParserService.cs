using System.Net;
using System.Text.RegularExpressions;
using JobTracker.Api.Contracts;

namespace JobTracker.Api.Services;

public sealed partial class JobParserService(HttpClient httpClient, IOcrService ocrService) : IJobParser
{
    public ParsedJobResponse ParseText(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
            throw new ArgumentException("Job text is required.", nameof(text));

        var lines = text.Split(['\r', '\n'], StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
        var title = FindValue(lines, "title", "role", "position") ?? lines.FirstOrDefault() ?? "Untitled role";
        var company = FindValue(lines, "company", "employer") ?? "Unknown company";
        var location = FindValue(lines, "location") ?? "Location not specified";
        var pay = FindValue(lines, "salary", "pay", "compensation") ?? "Pay not specified";
        var skills = FindValue(lines, "skills", "requirements", "technologies") ?? ExtractSkills(text);
        return new ParsedJobResponse(company, title, text.Trim(), skills, pay, location, null, null);
    }

    public async Task<ParsedJobResponse> ParseUrlAsync(string url, CancellationToken cancellationToken)
    {
        var uri = await UrlGuard.ValidatePublicHttpUrlAsync(url, cancellationToken);

        using var response = await httpClient.GetAsync(uri, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        response.EnsureSuccessStatusCode();
        var html = await response.Content.ReadAsStringAsync(cancellationToken);
        var text = HtmlTagRegex().Replace(WebUtility.HtmlDecode(html), " ");
        text = WhitespaceRegex().Replace(text, " ").Trim();
        var parsed = ParseText(text);
        return parsed with { SourceUrl = uri.ToString(), Notice = "Review scraped details before saving." };
    }

    public async Task<ParsedJobResponse> ParseScreenshotAsync(Stream image, string fileName, string contentType, CancellationToken cancellationToken)
    {
        var ocr = await ocrService.ExtractTextAsync(image, fileName, contentType, cancellationToken);
        if (string.IsNullOrWhiteSpace(ocr.Text))
            return new ParsedJobResponse("OCR pending", "Review uploaded screenshot", string.Empty, string.Empty, "Pay not specified", "Location not specified", null, ocr.Notice);

        var parsed = ParseText(ocr.Text);
        return parsed with { Notice = ocr.Notice };
    }

    private static string? FindValue(IEnumerable<string> lines, params string[] labels)
    {
        foreach (var line in lines)
        {
            var separator = line.IndexOf(':');
            if (separator < 0) continue;
            var label = line[..separator].Trim().ToLowerInvariant();
            if (labels.Contains(label)) return line[(separator + 1)..].Trim();
        }
        return null;
    }

    private static string ExtractSkills(string text)
    {
        var known = new[] { "C#", ".NET", "Angular", "TypeScript", "PostgreSQL", "Docker", "AWS", "Azure", "React", "SQL" };
        return string.Join(", ", known.Where(skill => text.Contains(skill, StringComparison.OrdinalIgnoreCase)));
    }

    [GeneratedRegex("<[^>]+>", RegexOptions.Compiled)]
    private static partial Regex HtmlTagRegex();

    [GeneratedRegex("\\s+", RegexOptions.Compiled)]
    private static partial Regex WhitespaceRegex();
}
