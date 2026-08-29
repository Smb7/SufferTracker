using System.Security.Claims;
using JobTracker.Api.Contracts;
using JobTracker.Api.Controllers;
using JobTracker.Api.Data;
using JobTracker.Api.Models;
using JobTracker.Api.Services;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Xunit;

namespace JobTracker.Tests;

public sealed class AuthAdminTests
{
    [Fact]
    public async Task Login_RejectsLockedAccountAndRecordsFailure()
    {
        await using var db = CreateDb();
        var user = SeedUser(db, locked: true);
        var audit = new RecordingAudit();
        var controller = CreateAuth(db, audit);
        var result = await controller.Login(new LoginRequest(user.Email, "password123"), CancellationToken.None);
        Assert.Equal(StatusCodes.Status403Forbidden, (result.Result as ObjectResult)?.StatusCode);
        Assert.False(audit.Last!.Value.Succeeded);
        Assert.Equal(user.Email, audit.Last.Value.Username);
    }

    [Fact]
    public async Task Login_RecordsSuccessfulAttempt()
    {
        await using var db = CreateDb();
        var user = SeedUser(db);
        var audit = new RecordingAudit();
        var controller = CreateAuth(db, audit);
        var result = await controller.Login(new LoginRequest(user.Email, "password123"), CancellationToken.None);
        Assert.IsType<OkObjectResult>(result.Result);
        Assert.True(audit.Last!.Value.Succeeded);
        Assert.False(audit.Last.Value.MfaEnabled);
    }

    [Fact]
    public async Task Login_UnknownUserIsFailureWithoutUserId()
    {
        await using var db = CreateDb();
        var audit = new RecordingAudit();
        var controller = CreateAuth(db, audit);
        var result = await controller.Login(new LoginRequest("missing@test.com", "password123"), CancellationToken.None);
        Assert.IsType<UnauthorizedObjectResult>(result.Result);
        Assert.False(audit.Last!.Value.Succeeded);
        Assert.Null(audit.Last.Value.UserId);
    }

    [Fact]
    public async Task Admin_LockUnlockAndResetMfa()
    {
        await using var db = CreateDb();
        var target = SeedUser(db, email: "member@test.com");
        target.MfaEnabled = true;
        target.MfaSecret = "secret";
        await db.SaveChangesAsync();
        var admin = new AdminController(db) { ControllerContext = AdminContext(Guid.NewGuid()) };

        var locked = await admin.Lock(target.Id, CancellationToken.None);
        Assert.True(((locked as OkObjectResult)!.Value as AdminUserResponse)!.IsLocked);

        var reset = await admin.ResetMfa(target.Id, CancellationToken.None);
        var afterReset = (reset as OkObjectResult)!.Value as AdminUserResponse;
        Assert.False(afterReset!.MfaEnabled);
        Assert.Null((await db.Users.FindAsync(target.Id))!.MfaSecret);

        var unlocked = await admin.Unlock(target.Id, CancellationToken.None);
        Assert.False(((unlocked as OkObjectResult)!.Value as AdminUserResponse)!.IsLocked);
    }

    [Fact]
    public async Task Admin_CannotLockSelf()
    {
        await using var db = CreateDb();
        var adminUser = SeedUser(db, email: "admin@test.com", admin: true);
        var admin = new AdminController(db) { ControllerContext = AdminContext(adminUser.Id) };
        var result = await admin.Lock(adminUser.Id, CancellationToken.None);
        Assert.IsType<BadRequestObjectResult>(result);
        Assert.False((await db.Users.FindAsync(adminUser.Id))!.IsLocked);
    }

    [Fact]
    public async Task EnsureAsync_CreatesAdminWhenMissing()
    {
        await using var db = CreateDb();
        var created = new string('a', 12);
        var hasher = new PasswordHasher<User>();
        var config = new ConfigurationBuilder().AddInMemoryCollection(new Dictionary<string, string?>
        {
            ["Admin:Emails:0"] = "ops@test.com",
            ["Admin:Password"] = created
        }).Build();

        await AdminBootstrap.EnsureAsync(db, hasher, config);

        var user = await db.Users.SingleAsync(item => item.Email == "ops@test.com");
        Assert.True(user.IsAdmin);
        Assert.Equal(PasswordVerificationResult.Success, hasher.VerifyHashedPassword(user, user.PasswordHash, created));
    }

    [Fact]
    public async Task EnsureAsync_ResetsPasswordAndUnlocksExistingAdmin()
    {
        await using var db = CreateDb();
        var rotated = new string('b', 12);
        SeedUser(db, email: "ops@test.com", locked: true);
        var hasher = new PasswordHasher<User>();
        var config = new ConfigurationBuilder().AddInMemoryCollection(new Dictionary<string, string?>
        {
            ["Admin:Emails:0"] = "ops@test.com",
            ["Admin:Password"] = rotated
        }).Build();

        await AdminBootstrap.EnsureAsync(db, hasher, config);

        var user = await db.Users.SingleAsync(item => item.Email == "ops@test.com");
        Assert.True(user.IsAdmin);
        Assert.False(user.IsLocked);
        Assert.Equal(PasswordVerificationResult.Success, hasher.VerifyHashedPassword(user, user.PasswordHash, rotated));
    }

    private static AuthController CreateAuth(AppDbContext db, ILoginAudit audit)
    {
        var tokens = new TokenService(new ConfigurationBuilder().AddInMemoryCollection(new Dictionary<string, string?>
        {
            ["Jwt:Key"] = "unit-test-signing-key-0123456789abcdef",
            ["Jwt:Issuer"] = "SufferTracker.Tests",
            ["Jwt:Audience"] = "SufferTracker.Tests.Clients"
        }).Build());
        var config = new ConfigurationBuilder().AddInMemoryCollection(new Dictionary<string, string?> { ["Admin:Emails:0"] = "smoke@test.com" }).Build();
        return new AuthController(db, tokens, new PasswordHasher<User>(), new TotpService(), audit, config)
        {
            ControllerContext = new ControllerContext { HttpContext = new DefaultHttpContext() }
        };
    }

    private static AppDbContext CreateDb()
    {
        var options = new DbContextOptionsBuilder<AppDbContext>().UseInMemoryDatabase(Guid.NewGuid().ToString()).Options;
        return new AppDbContext(options);
    }

    private static User SeedUser(AppDbContext db, string email = "smoke@test.com", bool locked = false, bool admin = false)
    {
        var user = new User { Email = email, PasswordHash = string.Empty, DisplayName = "Smoke", IsLocked = locked, IsAdmin = admin };
        user.PasswordHash = new PasswordHasher<User>().HashPassword(user, "password123");
        db.Users.Add(user);
        db.SaveChanges();
        return user;
    }

    private static ControllerContext AdminContext(Guid id)
    {
        return new ControllerContext
        {
            HttpContext = new DefaultHttpContext
            {
                User = new ClaimsPrincipal(new ClaimsIdentity([new Claim(ClaimTypes.NameIdentifier, id.ToString()), new Claim(ClaimTypes.Role, "Admin")], "test"))
            }
        };
    }

    private sealed class RecordingAudit : ILoginAudit
    {
        public (string Username, Guid? UserId, bool MfaEnabled, bool Succeeded)? Last { get; private set; }
        public Task RecordAsync(string username, Guid? userId, bool mfaEnabled, bool succeeded, string ip, CancellationToken cancellationToken)
        {
            Last = (username, userId, mfaEnabled, succeeded);
            return Task.CompletedTask;
        }
    }
}
