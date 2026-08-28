using JobTracker.Api.Data;
using JobTracker.Api.Models;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;

namespace JobTracker.Api.Services;

public static class AdminBootstrap
{
    public static async Task EnsureAsync(AppDbContext db, IPasswordHasher<User> hasher, IConfiguration config, CancellationToken cancellationToken = default)
    {
        var emails = config.GetSection("Admin:Emails").Get<string[]>() ?? [];
        var password = config["Admin:Password"];
        var canSetPassword = !string.IsNullOrWhiteSpace(password) && password.Length >= 8;
        foreach (var email in emails.Select(item => item.Trim().ToLowerInvariant()).Where(item => item.Length > 0))
        {
            var user = await db.Users.SingleOrDefaultAsync(item => item.Email == email, cancellationToken);
            if (user is null)
            {
                if (!canSetPassword) continue;
                user = new User { Email = email, PasswordHash = string.Empty, DisplayName = "Admin", IsAdmin = true };
                user.PasswordHash = hasher.HashPassword(user, password!);
                user.Preferences = new UserPreference { UserId = user.Id };
                db.Users.Add(user);
                continue;
            }
            user.IsAdmin = true;
            user.IsLocked = false;
            if (canSetPassword) user.PasswordHash = hasher.HashPassword(user, password!);
        }
        await db.SaveChangesAsync(cancellationToken);
    }
}
