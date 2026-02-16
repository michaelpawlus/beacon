"""Application prep agent — identifies high-relevance jobs needing applications."""

import logging
import sqlite3

from beacon.agents.base import AgentTask, BaseAgent

logger = logging.getLogger("beacon.agents.application_prep")


class ApplicationPrepAgent(BaseAgent):
    """Identifies high-relevance jobs without applications and suggests preparation."""

    name = "application_prep"

    def plan(self, conn: sqlite3.Connection, context: dict) -> list[AgentTask]:
        """Find high-relevance jobs that haven't been applied to."""
        min_score = context.get("min_relevance", 7.0)

        unapplied = conn.execute(
            """SELECT j.id, j.title, j.relevance_score, c.name as company_name
               FROM job_listings j
               JOIN companies c ON j.company_id = c.id
               LEFT JOIN applications a ON j.id = a.job_id
               WHERE j.status = 'active'
               AND j.relevance_score >= ?
               AND a.id IS NULL
               ORDER BY j.relevance_score DESC
               LIMIT 10""",
            (min_score,),
        ).fetchall()

        tasks = []
        for job in unapplied:
            tasks.append(AgentTask(
                description=(
                    f"Prepare application for {job['title']} at {job['company_name']} "
                    f"(score: {job['relevance_score']:.1f})"
                ),
                data={
                    "job_id": job["id"],
                    "title": job["title"],
                    "company_name": job["company_name"],
                    "relevance_score": job["relevance_score"],
                },
            ))

        return tasks

    def execute(self, conn: sqlite3.Connection, task: AgentTask) -> dict:
        """Create a draft application for a high-relevance job."""
        job_id = task.data["job_id"]

        try:
            # Check that profile has data
            work_count = conn.execute("SELECT COUNT(*) as cnt FROM work_experiences").fetchone()["cnt"]
            if work_count == 0:
                return {
                    "job_id": job_id,
                    "status": "skipped",
                    "reason": "No profile data — run 'beacon profile interview' first",
                }

            # Create a draft application
            from beacon.db.profile import add_application
            app_id = add_application(conn, job_id, status="draft")

            return {
                "job_id": job_id,
                "application_id": app_id,
                "title": task.data["title"],
                "company": task.data["company_name"],
                "status": "draft_created",
            }

        except Exception as e:
            logger.error("Failed to prepare application for job %d: %s", job_id, e)
            return {"job_id": job_id, "error": str(e)}

    def summarize(self, results: list[dict]) -> str:
        created = [r for r in results if r.get("status") == "draft_created"]
        skipped = [r for r in results if r.get("status") == "skipped"]
        errors = [r for r in results if r.get("error")]
        return f"{len(created)} drafts created, {len(skipped)} skipped, {len(errors)} errors"
