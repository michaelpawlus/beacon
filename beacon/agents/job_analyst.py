"""Job analyst agent — re-analyzes borderline-scored jobs."""

import logging
import sqlite3

from beacon.agents.base import AgentTask, BaseAgent

logger = logging.getLogger("beacon.agents.job_analyst")


class JobAnalystAgent(BaseAgent):
    """LLM re-analyzes borderline-scored jobs (relevance 4-7)."""

    name = "job_analyst"

    def plan(self, conn: sqlite3.Connection, context: dict) -> list[AgentTask]:
        """Find active jobs with borderline relevance scores."""
        low = context.get("borderline_low", 4.0)
        high = context.get("borderline_high", 7.0)

        borderline = conn.execute(
            """SELECT j.id, j.title, j.relevance_score, c.name as company_name
               FROM job_listings j
               JOIN companies c ON j.company_id = c.id
               WHERE j.status = 'active'
               AND j.relevance_score BETWEEN ? AND ?
               ORDER BY j.relevance_score DESC
               LIMIT 20""",
            (low, high),
        ).fetchall()

        tasks = []
        for job in borderline:
            tasks.append(AgentTask(
                description=(
                    f"Re-analyze {job['title']} at {job['company_name']} "
                    f"(current: {job['relevance_score']:.1f})"
                ),
                data={
                    "job_id": job["id"],
                    "title": job["title"],
                    "company_name": job["company_name"],
                    "current_score": job["relevance_score"],
                },
            ))

        return tasks

    def execute(self, conn: sqlite3.Connection, task: AgentTask) -> dict:
        """Re-score a borderline job using the existing scoring algorithm."""
        job_id = task.data["job_id"]

        try:
            job = conn.execute(
                "SELECT * FROM job_listings WHERE id = ?", (job_id,)
            ).fetchone()

            if not job:
                return {"job_id": job_id, "error": "Job not found"}

            from beacon.research.job_scoring import compute_job_relevance

            job_data = {
                "title": job["title"],
                "description_text": job["description_text"],
                "location": job["location"],
                "department": job["department"],
            }

            relevance = compute_job_relevance(job_data)
            new_score = relevance["score"]

            # Update if score changed
            if abs(new_score - task.data["current_score"]) > 0.1:
                import json
                conn.execute(
                    "UPDATE job_listings SET relevance_score = ?, match_reasons = ? WHERE id = ?",
                    (new_score, json.dumps(relevance["reasons"]), job_id),
                )
                conn.commit()

            return {
                "job_id": job_id,
                "title": task.data["title"],
                "old_score": task.data["current_score"],
                "new_score": new_score,
                "changed": abs(new_score - task.data["current_score"]) > 0.1,
            }

        except Exception as e:
            logger.error("Failed to re-analyze job %d: %s", job_id, e)
            return {"job_id": job_id, "error": str(e)}

    def summarize(self, results: list[dict]) -> str:
        changed = [r for r in results if r.get("changed")]
        errors = [r for r in results if r.get("error")]
        return f"Analyzed {len(results)} jobs, {len(changed)} rescored, {len(errors)} errors"
