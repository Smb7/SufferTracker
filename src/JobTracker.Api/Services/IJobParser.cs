using JobTracker.Api.Contracts;

namespace JobTracker.Api.Services;

public interface IJobParser
{
    ParsedJobResponse ParseText(string text);
    Task<ParsedJobResponse> ParseUrlAsync(string url, CancellationToken cancellationToken);
    ParsedJobResponse ParseScreenshot(string fileName);
}
