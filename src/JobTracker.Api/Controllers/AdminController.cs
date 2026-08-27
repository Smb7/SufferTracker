using System.Security.Claims;
using JobTracker.Api.Contracts;
using JobTracker.Api.Data;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace JobTracker.Api.Controllers;

[Authorize(Roles = "Admin"), ApiController, Route("api/admin")]
public sealed class AdminController(AppDbContext db) : ControllerBase
{
    [HttpGet("users")]
    public async Task<ActionResult<IReadOnlyList<AdminUserResponse>>> Users(CancellationToken cancellationToken)
    {
        var users = await db.Users.AsNoTracking().OrderBy(user => user.Email)
            .Select(user => new AdminUserResponse(user.Id, user.Email, user.DisplayName, user.MfaEnabled, user.IsLocked, user.IsAdmin, user.CreatedAtUtc))
            .ToListAsync(cancellationToken);
        return Ok(users);
    }

    [HttpGet("logins")]
    public async Task<ActionResult<IReadOnlyList<LoginEventResponse>>> Logins(CancellationToken cancellationToken)
    {
        var events = await db.LoginEvents.AsNoTracking().OrderByDescending(item => item.OccurredAtUtc).Take(500)
            .Select(item => new LoginEventResponse(item.Id, item.Username, item.MfaEnabled, item.IpAddress, item.Succeeded, item.OccurredAtUtc, item.Latitude, item.Longitude, item.City, item.Country))
            .ToListAsync(cancellationToken);
        return Ok(events);
    }

    [HttpPost("users/{id:guid}/lock")]
    public async Task<IActionResult> Lock(Guid id, CancellationToken cancellationToken)
    {
        var user = await db.Users.FindAsync([id], cancellationToken);
        if (user is null) return NotFound();
        if (IsSelf(user.Id)) return BadRequest(new { message = "You cannot lock your own account." });
        user.IsLocked = true;
        await db.SaveChangesAsync(cancellationToken);
        return Ok(new AdminUserResponse(user.Id, user.Email, user.DisplayName, user.MfaEnabled, user.IsLocked, user.IsAdmin, user.CreatedAtUtc));
    }

    [HttpPost("users/{id:guid}/unlock")]
    public async Task<IActionResult> Unlock(Guid id, CancellationToken cancellationToken)
    {
        var user = await db.Users.FindAsync([id], cancellationToken);
        if (user is null) return NotFound();
        user.IsLocked = false;
        await db.SaveChangesAsync(cancellationToken);
        return Ok(new AdminUserResponse(user.Id, user.Email, user.DisplayName, user.MfaEnabled, user.IsLocked, user.IsAdmin, user.CreatedAtUtc));
    }

    [HttpPost("users/{id:guid}/reset-mfa")]
    public async Task<IActionResult> ResetMfa(Guid id, CancellationToken cancellationToken)
    {
        var user = await db.Users.FindAsync([id], cancellationToken);
        if (user is null) return NotFound();
        user.MfaEnabled = false;
        user.MfaSecret = null;
        await db.SaveChangesAsync(cancellationToken);
        return Ok(new AdminUserResponse(user.Id, user.Email, user.DisplayName, user.MfaEnabled, user.IsLocked, user.IsAdmin, user.CreatedAtUtc));
    }

    private bool IsSelf(Guid id)
    {
        var value = User.FindFirstValue(ClaimTypes.NameIdentifier);
        return Guid.TryParse(value, out var current) && current == id;
    }
}
