"""Research agent — identifies and refreshes stale company signals."""

import logging
import sqlite3

from beacon.agents.base import AgentTask, BaseAgent

logger = logging.getLogger("beacon.agents.researcher")


class ResearchAgent(BaseAgent):
    """Identifies companies with stale signals and refreshes scores."""

    name = "researcher"

    def plan(self, conn: sqlite3.Connection, context: dict) -> list[AgentTask]:
        """Find companies that haven't been researched recently."""
        stale_threshold = context.get("stale_days", 30)

        stale = conn.execute(
            """SELECT id, name, last_researched_at,
                      julianday('now') - julianday(last_researched_at) as days_stale
               FROM companies
               WHERE last_researched_at IS NOT NULL
               AND julianday('now') - julianday(last_researched_at) > ?
               ORDER BY days_stale DESC
               LIMIT 10""",
            (stale_threshold,),
        ).fetchall()

        # Also find companies never researched
        never_researched = conn.execute(
            """SELECT id, name FROM companies
               WHERE last_researched_at IS NULL
               LIMIT 5"""
        ).fetchall()

        tasks = []
        for company in stale:
            tasks.append(AgentTask(
                description=f"Refresh signals for {company['name']} (stale {int(company['days_stale'])}d)",
                data={"company_id": company["id"], "company_name": company["name"], "action": "refresh"},
            ))

        for company in never_researched:
            tasks.append(AgentTask(
                description=f"Initial research for {company['name']}",
                data={"company_id": company["id"], "company_name": company["name"], "action": "initial"},
            ))

        return tasks

    def execute(self, conn: sqlite3.Connection, task: AgentTask) -> dict:
        """Refresh signals for a company (recompute scores from existing data)."""
        company_id = task.data["company_id"]

        try:
            from beacon.research.scoring import compute_composite_score

            # Count current signals
            signal_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM ai_signals WHERE company_id = ?",
                (company_id,),
            ).fetchone()["cnt"]

            # Recompute score
            score = compute_composite_score(conn, company_id)

            # Update last_researched_at
            conn.execute(
                "UPDATE companies SET last_researched_at = datetime('now') WHERE id = ?",
                (company_id,),
            )
            conn.commit()

            # Log the refresh
            from beacon.db.feedback import record_signal_refresh
            record_signal_refresh(conn, company_id, signals_updated=signal_count)

            return {
                "company": task.data["company_name"],
                "signals": signal_count,
                "score": score,
            }

        except Exception as e:
            logger.error("Failed to refresh %s: %s", task.data["company_name"], e)
            return {"company": task.data["company_name"], "error": str(e)}

    def summarize(self, results: list[dict]) -> str:
        refreshed = [r for r in results if "score" in r]
        errors = [r for r in results if "error" in r]
        return f"Refreshed {len(refreshed)} companies, {len(errors)} errors"
