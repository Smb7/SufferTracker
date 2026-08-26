using JobTracker.Api.Contracts;
using JobTracker.Api.Models;
using JobTracker.Api.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using System.Net.Http;

namespace JobTracker.Api.Controllers;

[ApiController, Authorize, Route("api/jobs/parse")]
public sealed class ParsingController(IJobParser parser, IHttpClientFactory httpClientFactory) : ControllerBase
{
    private const long MaxImageBytes = 10 * 1024 * 1024;
    private static readonly string[] SupportedImageTypes = ["image/jpeg", "image/png", "image/webp"];

    [HttpGet("fetch-page")]
    public async Task<IActionResult> FetchPage([FromQuery] string url, CancellationToken cancellationToken)
    {
        try
        {
            var uri = await UrlGuard.ValidatePublicHttpUrlAsync(url, cancellationToken);
            using var client = httpClientFactory.CreateClient("page-fetch");
            client.Timeout = TimeSpan.FromSeconds(20);
            using var response = await client.GetAsync(uri, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
            response.EnsureSuccessStatusCode();
            var mediaType = response.Content.Headers.ContentType?.MediaType;
            if (mediaType is not null && !mediaType.StartsWith("text/", StringComparison.OrdinalIgnoreCase) && mediaType != "application/xhtml+xml")
                return BadRequest(new { message = "That URL is not an HTML page." });
            var html = await response.Content.ReadAsStringAsync(cancellationToken);
            return Content(html, "text/html");
        }
        catch (ArgumentException exception) { return BadRequest(new { message = exception.Message }); }
        catch (HttpRequestException exception) { return BadRequest(new { message = $"Could not fetch URL: {exception.Message}" }); }
    }

    [HttpPost]
    [RequestSizeLimit(MaxImageBytes)]
    public async Task<ActionResult<ParsedJobResponse>> Parse([FromForm] ParseJobRequest request, IFormFile? image, CancellationToken cancellationToken)
    {
        try
        {
            if (request.InputType == InputType.Text) return Ok(parser.ParseText(request.Text ?? string.Empty));
            if (request.InputType == InputType.Link) return Ok(await parser.ParseUrlAsync(request.Url ?? string.Empty, cancellationToken));
            if (request.InputType != InputType.Screenshot) return BadRequest(new { message = "Unsupported input type." });
            if (image is null) return BadRequest(new { message = "An image is required for screenshot parsing." });
            if (image.Length is <= 0 or > MaxImageBytes) return BadRequest(new { message = "Screenshot must be between 1 byte and 10 MB." });
            if (!SupportedImageTypes.Contains(image.ContentType, StringComparer.OrdinalIgnoreCase))
                return BadRequest(new { message = "Only JPEG, PNG, and WebP screenshots are supported." });

            await using var imageStream = new MemoryStream();
            await image.CopyToAsync(imageStream, cancellationToken);
            if (!HasImageSignature(imageStream, image.ContentType))
                return BadRequest(new { message = "The uploaded file does not match its declared image type." });
            imageStream.Position = 0;
            return Ok(await parser.ParseScreenshotAsync(imageStream, Path.GetFileName(image.FileName), image.ContentType, cancellationToken));
        }
        catch (ArgumentException exception) { return BadRequest(new { message = exception.Message }); }
        catch (HttpRequestException exception) { return BadRequest(new { message = $"Could not fetch URL: {exception.Message}" }); }
        catch (InvalidDataException exception) { return BadRequest(new { message = exception.Message }); }
    }

    private static bool HasImageSignature(Stream image, string contentType)
    {
        Span<byte> header = stackalloc byte[12];
        image.Position = 0;
        var bytesRead = image.Read(header);
        image.Position = 0;
        return contentType.ToLowerInvariant() switch
        {
            "image/jpeg" => bytesRead >= 3 && header[0] == 0xFF && header[1] == 0xD8 && header[2] == 0xFF,
            "image/png" => bytesRead >= 8 && header[..8].SequenceEqual(new byte[] { 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A }),
            "image/webp" => bytesRead >= 12 && header[..4].SequenceEqual("RIFF"u8) && header[8..12].SequenceEqual("WEBP"u8),
            _ => false
        };
    }
}
