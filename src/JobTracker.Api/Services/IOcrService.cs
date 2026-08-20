namespace JobTracker.Api.Services;

public sealed record OcrResult(string Text, bool ProviderUsed, string? Notice);

public interface IOcrService
{
    Task<OcrResult> ExtractTextAsync(Stream image, string fileName, string contentType, CancellationToken cancellationToken);
}
