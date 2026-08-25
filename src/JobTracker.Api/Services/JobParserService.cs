using System.Net;
using System.Text.Json;
using System.Text.RegularExpressions;
using JobTracker.Api.Contracts;

namespace JobTracker.Api.Services;

public sealed partial class JobParserService(HttpClient httpClient, IOcrService ocrService) : IJobParser
{
    public ParsedJobResponse ParseText(string text) => ParseStatic(text);

    public async Task<ParsedJobResponse> ParseUrlAsync(string url, CancellationToken cancellationToken)
    {
        var uri = await UrlGuard.ValidatePublicHttpUrlAsync(url, cancellationToken);

        using var response = await httpClient.GetAsync(uri, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        response.EnsureSuccessStatusCode();
        var html = await response.Content.ReadAsStringAsync(cancellationToken);
        return BuildParsedFromHtml(html) with { SourceUrl = uri.ToString(), Notice = "Review scraped details before saving." };
    }

    internal static ParsedJobResponse BuildParsedFromHtml(string html)
    {
        var readable = ExtractReadableText(html);
        var parsed = string.IsNullOrWhiteSpace(readable)
            ? new ParsedJobResponse("Unknown company", "Untitled role", string.Empty, string.Empty, "Pay not specified", "Location not specified", null, null)
            : ParseStatic(readable);

        var structured = TryExtractJobPosting(html);
        var skills = FirstNonEmpty(parsed.Skills, string.IsNullOrWhiteSpace(parsed.Skills) ? ExtractSkills(FirstNonEmpty(structured?.Description, parsed.Description)) : null);
        return parsed with
        {
            Title = structured?.Title ?? parsed.Title,
            Company = structured?.Company ?? parsed.Company,
            Pay = structured?.Pay ?? parsed.Pay,
            Location = structured?.Location ?? parsed.Location,
            Description = FirstNonEmpty(parsed.Description, structured?.Description),
            Skills = skills
        };
    }

    private static string FirstNonEmpty(params string?[] values) => values.FirstOrDefault(value => !string.IsNullOrWhiteSpace(value)) ?? string.Empty;

    internal static ParsedJobResponse ParseStatic(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
            throw new ArgumentException("Job text is required.", nameof(text));

        var lines = text.Split(['\r', '\n'], StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
        var title = FindValue(lines, "title", "role", "position") ?? ExtractTitle(lines);
        var company = FindValue(lines, "company", "employer") ?? ExtractCompany(lines) ?? "Unknown company";
        var location = FindValue(lines, "location", "based in", "office") ?? ExtractLocation(text) ?? "Location not specified";
        var pay = FindValue(lines, "salary", "pay", "compensation") ?? ExtractPay(text) ?? "Pay not specified";
        var skills = FindValue(lines, "skills", "requirements", "technologies") ?? ExtractSkills(text);
        return new ParsedJobResponse(company, title, text.Trim(), skills, pay, location, null, null);
    }

    public async Task<ParsedJobResponse> ParseScreenshotAsync(Stream image, string fileName, string contentType, CancellationToken cancellationToken)
    {
        var ocr = await ocrService.ExtractTextAsync(image, fileName, contentType, cancellationToken);
        if (string.IsNullOrWhiteSpace(ocr.Text))
            return new ParsedJobResponse("OCR pending", "Review uploaded screenshot", string.Empty, string.Empty, "Pay not specified", "Location not specified", null, ocr.Notice);

        var parsed = ParseText(ocr.Text);
        return parsed with { Notice = ocr.Notice };
    }

    internal static string ExtractReadableText(string html)
    {
        if (string.IsNullOrWhiteSpace(html)) return string.Empty;
        var bodyMatch = BodyRegex().Match(html);
        var content = bodyMatch.Success ? bodyMatch.Groups[1].Value : html;
        content = NoisyBlockRegex().Replace(content, " ");
        content = CommentRegex().Replace(content, " ");
        content = BlockBoundaryRegex().Replace(content, "\n");
        content = HtmlTagRegex().Replace(content, " ");
        var decoded = WebUtility.HtmlDecode(content).Replace("\r", "\n");
        var lines = decoded.Split('\n')
            .Select(line => WhitespaceRegex().Replace(line, " ").Trim())
            .Where(line => line.Length > 0);
        return string.Join('\n', lines);
    }

    internal sealed record StructuredJob(string? Title, string? Company, string? Pay, string? Location, string? Description);

    internal static StructuredJob? TryExtractJobPosting(string html)
    {
        foreach (Match block in JsonLdRegex().Matches(html))
        {
            try
            {
                using var document = JsonDocument.Parse(block.Groups[1].Value, new JsonDocumentOptions { AllowTrailingCommas = true });
                var posting = FindJobPosting(document.RootElement);
                if (posting is not { } jobPosting) continue;

                var title = jobPosting.TryGetProperty("title", out var titleElement) && titleElement.ValueKind == JsonValueKind.String ? titleElement.GetString() : null;
                var company = ReadOrganization(jobPosting);
                var pay = ReadSalary(jobPosting);
                var location = ReadLocation(jobPosting);
                var description = jobPosting.TryGetProperty("description", out var descriptionElement) && descriptionElement.ValueKind == JsonValueKind.String
                    ? StripHtml(descriptionElement.GetString() ?? string.Empty)
                    : null;
                if (title is not null || company is not null || pay is not null || location is not null)
                    return new StructuredJob(title, company, pay, location, description);
            }
            catch (JsonException)
            {
                // Malformed JSON-LD blocks are skipped; heuristic parsing still applies.
            }
        }
        return null;
    }

    private static JsonElement? FindJobPosting(JsonElement element)
    {
        if (element.ValueKind == JsonValueKind.Object)
        {
            if (element.TryGetProperty("@type", out var type) &&
                (type.ValueKind == JsonValueKind.String && type.GetString()?.Equals("JobPosting", StringComparison.OrdinalIgnoreCase) == true))
                return element;
            if (element.TryGetProperty("@graph", out var graph) && graph.ValueKind == JsonValueKind.Array)
                foreach (var item in graph.EnumerateArray())
                    if (FindJobPosting(item) is { } found) return found;
            return null;
        }
        if (element.ValueKind == JsonValueKind.Array)
            foreach (var item in element.EnumerateArray())
                if (FindJobPosting(item) is { } found) return found;
        return null;
    }

    private static string? ReadOrganization(JsonElement posting)
    {
        if (!posting.TryGetProperty("hiringOrganization", out var organization)) return null;
        if (organization.ValueKind == JsonValueKind.String) return organization.GetString();
        if (organization.ValueKind == JsonValueKind.Object && organization.TryGetProperty("name", out var name) && name.ValueKind == JsonValueKind.String)
            return name.GetString();
        return null;
    }

    private static string? ReadSalary(JsonElement posting)
    {
        if (!posting.TryGetProperty("baseSalary", out var baseSalary)) return null;
        var value = baseSalary.ValueKind == JsonValueKind.Object && baseSalary.TryGetProperty("value", out var nested) ? nested : baseSalary;
        decimal? min = ReadNumber(value, "minValue") ?? ReadNumber(value, "value");
        decimal? max = ReadNumber(value, "maxValue") ?? min;
        if (min is not { } minValue) return null;
        var currency = value.TryGetProperty("currency", out var currencyElement) && currencyElement.ValueKind == JsonValueKind.String ? CurrencySymbol(currencyElement.GetString()) : "$";
        var unit = value.TryGetProperty("unitText", out var unitElement) && unitElement.ValueKind == JsonValueKind.String ? unitElement.GetString() : "YEAR";
        var suffix = string.Equals(unit, "HOUR", StringComparison.OrdinalIgnoreCase) ? "/hour" : " per year";
        return max is { } high && high != minValue
            ? $"{currency}{minValue:N0} - {currency}{high:N0}{suffix}"
            : $"{currency}{minValue:N0}{suffix}";
    }

    private static decimal? ReadNumber(JsonElement value, string property) =>
        value.TryGetProperty(property, out var number) && number.ValueKind == JsonValueKind.Number && number.TryGetDecimal(out var parsed) ? parsed : null;

    private static string CurrencySymbol(string? code) => code?.ToUpperInvariant() switch
    {
        "USD" => "$", "EUR" => "€", "GBP" => "£",
        null or "" => "$",
        _ => code + " "
    };

    private static string? ReadLocation(JsonElement posting)
    {
        if (!posting.TryGetProperty("jobLocation", out var jobLocation)) return null;
        JsonElement? address = null;
        if (jobLocation.ValueKind == JsonValueKind.Array && jobLocation.GetArrayLength() > 0)
        {
            var first = jobLocation.EnumerateArray().First();
            if (first.ValueKind == JsonValueKind.Object && first.TryGetProperty("address", out var nested)) address = nested;
        }
        else if (jobLocation.ValueKind == JsonValueKind.Object && jobLocation.TryGetProperty("address", out var single)) address = single;

        if (address is not JsonElement addressElement || addressElement.ValueKind != JsonValueKind.Object) return null;
        var locality = addressElement.TryGetProperty("addressLocality", out var localityElement) && localityElement.ValueKind == JsonValueKind.String ? localityElement.GetString() : null;
        var region = addressElement.TryGetProperty("addressRegion", out var regionElement) && regionElement.ValueKind == JsonValueKind.String ? regionElement.GetString() : null;
        var joined = string.Join(", ", new[] { locality, region }.Where(part => !string.IsNullOrWhiteSpace(part)));
        return joined.Length > 0 ? joined : null;
    }

    private static string StripHtml(string value)
    {
        var decoded = WebUtility.HtmlDecode(NoisyBlockRegex().Replace(HtmlTagRegex().Replace(value, " "), " "));
        return WhitespaceRegex().Replace(decoded, " ").Trim();
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

    private static string ExtractTitle(string[] lines)
    {
        var first = lines.FirstOrDefault() ?? "Untitled role";
        var pipeIndex = first.IndexOf('|');
        if (pipeIndex > 0) first = first[..pipeIndex];
        var atIndex = first.LastIndexOf(" at ", StringComparison.OrdinalIgnoreCase);
        if (atIndex > 0) first = first[..atIndex];
        return first.Length > 80 ? first[..80].Trim() : first.Trim();
    }

    private static string? ExtractCompany(string[] lines)
    {
        foreach (var line in lines.Take(8))
        {
            var hiring = HiringLineRegex().Match(line);
            if (hiring.Success) return System.Net.WebUtility.HtmlDecode(hiring.Groups[1].Value).Trim(" .-–—|".ToCharArray());
            var join = JoinLineRegex().Match(line);
            if (join.Success)
            {
                var candidate = LeadingProperNouns(join.Groups[1].Value);
                if (!string.IsNullOrWhiteSpace(candidate)) return candidate;
            }
            var about = AboutLineRegex().Match(line);
            if (about.Success) return about.Groups[1].Value.Trim();
        }
        return null;
    }

    private static string? ExtractLocation(string text)
    {
        var place = PlaceRegex().Match(text);
        if (place.Success)
            return $"{place.Groups[1].Value.Trim()}, {place.Groups[2].Value.ToUpperInvariant()}";
        return RemoteRegex().IsMatch(text) ? "Remote" : null;
    }

    private static string? ExtractPay(string text)
    {
        var range = SalaryRangeRegex().Match(text);
        if (range.Success)
        {
            var low = FormatAmount(range.Groups[2].Value, range.Groups[3].Value);
            var highCurrency = string.IsNullOrEmpty(range.Groups[4].Value) ? range.Groups[1].Value : range.Groups[4].Value;
            var high = FormatAmount(range.Groups[5].Value, range.Groups[6].Value);
            var currency = string.IsNullOrEmpty(range.Groups[1].Value) ? range.Groups[4].Value : range.Groups[1].Value;
            return $"{currency}{low} - {highCurrency}{high}{Suffix(range.Value)}";
        }
        var single = SalarySingleRegex().Match(text);
        if (single.Success)
            return $"{single.Groups[1].Value}{FormatAmount(single.Groups[2].Value, single.Groups[3].Value)}{Suffix(single.Value)}";
        return null;
    }

    private static string FormatAmount(string amount, string kiloSuffix) =>
        !string.IsNullOrEmpty(kiloSuffix) && decimal.TryParse(amount.Replace(",", ""), out var value)
            ? (value * 1000).ToString("N0")
            : amount.Replace(" ", "");

    private static string Suffix(string matchedText) =>
        HourlyUnitRegex().IsMatch(matchedText) ? "/hour"
        : SalaryPeriodRegex().IsMatch(matchedText) || char.ToLowerInvariant(matchedText[^1]) == 'k' || matchedText.Contains('k') || matchedText.Contains('K')
            ? " per year"
            : string.Empty;

    private static string ExtractSkills(string text)
    {
        var known = new[]
        {
            "C#", ".NET", "Angular", "TypeScript", "JavaScript", "PostgreSQL", "SQL Server", "Docker", "Kubernetes",
            "AWS", "Azure", "GCP", "React", "Vue", "Python", "Java", "Go", "Rust", "Terraform", "CI/CD", "REST", "GraphQL"
        };
        return string.Join(", ", known.Where(skill => text.Contains(skill, StringComparison.OrdinalIgnoreCase)));
    }

    [GeneratedRegex(@"^([A-Z][\w&.,'\- ]{1,48}?)\s+(?:is|are)\s+hiring\b", RegexOptions.IgnoreCase)]
    private static partial Regex HiringLineRegex();

    [GeneratedRegex(@"^(?:join|at)\s+([A-Za-z][\w&.,'\- ]{1,60})", RegexOptions.IgnoreCase)]
    private static partial Regex JoinLineRegex();

    private static readonly HashSet<string> ConnectorWords = new(StringComparer.OrdinalIgnoreCase)
        { "as", "to", "for", "a", "an", "the", "and", "our", "with" };

    private static string LeadingProperNouns(string phrase)
    {
        var words = phrase.Split(' ', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        var kept = new List<string>();
        foreach (var word in words)
        {
            if (ConnectorWords.Contains(word.TrimEnd('.', '!', ',', ':'))) break;
            if (!char.IsUpper(word[0]) && kept.Count > 0) break;
            if (!char.IsUpper(word[0])) break;
            kept.Add(word);
        }
        var joined = string.Join(' ', kept).Trim(" .,!-–—|".ToCharArray());
        return joined.Length is < 2 or > 48 ? string.Empty : joined;
    }

    [GeneratedRegex(@"^about\s+(?:the\s+)?([A-Z][\w&.,'\- ]{1,48})", RegexOptions.IgnoreCase)]
    private static partial Regex AboutLineRegex();

    [GeneratedRegex(@"\bremote\b|\bwork from home\b|\bhybrid\b", RegexOptions.IgnoreCase)]
    private static partial Regex RemoteRegex();

    [GeneratedRegex(@"\b([A-Z][a-zA-Z.'-]*(?: [A-Z][a-zA-Z.'-]*){0,3}),\s?(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b")]
    private static partial Regex PlaceRegex();

    [GeneratedRegex(@"([$€£])\s?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s?([kK])?\s?[-–—to]{1,4}\s?([$€£])?\s?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s?([kK])?\s?(?:/hr|per hour|hourly|/yr|per year|annually|a year)?")]
    private static partial Regex SalaryRangeRegex();

    [GeneratedRegex(@"([$€£])\s?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s?([kK])?\s?(?:/hr|per hour|hourly|/yr|per year|annually|a year)")]
    private static partial Regex SalarySingleRegex();

    [GeneratedRegex(@"(/hr|per hour|hourly)", RegexOptions.IgnoreCase)]
    private static partial Regex HourlyUnitRegex();

    [GeneratedRegex(@"(per year|annually|a year|/yr)", RegexOptions.IgnoreCase)]
    private static partial Regex SalaryPeriodRegex();

    [GeneratedRegex("<[^>]+>", RegexOptions.Compiled)]
    private static partial Regex HtmlTagRegex();

    [GeneratedRegex("\\s+", RegexOptions.Compiled)]
    private static partial Regex WhitespaceRegex();

    [GeneratedRegex(@"<body\b[^>]*>([\s\S]*?)</body>", RegexOptions.Compiled | RegexOptions.IgnoreCase)]
    private static partial Regex BodyRegex();

    [GeneratedRegex(@"<\b(script|style|noscript|svg|iframe|template)\b[^>]*>[\s\S]*?</\1\s*>", RegexOptions.Compiled | RegexOptions.IgnoreCase)]
    private static partial Regex NoisyBlockRegex();

    [GeneratedRegex(@"<!--[\s\S]*?-->", RegexOptions.Compiled)]
    private static partial Regex CommentRegex();

    [GeneratedRegex(@"</?(?:p|div|h[1-6]|li|tr|section|article|header|footer|ul|ol|table)\b[^>]*>|<br\s*/?>", RegexOptions.Compiled | RegexOptions.IgnoreCase)]
    private static partial Regex BlockBoundaryRegex();

    [GeneratedRegex("""<script[^>]+type=["']application/ld\+json["'][^>]*>([\s\S]*?)</script>""", RegexOptions.Compiled | RegexOptions.IgnoreCase)]
    private static partial Regex JsonLdRegex();
}
