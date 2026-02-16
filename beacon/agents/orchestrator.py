"""Agent orchestrator — runs all agents in sequence with plan→execute→summarize."""

import logging
import sqlite3
import time

from beacon.agents.application_prep import ApplicationPrepAgent
from beacon.agents.base import BaseAgent
from beacon.agents.job_analyst import JobAnalystAgent
from beacon.agents.researcher import ResearchAgent
from beacon.config import BeaconConfig

logger = logging.getLogger("beacon.agents.orchestrator")


class Orchestrator:
    """Runs all agents: plan → execute → summarize, logs to automation_log."""

    def __init__(self, agents: list[BaseAgent] | None = None):
        self.agents = agents or [
            ResearchAgent(),
            JobAnalystAgent(),
            ApplicationPrepAgent(),
        ]

    def run(
        self,
        conn: sqlite3.Connection,
        config: BeaconConfig,
        dry_run: bool = False,
        context: dict | None = None,
    ) -> dict[str, str]:
        """Run all agents. Returns {agent_name: summary_string}."""
        started_at = time.time()
        ctx = context or {"min_relevance": config.min_relevance_alert}
        summaries = {}
        total_signals = 0
        total_jobs = 0
        errors_list = []

        for agent in self.agents:
            try:
                tasks = agent.plan(conn, ctx)
                logger.info("Agent %s planned %d tasks", agent.name, len(tasks))

                if dry_run:
                    task_descriptions = [t.description for t in tasks]
                    summaries[agent.name] = f"[dry-run] {len(tasks)} tasks planned: {'; '.join(task_descriptions[:3])}"
                    continue

                results = []
                for task in tasks:
                    result = agent.execute(conn, task)
                    results.append(result)

                summary = agent.summarize(results)
                summaries[agent.name] = summary

                # Track metrics
                if agent.name == "researcher":
                    total_signals += len([r for r in results if "score" in r])
                elif agent.name == "job_analyst":
                    total_jobs += len([r for r in results if r.get("changed")])

            except Exception as e:
                error_msg = f"{agent.name}: {e}"
                logger.error("Agent failed: %s", error_msg)
                errors_list.append(error_msg)
                summaries[agent.name] = f"Error: {e}"

        # Log to automation_log
        if not dry_run:
            duration = time.time() - started_at
            conn.execute(
                """INSERT INTO automation_log
                   (run_type, jobs_found, new_relevant_jobs, signals_refreshed,
                    errors, duration_seconds, completed_at)
                   VALUES ('full', 0, ?, ?, ?, ?, datetime('now'))""",
                (total_jobs, total_signals,
                 "; ".join(errors_list) if errors_list else None,
                 duration),
            )
            conn.commit()

        return summaries
