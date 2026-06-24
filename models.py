from datetime import datetime, UTC
from enum import Enum
from functools import total_ordering
from typing import List, Optional, Any
from sqlalchemy import ForeignKey, String, DateTime, Enum as SQLEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TaskStatus(Enum):
    TO_DO = "To Do"
    IN_PROGRESS = "In Progress"
    CODE_REVIEW = "Code Review"
    TESTING = "Testing"
    DONE = "Done"

    def __hash__(self) -> int:
        return hash(self.value)


@total_ordering
class TaskPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKER = "blocker"

    @property
    def weight(self) -> int:
        weights = {
            TaskPriority.LOW: 1,
            TaskPriority.MEDIUM: 2,
            TaskPriority.HIGH: 3,
            TaskPriority.BLOCKER: 4
        }
        return weights[self]

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, TaskPriority):
            return NotImplemented
        return self.weight < other.weight

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, TaskPriority):
            return NotImplemented
        return self.weight == other.weight

    def __hash__(self) -> int:
        return hash(self.value)


# --- Исключения бизнес-логики ---
class TaskTrackerError(Exception):
    """Базовое исключение для трекера задач."""
    pass


class InvalidStateTransitionError(TaskTrackerError):
    """Исключение при некорректном переходе между статусами задач."""
    pass


class UnassignedTaskError(TaskTrackerError):
    """Исключение при попытке взять в работу задачу без исполнителя."""
    pass


# --- Матрица переходов бизнес-процесса ---
ALLOWED_TRANSITIONS = {
    TaskStatus.TO_DO: [TaskStatus.IN_PROGRESS],
    TaskStatus.IN_PROGRESS: [TaskStatus.CODE_REVIEW, TaskStatus.TO_DO],
    TaskStatus.CODE_REVIEW: [TaskStatus.TESTING, TaskStatus.IN_PROGRESS],
    TaskStatus.TESTING: [TaskStatus.DONE, TaskStatus.IN_PROGRESS],
    TaskStatus.DONE: []
}


# --- Описание моделей БД ---
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    fullname: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)

    tasks: Mapped[List["Task"]] = relationship(back_populates="assignee")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500))
    assignee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus, values_callable=lambda x: [e.value for e in x]),
        default=TaskStatus.TO_DO
    )
    priority: Mapped[TaskPriority] = mapped_column(
        SQLEnum(TaskPriority, values_callable=lambda x: [e.value for e in x]),
        default=TaskPriority.LOW
    )

    deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )

    assignee: Mapped[Optional["User"]] = relationship(back_populates="tasks")
    logs: Mapped[List["TaskLog"]] = relationship(back_populates="task", cascade="all, delete-orphan")

    def move_to_status(self, new_status: TaskStatus) -> None:
        if self.status == new_status:
            return

        if new_status == TaskStatus.IN_PROGRESS and not self.assignee_id:
            raise UnassignedTaskError("Нельзя взять задачу в 'In Progress', если у нее не назначен исполнитель.")

        valid_statuses = ALLOWED_TRANSITIONS.get(self.status, [])
        if new_status not in valid_statuses:
            raise InvalidStateTransitionError(
                f"Запрещенный переход: из '{self.status.value}' в '{new_status.value}'."
            )

        self.status = new_status


class TaskLog(Base):
    __tablename__ = "task_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))

    old_status: Mapped[Optional[TaskStatus]] = mapped_column(
        SQLEnum(TaskStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=True
    )
    new_status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus, values_callable=lambda x: [e.value for e in x])
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )

    task: Mapped["Task"] = relationship(back_populates="logs")