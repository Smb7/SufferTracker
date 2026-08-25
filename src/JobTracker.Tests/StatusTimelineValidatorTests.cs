using JobTracker.Api.Models;
using JobTracker.Api.Services;
using Xunit;

namespace JobTracker.Tests;

public sealed class StatusTimelineValidatorTests
{
    [Fact]
    public void Validate_AcceptsAppliedOnlyTimeline()
    {
        var events = StatusTimelineValidator.Validate([JobStatus.Applied]);

        Assert.Single(events);
        Assert.Equal(JobStatus.Applied, events[0].Status);
    }

    [Fact]
    public void Validate_AcceptsSequentialInterviewRounds()
    {
        var events = StatusTimelineValidator.Validate([JobStatus.Applied, JobStatus.Interview, JobStatus.Interview, JobStatus.Interview]);

        Assert.Equal(4, events.Count);
        Assert.Equal(3, events.Count(item => item.Status == JobStatus.Interview));
    }

    [Fact]
    public void Validate_UnlocksJobOfferAfterAnInterview()
    {
        var events = StatusTimelineValidator.Validate([JobStatus.Applied, JobStatus.Interview, JobStatus.JobOffer]);

        Assert.Equal(JobStatus.JobOffer, events[^1].Status);
    }

    [Fact]
    public void Validate_RejectsJobOfferWithoutInterview()
    {
        var ex = Assert.Throws<ArgumentException>(() => StatusTimelineValidator.Validate([JobStatus.Applied, JobStatus.JobOffer]));

        Assert.Contains("interview", ex.Message, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void Validate_RejectsTimelinesNotStartingWithApplied()
    {
        Assert.Throws<ArgumentException>(() => StatusTimelineValidator.Validate([JobStatus.Interview]));
        Assert.Throws<ArgumentException>(() => StatusTimelineValidator.Validate([]));
    }

    [Fact]
    public void Validate_RejectsAppliedAppearingTwice()
    {
        Assert.Throws<ArgumentException>(() => StatusTimelineValidator.Validate([JobStatus.Applied, JobStatus.Interview, JobStatus.Applied]));
    }

    [Fact]
    public void Validate_NothingFollowsTerminalStatuses()
    {
        Assert.Throws<ArgumentException>(() => StatusTimelineValidator.Validate([JobStatus.Applied, JobStatus.Rejected, JobStatus.Interview]));
        Assert.Throws<ArgumentException>(() => StatusTimelineValidator.Validate([JobStatus.Applied, JobStatus.Ghosted, JobStatus.JobOffer]));
        Assert.Throws<ArgumentException>(() => StatusTimelineValidator.Validate([JobStatus.Applied, JobStatus.Interview, JobStatus.JobOffer, JobStatus.Interview]));
    }

    [Fact]
    public void Validate_TerminalStatusesAreReachableFromAnyLiveStage()
    {
        Assert.Equal(JobStatus.Rejected, StatusTimelineValidator.Validate([JobStatus.Applied, JobStatus.Rejected])[^1].Status);
        Assert.Equal(JobStatus.Ghosted, StatusTimelineValidator.Validate([JobStatus.Applied, JobStatus.Interview, JobStatus.Ghosted])[^1].Status);
    }

    [Theory]
    [InlineData(new[] { 0 }, new[] { 5 })]                 // Waiting legacy -> Applied only
    [InlineData(new[] { 1, 3 }, new[] { 5, 1, 1, 1 })]     // Interview round 3 -> Applied + I,I,I
    public void Synthesize_BuildsValidPrefixes(int[] legacy, int[] expected)
    {
        var timeline = StatusTimelineValidator.Synthesize((JobStatus)legacy[0], legacy.ElementAtOrDefault(1));

        Assert.Equal(expected.Select(value => (JobStatus)value), timeline);
        StatusTimelineValidator.Validate(timeline); // synthesized prefixes always pass validation
    }
}
