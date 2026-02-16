"""Base agent abstract class."""

import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AgentTask:
    """A task for an agent to execute."""

    description: str
    data: dict | None = None


@dataclass
class AgentResult:
    """Result from an agent execution."""

    tasks_planned: int = 0
    tasks_executed: int = 0
    summary: str = ""
    errors: list[str] | None = None


class BaseAgent(ABC):
    """Abstract base class for Beacon agents."""

    name: str = "base"

    @abstractmethod
    def plan(self, conn: sqlite3.Connection, context: dict) -> list[AgentTask]:
        """Analyze the current state and plan tasks."""

    @abstractmethod
    def execute(self, conn: sqlite3.Connection, task: AgentTask) -> dict:
        """Execute a single planned task. Returns result dict."""

    def summarize(self, results: list[dict]) -> str:
        """Summarize the results of all executed tasks."""
        count = len(results)
        errors = [r.get("error") for r in results if r.get("error")]
        if errors:
            return f"{count} tasks, {len(errors)} errors"
        return f"{count} tasks completed"
