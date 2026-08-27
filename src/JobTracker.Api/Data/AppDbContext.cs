using System.Text.Json;
using System.Text.Json.Serialization;
using JobTracker.Api.Models;
using Microsoft.EntityFrameworkCore;

namespace JobTracker.Api.Data;

public sealed class AppDbContext(DbContextOptions<AppDbContext> options) : DbContext(options)
{
    public static readonly JsonSerializerOptions StatusEventSerializerOptions = new()
    {
        Converters = { new JsonStringEnumConverter() },
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase
    };

    public DbSet<User> Users => Set<User>();
    public DbSet<JobApplication> JobApplications => Set<JobApplication>();
    public DbSet<UserPreference> UserPreferences => Set<UserPreference>();
    public DbSet<LoginEvent> LoginEvents => Set<LoginEvent>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<User>(entity =>
        {
            entity.HasKey(user => user.Id);
            entity.HasIndex(user => user.Email).IsUnique();
            entity.Property(user => user.Email).HasMaxLength(320).IsRequired();
            entity.Property(user => user.PasswordHash).IsRequired();
            entity.HasOne(user => user.Preferences).WithOne(preferences => preferences.User)
                .HasForeignKey<UserPreference>(preferences => preferences.UserId)
                .OnDelete(DeleteBehavior.Cascade);
        });

        modelBuilder.Entity<JobApplication>(entity =>
        {
            entity.HasKey(job => job.Id);
            entity.HasIndex(job => new { job.UserId, job.Status });
            entity.Property(job => job.Company).HasMaxLength(200).IsRequired();
            entity.Property(job => job.Title).HasMaxLength(300).IsRequired();
            entity.Property(job => job.Status).HasConversion<string>().HasMaxLength(30);
            entity.Property(job => job.StatusEvents).HasColumnType("jsonb").HasConversion(
                events => JsonSerializer.Serialize(events, StatusEventSerializerOptions),
                json => JsonSerializer.Deserialize<List<StatusEvent>>(json, StatusEventSerializerOptions) ?? new List<StatusEvent>(),
                new Microsoft.EntityFrameworkCore.ChangeTracking.ValueComparer<List<StatusEvent>>(
                    (left, right) => JsonSerializer.Serialize(left, StatusEventSerializerOptions) == JsonSerializer.Serialize(right, StatusEventSerializerOptions),
                    events => events.Aggregate(17, (hash, item) => hash * 31 + item.Status.GetHashCode()),
                    events => events.ToList()));
            entity.HasOne(job => job.User).WithMany(user => user.Jobs)
                .HasForeignKey(job => job.UserId).OnDelete(DeleteBehavior.Cascade);
        });

        modelBuilder.Entity<UserPreference>(entity => entity.HasKey(preferences => preferences.UserId));

        modelBuilder.Entity<LoginEvent>(entity =>
        {
            entity.HasKey(item => item.Id);
            entity.Property(item => item.Username).HasMaxLength(320).IsRequired();
            entity.Property(item => item.IpAddress).HasMaxLength(64).IsRequired();
            entity.HasIndex(item => item.OccurredAtUtc);
            entity.HasOne<User>().WithMany().HasForeignKey(item => item.UserId).OnDelete(DeleteBehavior.SetNull);
        });
    }
}
