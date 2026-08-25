using JobTracker.Api.Services;
using Xunit;

namespace JobTracker.Tests;

public sealed class TotpServiceTests
{
    // RFC 6238 reference secret: ASCII "12345678901234567890" in base32.
    private const string RfcSecret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ";
    private static readonly DateTimeOffset T0 = new(1970, 1, 1, 0, 0, 0, TimeSpan.Zero);

    private readonly TotpService totp = new();

    [Theory]
    [InlineData(59, "287082")]
    [InlineData(1111111109, "081804")]
    [InlineData(1234567890, "005924")]
    public void Validate_AcceptsRfc6238Sha1Vectors(long unixSeconds, string expectedCode)
    {
        var time = T0.AddSeconds(unixSeconds);
        Assert.Equal(expectedCode, totp.GenerateCode(RfcSecret, time));
        Assert.True(totp.ValidateCode(RfcSecret, expectedCode, time));
    }

    [Fact]
    public void Validate_AcceptsAdjacentWindowForClockSkew()
    {
        Assert.True(totp.ValidateCode(RfcSecret, "287082", T0.AddSeconds(89)));
        Assert.True(totp.ValidateCode(RfcSecret, "287082", T0.AddSeconds(29)));
    }

    [Theory]
    [InlineData("287082", true)]
    [InlineData(" 287082 ", true)]
    [InlineData(" 287 082 ", true)]
    [InlineData("287083", false)]
    public void Validate_NormalizesWhitespaceAndRejectsWrongDigits(string code, bool expected)
    {
        Assert.Equal(expected, totp.ValidateCode(RfcSecret, code, T0.AddSeconds(59)));
    }

    [Fact]
    public void Validate_RejectsCodeFromDistantWindow()
    {
        Assert.False(totp.ValidateCode(RfcSecret, "287082", T0.AddSeconds(59 + 30 * 5)));
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("28708")]
    [InlineData("2870821")]
    [InlineData("28708a")]
    [InlineData("abcdef")]
    public void Validate_RejectsMalformedCodes(string? code)
    {
        Assert.False(totp.ValidateCode(RfcSecret, code, T0.AddSeconds(59)));
    }

    [Fact]
    public void Validate_ReturnsFalseForInvalidBase32Secret()
    {
        Assert.False(totp.ValidateCode("not!valid@base32", "287082", T0.AddSeconds(59)));
    }

    [Fact]
    public void GenerateSecret_ProducesDecodableUniqueSecrets()
    {
        var first = totp.GenerateSecret();
        var second = totp.GenerateSecret();

        Assert.NotEqual(first, second);
        Assert.Equal(32, first.Length);
        Assert.Matches("^[A-Z2-7]+$", first);
        Assert.Equal(20, TotpService.Base32Decode(first).Length);
    }

    [Theory]
    [InlineData("", new byte[0])]
    [InlineData("MY", new byte[] { 0x66 })]
    [InlineData("MZXQ", new byte[] { 0x66, 0x6F })]
    [InlineData("MZXW6", new byte[] { 0x66, 0x6F, 0x6F })]
    [InlineData("MZXW6YQ", new byte[] { 0x66, 0x6F, 0x6F, 0x62 })]
    [InlineData("MZXW6YTB", new byte[] { 0x66, 0x6F, 0x6F, 0x62, 0x61 })]
    public void Base32_RoundTripsRfc4648Vectors(string encoded, byte[] decoded)
    {
        Assert.Equal(encoded, TotpService.Base32Encode(decoded));
        Assert.Equal(decoded, TotpService.Base32Decode(encoded));
    }

    [Fact]
    public void BuildOtpAuthUri_EscapesAccountAndIssuer()
    {
        var uri = totp.BuildOtpAuthUri("user+tag@example.com", RfcSecret);

        Assert.StartsWith("otpauth://totp/", uri);
        Assert.Contains("SufferTracker%3Auser%2Btag%40example.com", uri);
        Assert.Contains($"secret={RfcSecret}", uri);
        Assert.Contains("digits=6", uri);
        Assert.Contains("period=30", uri);
    }
}
