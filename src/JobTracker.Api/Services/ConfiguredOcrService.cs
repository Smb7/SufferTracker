using System.Net.Http.Headers;
using System.Text.Json;

namespace JobTracker.Api.Services;

public sealed class ConfiguredOcrService(
    HttpClient httpClient,
    IConfiguration configuration,
    ILogger<ConfiguredOcrService> logger) : IOcrService
{
    public async Task<OcrResult> ExtractTextAsync(Stream image, string fileName, string contentType, CancellationToken cancellationToken)
    {
        var settings = configuration.GetSection("Ocr");
        var endpoint = settings["Endpoint"];
        if (string.IsNullOrWhiteSpace(endpoint))
        {
            logger.LogInformation("OCR requested for {FileName}; Ocr:Endpoint is not configured.", fileName);
            return new OcrResult(string.Empty, false, "OCR provider is not configured. Add Ocr:Endpoint to enable screenshot extraction.");
        }

        using var request = new HttpRequestMessage(HttpMethod.Post, endpoint);
        using var multipart = new MultipartFormDataContent();
        using var imageContent = new StreamContent(image);
        imageContent.Headers.ContentType = new MediaTypeHeaderValue(contentType);
        multipart.Add(imageContent, "image", Path.GetFileName(fileName));
        request.Content = multipart;

        var apiKey = settings["ApiKey"];
        if (!string.IsNullOrWhiteSpace(apiKey))
            request.Headers.TryAddWithoutValidation(settings["ApiKeyHeader"] ?? "Ocp-Apim-Subscription-Key", apiKey);

        using var response = await httpClient.SendAsync(request, cancellationToken);
        response.EnsureSuccessStatusCode();
        await using var responseStream = await response.Content.ReadAsStreamAsync(cancellationToken);
        using var document = await JsonDocument.ParseAsync(responseStream, cancellationToken: cancellationToken);
        var text = ReadText(document.RootElement);
        if (string.IsNullOrWhiteSpace(text))
            throw new InvalidDataException("The OCR provider returned no readable text.");

        return new OcrResult(text.Trim(), true, "OCR extracted these details. Review them before saving.");
    }

    private static string? ReadText(JsonElement root)
    {
        if (root.ValueKind == JsonValueKind.String) return root.GetString();
        if (root.ValueKind != JsonValueKind.Object) return null;

        foreach (var property in new[] { "text", "content", "fullText" })
            if (root.TryGetProperty(property, out var value) && value.ValueKind == JsonValueKind.String)
                return value.GetString();

        if (root.TryGetProperty("analyzeResult", out var analyzeResult)) return ReadAzureText(analyzeResult);
        if (root.TryGetProperty("readResult", out var readResult)) return ReadAzureText(readResult);
        return null;
    }

    private static string? ReadAzureText(JsonElement root)
    {
        if (!root.TryGetProperty("readResults", out var pages) || pages.ValueKind != JsonValueKind.Array) return null;
        var lines = pages.EnumerateArray()
            .SelectMany(page => page.TryGetProperty("lines", out var pageLines) && pageLines.ValueKind == JsonValueKind.Array
                ? pageLines.EnumerateArray()
                : Enumerable.Empty<JsonElement>())
            .Select(line => line.TryGetProperty("text", out var text) ? text.GetString() : null)
            .Where(text => !string.IsNullOrWhiteSpace(text));
        return string.Join(Environment.NewLine, lines);
    }
}
