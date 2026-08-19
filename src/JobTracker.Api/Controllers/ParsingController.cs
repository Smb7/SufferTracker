using JobTracker.Api.Contracts;
using JobTracker.Api.Models;
using JobTracker.Api.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace JobTracker.Api.Controllers;

[ApiController, Authorize, Route("api/jobs/parse")]
public sealed class ParsingController(IJobParser parser) : ControllerBase
{
    [HttpPost]
    public async Task<ActionResult<ParsedJobResponse>> Parse([FromForm] ParseJobRequest request, IFormFile? image, CancellationToken cancellationToken)
    {
        try
        {
            return request.InputType switch
            {
                InputType.Text => Ok(parser.ParseText(request.Text ?? string.Empty)),
                InputType.Link => Ok(await parser.ParseUrlAsync(request.Url ?? string.Empty, cancellationToken)),
                InputType.Screenshot when image is not null => Ok(parser.ParseScreenshot(image.FileName)),
                InputType.Screenshot => BadRequest(new { message = "An image is required for screenshot parsing." }),
                _ => BadRequest(new { message = "Unsupported input type." })
            };
        }
        catch (ArgumentException exception) { return BadRequest(new { message = exception.Message }); }
        catch (HttpRequestException exception) { return BadRequest(new { message = $"Could not fetch URL: {exception.Message}" }); }
    }
}
