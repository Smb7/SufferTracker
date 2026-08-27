using JobTracker.Api.Services;
using Microsoft.AspNetCore.Http;
using Xunit;

namespace JobTracker.Tests;

public sealed class ClientIpTests
{
    [Theory]
    [InlineData("8.8.8.8", true)]
    [InlineData("1.1.1.1", true)]
    [InlineData("127.0.0.1", false)]
    [InlineData("::1", false)]
    [InlineData("10.0.0.4", false)]
    [InlineData("192.168.1.20", false)]
    [InlineData("172.16.0.2", false)]
    [InlineData("172.31.255.1", false)]
    [InlineData("169.254.1.1", false)]
    [InlineData("not-an-ip", false)]
    public void IsPublic_ClassifiesAddresses(string ip, bool expected) => Assert.Equal(expected, ClientIp.IsPublic(ip));

    [Fact]
    public void From_PrefersForwardedFor()
    {
        var http = new DefaultHttpContext();
        http.Request.Headers["X-Forwarded-For"] = "203.0.113.10, 10.0.0.1";
        http.Connection.RemoteIpAddress = System.Net.IPAddress.Parse("127.0.0.1");
        Assert.Equal("203.0.113.10", ClientIp.From(http));
    }
}
