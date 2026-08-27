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
public sealed class AuthController(AppDbContext db, ITokenService tokens, IPasswordHasher<User> hasher, ITotpService totp, ILoginAudit audit, IConfiguration config) : ControllerBase
{
    [HttpPost("register")]
    public async Task<ActionResult<AuthResponse>> Register(RegisterRequest request, CancellationToken cancellationToken)
    {
        var email = request.Email.Trim().ToLowerInvariant();
        if (string.IsNullOrWhiteSpace(email) || request.Password.Length < 8)
            return BadRequest(new { message = "Email is required and password must be at least 8 characters." });
        if (await db.Users.AnyAsync(user => user.Email == email, cancellationToken))
            return Conflict(new { message = "An account with that email already exists." });

        var user = new User { Email = email, PasswordHash = string.Empty, DisplayName = request.DisplayName.Trim(), IsAdmin = IsConfiguredAdmin(email) };
        user.PasswordHash = hasher.HashPassword(user, request.Password);
        user.Preferences = new UserPreference { UserId = user.Id };
        db.Users.Add(user);
        await db.SaveChangesAsync(cancellationToken);
        return Ok(ToResponse(user));
    }

    [HttpPost("login")]
    public async Task<ActionResult<AuthResponse>> Login(LoginRequest request, CancellationToken cancellationToken)
    {
        var username = request.Email.Trim().ToLowerInvariant();
        var ip = ClientIp.From(HttpContext);
        var user = await db.Users.SingleOrDefaultAsync(item => item.Email == username, cancellationToken);
        if (user is null || hasher.VerifyHashedPassword(user, user.PasswordHash, request.Password) == PasswordVerificationResult.Failed)
        {
            await audit.RecordAsync(username, user?.Id, user?.MfaEnabled ?? false, false, ip, cancellationToken);
            return Unauthorized(new { message = "Invalid email or password." });
        }
        if (user.IsLocked)
        {
            await audit.RecordAsync(username, user.Id, user.MfaEnabled, false, ip, cancellationToken);
            return StatusCode(StatusCodes.Status403Forbidden, new { message = "This account is locked." });
        }
        if (user.MfaEnabled && !totp.ValidateCode(user.MfaSecret ?? string.Empty, request.Code))
        {
            await audit.RecordAsync(username, user.Id, true, false, ip, cancellationToken);
            return Unauthorized(new { mfaRequired = true, message = "Enter the 6-digit code from your authenticator app." });
        }
        await audit.RecordAsync(username, user.Id, user.MfaEnabled, true, ip, cancellationToken);
        return Ok(ToResponse(user));
    }

    [Authorize, HttpGet("mfa/status")]
    public async Task<IActionResult> MfaStatus(CancellationToken cancellationToken)
    {
        var user = await CurrentUser(cancellationToken);
        if (user is null) return Unauthorized();
        return Ok(new MfaStatusResponse(user.MfaEnabled));
    }

    [Authorize, HttpPost("mfa/setup")]
    public async Task<ActionResult<MfaSetupResponse>> StartMfaSetup(CancellationToken cancellationToken)
    {
        var user = await CurrentUser(cancellationToken);
        if (user is null) return Unauthorized();
        user.MfaSecret = totp.GenerateSecret();
        user.MfaEnabled = false;
        await db.SaveChangesAsync(cancellationToken);
        return Ok(new MfaSetupResponse(user.MfaSecret, totp.BuildOtpAuthUri(user.Email, user.MfaSecret)));
    }

    [Authorize, HttpPost("mfa/enable")]
    public async Task<IActionResult> EnableMfa(MfaCodeRequest request, CancellationToken cancellationToken)
    {
        var user = await CurrentUser(cancellationToken);
        if (user is null) return Unauthorized();
        if (string.IsNullOrEmpty(user.MfaSecret)) return BadRequest(new { message = "Start MFA setup before enabling it." });
        if (!totp.ValidateCode(user.MfaSecret, request.Code)) return BadRequest(new { message = "That code is not valid. Try the next one." });
        user.MfaEnabled = true;
        await db.SaveChangesAsync(cancellationToken);
        return Ok(new MfaStatusResponse(true));
    }

    [Authorize, HttpPost("mfa/disable")]
    public async Task<IActionResult> DisableMfa(MfaCodeRequest request, CancellationToken cancellationToken)
    {
        var user = await CurrentUser(cancellationToken);
        if (user is null) return Unauthorized();
        if (user.MfaEnabled && !totp.ValidateCode(user.MfaSecret ?? string.Empty, request.Code))
            return BadRequest(new { message = "That code is not valid. MFA is still enabled." });
        user.MfaEnabled = false;
        user.MfaSecret = null;
        await db.SaveChangesAsync(cancellationToken);
        return Ok(new MfaStatusResponse(false));
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

    private AuthResponse ToResponse(User user) => new(tokens.CreateToken(user), user.Id, user.Email, user.DisplayName, user.IsAdmin);

    private bool IsConfiguredAdmin(string email)
    {
        var emails = config.GetSection("Admin:Emails").Get<string[]>() ?? [];
        return emails.Any(item => string.Equals(item.Trim(), email, StringComparison.OrdinalIgnoreCase));
    }
}
