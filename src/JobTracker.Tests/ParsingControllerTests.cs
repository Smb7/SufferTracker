using JobTracker.Api.Contracts;
using JobTracker.Api.Controllers;
using JobTracker.Api.Models;
using JobTracker.Api.Services;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Xunit;

namespace JobTracker.Tests;

public sealed class ParsingControllerTests
{
    [Fact]
    public async Task Parse_RejectsPngWithInvalidFileSignature()
    {
        var parser = new RecordingParser();
        var controller = new ParsingController(parser, new StubHttpClientFactory());
        var image = CreateFile([0x01, 0x02, 0x03], "image/png", "posting.png");

        var result = await controller.Parse(new ParseJobRequest(InputType.Screenshot, null, null), image, CancellationToken.None);

        Assert.IsType<BadRequestObjectResult>(result.Result);
        Assert.False(parser.ScreenshotCalled);
    }

    [Fact]
    public async Task Parse_ForwardsValidPngToParser()
    {
        var parser = new RecordingParser();
        var controller = new ParsingController(parser, new StubHttpClientFactory());
        var pngHeader = new byte[] { 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A };
        var image = CreateFile(pngHeader, "image/png", "posting.png");

        var result = await controller.Parse(new ParseJobRequest(InputType.Screenshot, null, null), image, CancellationToken.None);

        Assert.IsType<OkObjectResult>(result.Result);
        Assert.True(parser.ScreenshotCalled);
    }

    private static FormFile CreateFile(byte[] bytes, string contentType, string fileName)
    {
        var formFile = new FormFile(new MemoryStream(bytes), 0, bytes.Length, "image", fileName)
        {
            Headers = new HeaderDictionary { ["Content-Type"] = contentType }
        };
        return formFile;
    }

    private sealed class StubHttpClientFactory : System.Net.Http.IHttpClientFactory
    {
        public System.Net.Http.HttpClient CreateClient(string name) => new();
    }

    private sealed class RecordingParser : IJobParser
    {
        public bool ScreenshotCalled { get; private set; }
        public ParsedJobResponse ParseText(string text) => throw new NotSupportedException();
        public Task<ParsedJobResponse> ParseUrlAsync(string url, CancellationToken cancellationToken) => throw new NotSupportedException();
        public Task<ParsedJobResponse> ParseScreenshotAsync(Stream image, string fileName, string contentType, CancellationToken cancellationToken)
        {
            ScreenshotCalled = true;
            return Task.FromResult(new ParsedJobResponse("Acme", "Engineer", "", "", "", "", null, null));
        }
    }
}
