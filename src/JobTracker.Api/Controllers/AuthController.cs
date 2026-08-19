using System.Security.Claims;
using JobTracker.Api.Contracts;
using JobTracker.Api.Data;
using JobTracker.Api.Models;
using JobTracker.Api.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace JobTracker.Api.Controllers;

[ApiController, Route("api/auth")]
public sealed class AuthController(AppDbContext db, ITokenService tokens, IPasswordHasher<User> hasher) : ControllerBase
{
    [HttpPost("register")]
    public async Task<ActionResult<AuthResponse>> Register(RegisterRequest request, CancellationToken cancellationToken)
    {
        var email = request.Email.Trim().ToLowerInvariant();
        if (string.IsNullOrWhiteSpace(email) || request.Password.Length < 8)
            return BadRequest(new { message = "Email is required and password must be at least 8 characters." });
        if (await db.Users.AnyAsync(user => user.Email == email, cancellationToken))
            return Conflict(new { message = "An account with that email already exists." });

        var user = new User { Email = email, PasswordHash = string.Empty, DisplayName = request.DisplayName.Trim() };
        user.PasswordHash = hasher.HashPassword(user, request.Password);
        user.Preferences = new UserPreference { UserId = user.Id };
        db.Users.Add(user);
        await db.SaveChangesAsync(cancellationToken);
        return Ok(ToResponse(user));
    }

    [HttpPost("login")]
    public async Task<ActionResult<AuthResponse>> Login(LoginRequest request, CancellationToken cancellationToken)
    {
        var user = await db.Users.SingleOrDefaultAsync(item => item.Email == request.Email.Trim().ToLowerInvariant(), cancellationToken);
        if (user is null || hasher.VerifyHashedPassword(user, user.PasswordHash, request.Password) == PasswordVerificationResult.Failed)
            return Unauthorized(new { message = "Invalid email or password." });
        return Ok(ToResponse(user));
    }

    [Authorize, HttpPut("profile")]
    public async Task<IActionResult> UpdateProfile(UpdateProfileRequest request, CancellationToken cancellationToken)
    {
        var user = await CurrentUser(cancellationToken);
        if (user is null) return Unauthorized();
        var email = request.Email.Trim().ToLowerInvariant();
        if (await db.Users.AnyAsync(item => item.Email == email && item.Id != user.Id, cancellationToken))
            return Conflict(new { message = "That email is already in use." });
        user.Email = email;
        user.DisplayName = request.DisplayName.Trim();
        if (!string.IsNullOrWhiteSpace(request.NewPassword)) user.PasswordHash = hasher.HashPassword(user, request.NewPassword);
        await db.SaveChangesAsync(cancellationToken);
        return Ok(ToResponse(user));
    }

    [Authorize, HttpDelete("account")]
    public async Task<IActionResult> DeleteAccount(CancellationToken cancellationToken)
    {
        var user = await CurrentUser(cancellationToken);
        if (user is null) return Unauthorized();
        db.Users.Remove(user);
        await db.SaveChangesAsync(cancellationToken);
        return NoContent();
    }

    private async Task<User?> CurrentUser(CancellationToken cancellationToken)
    {
        var value = User.FindFirstValue(ClaimTypes.NameIdentifier) ?? User.FindFirstValue(ClaimTypes.NameIdentifier);
        return Guid.TryParse(value, out var id) ? await db.Users.FindAsync([id], cancellationToken) : null;
    }

    private AuthResponse ToResponse(User user) => new(tokens.CreateToken(user), user.Id, user.Email, user.DisplayName);
}
