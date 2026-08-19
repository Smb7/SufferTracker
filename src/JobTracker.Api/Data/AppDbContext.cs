using JobTracker.Api.Models;
using Microsoft.EntityFrameworkCore;

namespace JobTracker.Api.Data;

public sealed class AppDbContext(DbContextOptions<AppDbContext> options) : DbContext(options)
{
    public DbSet<User> Users => Set<User>();
    public DbSet<JobApplication> JobApplications => Set<JobApplication>();
    public DbSet<UserPreference> UserPreferences => Set<UserPreference>();

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
            entity.HasOne(job => job.User).WithMany(user => user.Jobs)
                .HasForeignKey(job => job.UserId).OnDelete(DeleteBehavior.Cascade);
        });

        modelBuilder.Entity<UserPreference>(entity => entity.HasKey(preferences => preferences.UserId));
    }
}
