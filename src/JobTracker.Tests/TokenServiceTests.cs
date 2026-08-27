using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using JobTracker.Api.Models;
using JobTracker.Api.Services;
using Microsoft.Extensions.Configuration;
using Microsoft.IdentityModel.Tokens;
using Xunit;

namespace JobTracker.Tests;

public sealed class TokenServiceTests
{
    private static TokenService CreateService() => new(new ConfigurationBuilder()
        .AddInMemoryCollection(new Dictionary<string, string?>
        {
            ["Jwt:Key"] = "unit-test-signing-key-0123456789abcdef",
            ["Jwt:Issuer"] = "SufferTracker.Tests",
            ["Jwt:Audience"] = "SufferTracker.Tests.Clients"
        })
        .Build());

    [Fact]
    public void CreateToken_ProducesVerifiableTokenWithUserClaims()
    {
        var user = new User { Id = Guid.Parse("2c1f7a52-1b3e-4d5f-9a01-77aa88bb99cc"), Email = "shane@example.com", PasswordHash = "x", DisplayName = "Shane B" };
        var token = new JwtSecurityTokenHandler();
        var jwt = token.ReadJwtToken(CreateService().CreateToken(user));

        Assert.Equal(user.Id.ToString(), jwt.Subject);
        Assert.Equal("shane@example.com", jwt.Claims.Single(claim => claim.Type == JwtRegisteredClaimNames.Email).Value);
        Assert.Equal("Shane B", jwt.Claims.Single(claim => claim.Type == "display_name").Value);
        Assert.DoesNotContain(jwt.Claims, claim => claim.Type == ClaimTypes.Role || claim.Value == "Admin");
        Assert.Equal("SufferTracker.Tests", jwt.Issuer);
        Assert.Contains("SufferTracker.Tests.Clients", jwt.Audiences);
    }

    [Fact]
    public void CreateToken_TokenValidatesAgainstSigningKeyAndExpiresWithin12Hours()
    {
        var user = new User { Email = "shane@example.com", PasswordHash = "x", DisplayName = "Shane B" };
        var signed = CreateService().CreateToken(user);
        var handler = new JwtSecurityTokenHandler();

        var principal = handler.ValidateToken(signed, new TokenValidationParameters
        {
            ValidateIssuerSigningKey = true,
            IssuerSigningKey = new SymmetricSecurityKey(System.Text.Encoding.UTF8.GetBytes("unit-test-signing-key-0123456789abcdef")),
            ValidateIssuer = true, ValidIssuer = "SufferTracker.Tests",
            ValidateAudience = true, ValidAudience = "SufferTracker.Tests.Clients",
            ValidateLifetime = true
        }, out _);

        Assert.NotNull(principal.FindFirst(ClaimTypes.NameIdentifier));
        var expiry = handler.ReadJwtToken(signed).ValidTo;
        Assert.InRange(expiry - DateTime.UtcNow, TimeSpan.FromHours(11.5), TimeSpan.FromHours(12));
    }

    [Fact]
    public void CreateToken_AdminUserIncludesRoleClaim()
    {
        var user = new User { Email = "admin@example.com", PasswordHash = "x", DisplayName = "Admin", IsAdmin = true };
        var jwt = new JwtSecurityTokenHandler().ReadJwtToken(CreateService().CreateToken(user));
        Assert.Contains(jwt.Claims, claim => claim.Type is ClaimTypes.Role or "role" && claim.Value == "Admin");
    }

    [Fact]
    public void CreateToken_MissingKeyThrows()
    {
        var service = new TokenService(new ConfigurationBuilder().AddInMemoryCollection(new Dictionary<string, string?> { ["Jwt:Issuer"] = "i" }).Build());
        Assert.Throws<InvalidOperationException>(() => service.CreateToken(new User { Email = "x@y.z", PasswordHash = "x", DisplayName = "X" }));
    }
}
