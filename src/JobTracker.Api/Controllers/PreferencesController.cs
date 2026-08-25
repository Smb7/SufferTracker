using System.Security.Claims;
using JobTracker.Api.Contracts;
using JobTracker.Api.Data;
using JobTracker.Api.Models;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace JobTracker.Api.Controllers;

[ApiController, Authorize, Route("api/preferences")]
public sealed class PreferencesController(AppDbContext db) : ControllerBase
{
    [HttpGet]
    public async Task<ActionResult<PreferencesResponse>> Get(CancellationToken cancellationToken)
    {
        var preferences = await GetEntity(cancellationToken);
        return Ok(ToResponse(preferences));
    }

    [HttpPut]
    public async Task<ActionResult<PreferencesResponse>> Update(UpdatePreferencesRequest request, CancellationToken cancellationToken)
    {
        if (request.InterviewRounds is < 1 or > 10) return BadRequest(new { message = "Interview rounds must be between 1 and 10." });
        var preferences = await GetEntity(cancellationToken);
        preferences.DarkMode = request.DarkMode; preferences.DefaultView = request.DefaultView; preferences.InterviewRounds = request.InterviewRounds;
        await db.SaveChangesAsync(cancellationToken);
        return Ok(ToResponse(preferences));
    }

    private async Task<UserPreference> GetEntity(CancellationToken cancellationToken)
    {
        var userId = Guid.Parse(User.FindFirstValue(ClaimTypes.NameIdentifier) ?? throw new InvalidOperationException("Missing user claim."));
        var preferences = await db.UserPreferences.FindAsync([userId], cancellationToken);
        if (preferences is not null) return preferences;
        preferences = new UserPreference { UserId = userId }; db.UserPreferences.Add(preferences); await db.SaveChangesAsync(cancellationToken); return preferences;
    }

    private static PreferencesResponse ToResponse(UserPreference item) => new(item.DarkMode, item.DefaultView, item.InterviewRounds);
}
