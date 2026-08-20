using System.Net;
using System.Text;
using JobTracker.Api.Services;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging.Abstractions;
using Xunit;

namespace JobTracker.Tests;

public sealed class ConfiguredOcrServiceTests
{
    [Fact]
    public async Task ExtractTextAsync_ReadsGenericProviderTextResponse()
    {
        using var httpClient = new HttpClient(new StubHandler(_ => new HttpResponseMessage(HttpStatusCode.OK)
        {
            Content = new StringContent("{\"text\":\"Senior Engineer\\nCompany: Acme\"}", Encoding.UTF8, "application/json")
        }));
        var configuration = new ConfigurationBuilder().AddInMemoryCollection(new Dictionary<string, string?>
        {
            ["Ocr:Endpoint"] = "https://ocr.example.test/read",
            ["Ocr:ApiKey"] = "test-key"
        }).Build();
        var service = new ConfiguredOcrService(httpClient, configuration, NullLogger<ConfiguredOcrService>.Instance);

        await using var image = new MemoryStream([0x01, 0x02]);
        var result = await service.ExtractTextAsync(image, "posting.png", "image/png", CancellationToken.None);

        Assert.True(result.ProviderUsed);
        Assert.Equal("Senior Engineer\nCompany: Acme", result.Text);
    }

    [Fact]
    public async Task ExtractTextAsync_ReturnsPendingResultWithoutEndpoint()
    {
        using var httpClient = new HttpClient(new StubHandler(_ => throw new InvalidOperationException("Provider should not be called.")));
        var service = new ConfiguredOcrService(httpClient, new ConfigurationBuilder().Build(), NullLogger<ConfiguredOcrService>.Instance);

        await using var image = new MemoryStream([0x01, 0x02]);
        var result = await service.ExtractTextAsync(image, "posting.png", "image/png", CancellationToken.None);

        Assert.False(result.ProviderUsed);
        Assert.Contains("not configured", result.Notice);
    }

    private sealed class StubHandler(Func<HttpRequestMessage, HttpResponseMessage> responseFactory) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken) => Task.FromResult(responseFactory(request));
    }
}
