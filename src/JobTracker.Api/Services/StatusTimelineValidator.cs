using JobTracker.Api.Models;

namespace JobTracker.Api.Services;

public static class StatusTimelineValidator
{
    public static readonly JobStatus[] TerminalStatuses = [JobStatus.JobOffer, JobStatus.Ghosted, JobStatus.Rejected];

    /// <summary>
    /// Validates a requested, ordered status progression and returns the normalized event list.
    /// Rules: must start with Applied; interviews advance at most one round per step;
    /// Job Offer unlocks only after at least one recorded interview; nothing may follow a
    /// terminal status (Job Offer, Ghosted, Rejected).
    /// </summary>
    public static List<StatusEvent> Validate(IReadOnlyList<JobStatus> requested)
    {
        if (requested.Count == 0)
            throw new ArgumentException("A status timeline is required.", nameof(requested));
        if (requested[0] != JobStatus.Applied)
            throw new ArgumentException("Every application starts with an 'Applied' status.", nameof(requested));

        var events = new List<StatusEvent>();
        var interviewRound = 0;
        foreach (var status in requested)
        {
            if (events.Count > 0 && status == JobStatus.Interview && events[^1].Status == JobStatus.Interview)
            {
                // Consecutive interviews are intentional: each event advances the round.
            }
            else if (events.Count > 0 && events[^1].Status == status)
            {
                continue;
            }

            if (TerminalStatuses.Contains(events.LastOrDefault()?.Status ?? JobStatus.Applied) && events.Count > 0)
                throw new ArgumentException($"'{events[^1].Status}' is final; no further statuses can be added after it.");

            switch (status)
            {
                case JobStatus.Waiting:
                    continue; // Legacy alias for Applied.
                case JobStatus.Applied:
                    if (events.Count > 0) throw new ArgumentException("'Applied' can only appear once, at the start of the timeline.");
                    break;
                case JobStatus.Interview:
                    if (interviewRound >= MaxInterviewRounds)
                        throw new ArgumentException("Interview rounds cannot exceed 10.");
                    interviewRound++;
                    break;
                case JobStatus.JobOffer:
                    if (interviewRound == 0)
                        throw new ArgumentException("Record at least one interview before marking a job offer.");
                    break;
            }

            events.Add(new StatusEvent { Status = status, OccurredAtUtc = DateTime.UtcNow });
        }

        return events;
    }

    /// <summary>
    /// Builds a valid progression for clients that only know the target status
    /// (legacy payloads): everything leading up to that status is synthesized.
    /// </summary>
    public static List<JobStatus> Synthesize(JobStatus target, int? interviewRound)
    {
        var round = Math.Clamp(interviewRound ?? 1, 1, 10);
        var timeline = new List<JobStatus> { JobStatus.Applied };
        switch (target)
        {
            case JobStatus.Waiting:
                break;
            case JobStatus.Interview:
                for (var index = 1; index <= round; index++) timeline.Add(JobStatus.Interview);
                break;
            case JobStatus.JobOffer:
                timeline.Add(JobStatus.Interview);
                timeline.Add(JobStatus.JobOffer);
                break;
            default:
                timeline.Add(target);
                break;
        }
        return timeline;
    }

    private const int MaxInterviewRounds = 10;
}
