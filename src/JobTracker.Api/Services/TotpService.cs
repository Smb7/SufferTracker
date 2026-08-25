using System.Security.Cryptography;

namespace JobTracker.Api.Services;

public interface ITotpService
{
    string GenerateSecret();
    string BuildOtpAuthUri(string email, string secret);
    bool ValidateCode(string secret, string? code, DateTimeOffset? now = null);
}

public sealed class TotpService : ITotpService
{
    private const string Base32Alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
    private const int SecretBytes = 20;
    private const int StepSeconds = 30;
    private const int Digits = 6;

    public string GenerateSecret() => Base32Encode(RandomNumberGenerator.GetBytes(SecretBytes));

    public string BuildOtpAuthUri(string email, string secret) =>
        $"otpauth://totp/{Uri.EscapeDataString($"SufferTracker:{email}")}?secret={secret}&issuer={Uri.EscapeDataString("SufferTracker")}&digits={Digits}&period={StepSeconds}&algorithm=SHA1";

    public bool ValidateCode(string secret, string? code, DateTimeOffset? now = null)
    {
        if (string.IsNullOrWhiteSpace(code)) return false;
        var cleaned = code.Trim().Replace(" ", string.Empty);
        if (cleaned.Length != Digits || !cleaned.All(char.IsDigit)) return false;
        byte[] key;
        try { key = Base32Decode(secret); }
        catch (FormatException) { return false; }
        if (key.Length == 0) return false;

        var step = (now ?? DateTimeOffset.UtcNow).ToUnixTimeSeconds() / StepSeconds;
        return new[] { 0L, -1L, 1L }.Any(offset => ComputeHotp(key, step + offset) == cleaned);
    }

    internal string GenerateCode(string secret, DateTimeOffset now) => ComputeHotp(Base32Decode(secret), now.ToUnixTimeSeconds() / StepSeconds);

    private static string ComputeHotp(byte[] key, long counter)
    {
        var counterBytes = new byte[8];
        for (var index = 7; index >= 0; index--)
        {
            counterBytes[index] = (byte)(counter & 0xFF);
            counter >>= 8;
        }
        using var hmac = new HMACSHA1(key);
        var hash = hmac.ComputeHash(counterBytes);
        var offset = hash[^1] & 0x0F;
        var binary = ((hash[offset] & 0x7F) << 24) | (hash[offset + 1] << 16) | (hash[offset + 2] << 8) | hash[offset + 3];
        return (binary % 1_000_000).ToString($"D{Digits}");
    }

    internal static string Base32Encode(ReadOnlySpan<byte> data)
    {
        if (data.Length == 0) return string.Empty;
        var chars = new char[(data.Length * 8 + 4) / 5];
        var bits = 0; var buffer = 0; var position = 0;
        foreach (var value in data)
        {
            buffer = (buffer << 8) | value; bits += 8;
            while (bits >= 5)
            {
                chars[position++] = Base32Alphabet[(buffer >> (bits - 5)) & 0x1F];
                bits -= 5;
            }
        }
        if (bits > 0) chars[position++] = Base32Alphabet[(buffer << (5 - bits)) & 0x1F];
        return new string(chars, 0, position);
    }

    internal static byte[] Base32Decode(string value)
    {
        var trimmed = new string([.. value.Where(char.IsAsciiLetterOrDigit)]).ToUpperInvariant();
        if (trimmed.Length == 0) return [];
        var bytes = new byte[trimmed.Length * 5 / 8];
        var bits = 0; var buffer = 0; var position = 0;
        foreach (var character in trimmed)
        {
            var index = Base32Alphabet.IndexOf(character);
            if (index < 0) throw new FormatException($"Invalid base32 character '{character}'.");
            buffer = (buffer << 5) | index; bits += 5;
            if (bits >= 8)
            {
                bytes[position++] = (byte)(buffer >> (bits - 8));
                bits -= 8;
            }
        }
        return bytes;
    }
}
