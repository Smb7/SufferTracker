using JobTracker.Api.Services;
using Xunit;

namespace JobTracker.Tests;

public sealed class UrlGuardTests
{
    [Theory]
    [InlineData("not a url")]
    [InlineData("ftp://example.com/job")]
    [InlineData("/relative/path")]
    [InlineData("http://user:pass@example.com/job")]
    [InlineData("https://example@host/job")]
    [InlineData("http://127.0.0.1/jobs")]
    [InlineData("http://localhost/jobs")]
    [InlineData("https://[::1]/jobs")]
    [InlineData("http://[::ffff:10.0.0.5]/jobs")]
    [InlineData("http://169.254.169.254/latest/meta-data/")]
    [InlineData("http://10.1.2.3/jobs")]
    [InlineData("http://192.168.1.10/jobs")]
    [InlineData("http://172.16.0.9/jobs")]
    [InlineData("http://172.31.255.255/jobs")]
    [InlineData("http://100.100.1.1/jobs")]
    [InlineData("http://0.0.0.0/jobs")]
    public void Validate_RejectsNonPublicOrInvalidUrls(string url)
    {
        Assert.ThrowsAny<ArgumentException>(() => Validate(url));
    }

    [Fact]
    public void Validate_AcceptsPublicIpLiteralAndReturnsAbsoluteUri()
    {
        var uri = Validate("https://8.8.8.8/jobs/123");

        Assert.Equal(new Uri("https://8.8.8.8/jobs/123"), uri);
    }

    [Fact]
    public void Validate_AllowsPublicAddressesOutsidePrivateRanges()
    {
        Assert.Equal(new Uri("http://172.32.0.9/jobs"), Validate("http://172.32.0.9/jobs"));
        Assert.Equal(new Uri("http://1.1.1.1/jobs"), Validate("http://1.1.1.1/jobs"));
        Assert.Equal(new Uri("http://8.7.6.5/jobs"), Validate("http://8.7.6.5/jobs"));
    }

    private static Uri Validate(string url) =>
        UrlGuard.ValidatePublicHttpUrlAsync(url, CancellationToken.None).GetAwaiter().GetResult();
}
