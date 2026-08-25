using System.Security.Claims;
using JobTracker.Api.Contracts;
using JobTracker.Api.Data;
using JobTracker.Api.Services;
using JobTracker.Api.Models;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace JobTracker.Api.Controllers;

[ApiController, Authorize, Route("api/jobs")]
public sealed class JobsController(AppDbContext db) : ControllerBase
{
    [HttpGet]
    public async Task<ActionResult<IEnumerable<JobResponse>>> GetAll(CancellationToken cancellationToken)
    {
        var userId = CurrentUserId();
        var jobs = await db.JobApplications.Where(job => job.UserId == userId).OrderByDescending(job => job.UpdatedAtUtc).ToListAsync(cancellationToken);
        return Ok(jobs.Select(ToResponse));
    }

    [HttpPost]
    public async Task<ActionResult<JobResponse>> Create(CreateJobRequest request, CancellationToken cancellationToken)
    {
        if (request.Status == JobStatus.Interview && (request.InterviewRound is null or < 1 or > 10))
            return BadRequest(new { message = "Interview round must be between 1 and 10." });
        var now = DateTime.UtcNow;
        List<StatusEvent> timeline;
        try { timeline = StatusTimelineValidator.Validate(request.Timeline is { Count: > 0 } ? request.Timeline : StatusTimelineValidator.Synthesize(request.Status, request.InterviewRound)); }
        catch (ArgumentException ex) { return BadRequest(new { message = ex.Message }); }
        var job = new JobApplication
        {
            UserId = CurrentUserId(), Company = request.Company.Trim(), Title = request.Title.Trim(),
            Description = request.Description?.Trim() ?? string.Empty, Skills = request.Skills?.Trim() ?? string.Empty,
            Pay = request.Pay?.Trim() ?? string.Empty, Location = request.Location?.Trim() ?? string.Empty,
            Nickname = request.Nickname?.Trim() ?? string.Empty, SourceUrl = request.SourceUrl,
            StatusEvents = timeline, Status = timeline[^1].Status, InterviewRound = timeline.Count(item => item.Status == JobStatus.Interview),
            AppliedAtUtc = request.AppliedAtUtc?.ToUniversalTime() ?? now, UpdatedAtUtc = now
        };
        db.JobApplications.Add(job);
        await db.SaveChangesAsync(cancellationToken);
        return CreatedAtAction(nameof(GetById), new { id = job.Id }, ToResponse(job));
    }

    [HttpGet("{id:guid}")]
    public async Task<ActionResult<JobResponse>> GetById(Guid id, CancellationToken cancellationToken)
    {
        var job = await Find(id, cancellationToken);
        return job is null ? NotFound() : Ok(ToResponse(job));
    }

    [HttpPut("{id:guid}")]
    public async Task<ActionResult<JobResponse>> Update(Guid id, UpdateJobRequest request, CancellationToken cancellationToken)
    {
        var job = await Find(id, cancellationToken);
        if (job is null) return NotFound();
        List<StatusEvent> timeline;
        try { timeline = StatusTimelineValidator.Validate(request.Timeline is { Count: > 0 } ? request.Timeline : StatusTimelineValidator.Synthesize(request.Status, request.Timeline is null ? job.StatusEvents.Count(item => item.Status == JobStatus.Interview) : request.InterviewRound)); }
        catch (ArgumentException ex) { return BadRequest(new { message = ex.Message }); }
        job.Company = request.Company.Trim(); job.Title = request.Title.Trim(); job.Description = request.Description?.Trim() ?? string.Empty;
        job.Skills = request.Skills?.Trim() ?? string.Empty; job.Pay = request.Pay?.Trim() ?? string.Empty; job.Location = request.Location?.Trim() ?? string.Empty;
        job.Nickname = request.Nickname?.Trim() ?? string.Empty;
        job.StatusEvents = timeline; job.Status = timeline[^1].Status; job.InterviewRound = timeline.Count(item => item.Status == JobStatus.Interview);
        if (request.AppliedAtUtc.HasValue) job.AppliedAtUtc = request.AppliedAtUtc.Value.ToUniversalTime();
        job.UpdatedAtUtc = DateTime.UtcNow;
        await db.SaveChangesAsync(cancellationToken);
        return Ok(ToResponse(job));
    }

    [HttpDelete("{id:guid}")]
    public async Task<IActionResult> Delete(Guid id, CancellationToken cancellationToken)
    {
        var job = await Find(id, cancellationToken);
        if (job is null) return NotFound();
        db.JobApplications.Remove(job); await db.SaveChangesAsync(cancellationToken); return NoContent();
    }

    private Task<JobApplication?> Find(Guid id, CancellationToken cancellationToken) => db.JobApplications.SingleOrDefaultAsync(job => job.Id == id && job.UserId == CurrentUserId(), cancellationToken);
    private Guid CurrentUserId() => Guid.Parse(User.FindFirstValue(ClaimTypes.NameIdentifier) ?? throw new InvalidOperationException("Missing user claim."));
    private static JobResponse ToResponse(JobApplication job) => new(job.Id, job.Company, job.Title, job.Description, job.Skills, job.Pay, job.Location, job.Nickname, job.SourceUrl, job.Status, job.InterviewRound, job.AppliedAtUtc, job.UpdatedAtUtc, job.StatusEvents.Select(item => item.Status).ToList());
}
