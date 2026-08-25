using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JobTracker.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddStatusEvents : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "StatusEvents",
                table: "JobApplications",
                type: "jsonb",
                nullable: false,
                defaultValue: "[]");

            migrationBuilder.Sql("""
                UPDATE "JobApplications" SET "StatusEvents" =
                    jsonb_build_array(jsonb_build_object('status', 'Applied', 'occurredAtUtc', "AppliedAtUtc"))
                    || CASE
                        WHEN "Status" = 'Interview' THEN (
                            SELECT jsonb_agg(jsonb_build_object('status', 'Interview', 'occurredAtUtc',
                                least("AppliedAtUtc" + (gs * INTERVAL '3 days'), now())))
                            FROM generate_series(1, COALESCE("InterviewRound", 1)) AS gs)
                        WHEN "Status" = 'JobOffer' THEN jsonb_build_array(
                            jsonb_build_object('status', 'Interview', 'occurredAtUtc', "AppliedAtUtc"),
                            jsonb_build_object('status', 'JobOffer', 'occurredAtUtc', "UpdatedAtUtc"))
                        WHEN "Status" IN ('Ghosted', 'Rejected') THEN jsonb_build_array(
                            jsonb_build_object('status', lower("Status"::text), 'occurredAtUtc', "UpdatedAtUtc"))
                        ELSE '[]'::jsonb
                    END;
            """);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "StatusEvents",
                table: "JobApplications");
        }
    }
}
