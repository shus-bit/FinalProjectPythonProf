import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import (
    Base, Task, User, TaskStatus, TaskPriority,
    InvalidStateTransitionError, UnassignedTaskError
)


# Настройка тестовой БД в памяти
@pytest.fixture(name="db_session")
def fixture_db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()


@pytest.fixture(name="sample_user")
def fixture_sample_user(db_session):
    user = User(fullname="Алексей Иванов", role="Разработчик")
    db_session.add(user)
    db_session.commit()
    return user


# --- ТЕСТЫ МОДУЛЯ 3: СРАВНЕНИЕ ПРИОРИТЕТОВ ---

def test_priority_comparison():
    """Проверка ООП-логики сравнения приоритетов на основе весов."""
    assert TaskPriority.BLOCKER > TaskPriority.HIGH
    assert TaskPriority.HIGH > TaskPriority.MEDIUM
    assert TaskPriority.MEDIUM > TaskPriority.LOW
    assert TaskPriority.BLOCKER > TaskPriority.LOW
    assert TaskPriority.LOW == TaskPriority.LOW
    assert TaskPriority.HIGH != TaskPriority.BLOCKER


def test_backlog_sorting_by_priority():
    """Проверка корректности сортировки списка задач по весу приоритета."""
    # Создаем фиктивные объекты задач для проверки стандартной сортировки sorted()
    task_low = Task(title="Task 1", priority=TaskPriority.LOW, deadline=datetime.now())
    task_blocker = Task(title="Task 2", priority=TaskPriority.BLOCKER, deadline=datetime.now())
    task_high = Task(title="Task 3", priority=TaskPriority.HIGH, deadline=datetime.now())

    unordered_tasks = [task_low, task_blocker, task_high]

    # Сортируем от самых критичных к наименее важным (reverse=True)
    sorted_tasks = sorted(unordered_tasks, key=lambda t: t.priority, reverse=True)

    assert sorted_tasks[0].priority == TaskPriority.BLOCKER
    assert sorted_tasks[1].priority == TaskPriority.HIGH
    assert sorted_tasks[2].priority == TaskPriority.LOW


# --- ТЕСТЫ МОДУЛЯ 2: КОНЕЧНЫЙ АВТОМАТ (STATE MACHINE) ---

def test_valid_status_transitions(db_session, sample_user):
    """Проверка цепочки валидных переходов: To Do -> In Progress -> Code Review -> Testing -> Done."""
    task = Task(
        title="Тестовая задача",
        priority=TaskPriority.MEDIUM,
        deadline=datetime.now(),
        status=TaskStatus.TO_DO
    )
    db_session.add(task)
    db_session.commit()

    # Сначала назначаем исполнителя, иначе не сможем перевести в In Progress
    task.assignee_id = sample_user.id
    db_session.commit()

    # Идем по цепочке
    task.move_to_status(TaskStatus.IN_PROGRESS)
    assert task.status == TaskStatus.IN_PROGRESS

    task.move_to_status(TaskStatus.CODE_REVIEW)
    assert task.status == TaskStatus.CODE_REVIEW

    task.move_to_status(TaskStatus.TESTING)
    assert task.status == TaskStatus.TESTING

    task.move_to_status(TaskStatus.DONE)
    assert task.status == TaskStatus.DONE


def test_invalid_status_transition_raises_error(db_session):
    """Попытка перепрыгнуть статус (To Do -> Testing) должна вызывать ошибку."""
    task = Task(
        title="Тестовая задача",
        priority=TaskPriority.MEDIUM,
        deadline=datetime.now(),
        status=TaskStatus.TO_DO
    )
    db_session.add(task)
    db_session.commit()

    # Попытка прыгнуть в обход процесса
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        task.move_to_status(TaskStatus.TESTING)

    assert "Запрещенный переход" in str(exc_info.value)
    # Статус в базе должен остаться прежним
    assert task.status == TaskStatus.TO_DO


def test_unassigned_task_cannot_move_to_in_progress(db_session):
    """Задача без исполнителя не может быть переведена в статус 'In Progress'."""
    task = Task(
        title="Задача без автора",
        priority=TaskPriority.HIGH,
        deadline=datetime.now(),
        status=TaskStatus.TO_DO,
        assignee_id=None  # Исполнитель отсутствует
    )
    db_session.add(task)
    db_session.commit()

    with pytest.raises(UnassignedTaskError) as exc_info:
        task.move_to_status(TaskStatus.IN_PROGRESS)

    assert "не назначен исполнитель" in str(exc_info.value)
    assert task.status == TaskStatus.TO_DO


def test_backward_transition_allowed(db_session, sample_user):
    """Проверка разрешенного отката назад (например, из Testing обратно в In Progress)."""
    task = Task(
        title="Баг-репорт",
        priority=TaskPriority.BLOCKER,
        deadline=datetime.now(),
        status=TaskStatus.TESTING,
        assignee_id=sample_user.id
    )
    db_session.add(task)
    db_session.commit()

    # Согласно матрице ALLOWED_TRANSITIONS, из TESTING можно вернуться в IN_PROGRESS
    task.move_to_status(TaskStatus.IN_PROGRESS)
    assert task.status == TaskStatus.IN_PROGRESS


def test_out_of_done_transition_forbidden(db_session, sample_user):
    """Из финального статуса Done нельзя переводить задачу никуда."""
    task = Task(
        title="Завершенная задача",
        priority=TaskPriority.LOW,
        deadline=datetime.now(),
        status=TaskStatus.DONE,
        assignee_id=sample_user.id
    )
    db_session.add(task)
    db_session.commit()

    with pytest.raises(InvalidStateTransitionError):
        task.move_to_status(TaskStatus.TO_DO)