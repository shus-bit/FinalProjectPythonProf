import typer
import textwrap
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Task, User, TaskLog, TaskStatus, TaskPriority, TaskTrackerError
from reporter import generate_weekly_timesheet

DATABASE_URL = "sqlite:///task_tracker.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Инициализируем Typer
app = typer.Typer()

# Автоматическое создание таблиц при запуске приложения
Base.metadata.create_all(bind=engine)


@app.command("user-add")
def user_add(
        name: str = typer.Option(..., "--name", help="ФИО сотрудника"),
        role: str = typer.Option(..., "--role", help="Роль (Разработчик, Тестировщик, Менеджер)")
) -> None:
    """Добавить нового пользователя/исполнителя в систему."""
    session = SessionLocal()
    user = User(fullname=name, role=role)
    session.add(user)
    session.commit()
    typer.secho(f"Успешно: Пользователь '{name}' (ID: {user.id}) добавлен.", fg=typer.colors.GREEN)
    session.close()


@app.command("task-add")
def task_add(
        title: str = typer.Option(..., "--title", help="Заголовок задачи"),
        priority: str = typer.Option(..., "--priority", help="Приоритет (low, medium, high, blocker)"),
        deadline: str = typer.Option(..., "--deadline", help="Дедлайн в формате ГГГГ-ММ-ДД"),
        description: Optional[str] = typer.Option(None, "--description", help="Описание задачи")
) -> None:
    """Добавить новую задачу в бэклог."""
    session = SessionLocal()
    try:
        parsed_deadline = datetime.strptime(deadline, "%Y-%m-%d")

        try:
            task_priority = TaskPriority(priority.lower())
        except ValueError:
            typer.secho(f"Ошибка: Неверный приоритет '{priority}'. Доступные: low, medium, high, blocker.",
                        fg=typer.colors.RED)
            raise typer.Exit(code=1)

        task = Task(
            title=title,
            description=description,
            priority=task_priority,
            deadline=parsed_deadline,
            status=TaskStatus.TO_DO
        )
        session.add(task)
        session.commit()

        log = TaskLog(task_id=task.id, old_status=None, new_status=TaskStatus.TO_DO)
        session.add(log)
        session.commit()

        typer.secho(f"Успешно: Задача №{task.id} '{title}' добавлена в бэклог.", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"Критическая ошибка: {e}", fg=typer.colors.RED)
    finally:
        session.close()


@app.command("task-assign")
def task_assign(
        task_id: int = typer.Option(..., "--task-id", help="ID задачи"),
        user_id: int = typer.Option(..., "--user-id", help="ID пользователя")
) -> None:
    """Назначить исполнителя на задачу."""
    session = SessionLocal()
    task = session.get(Task, task_id)
    user = session.get(User, user_id)

    if not task or not user:
        typer.secho("Ошибка: Задача или Пользователь не найдены.", fg=typer.colors.RED)
        session.close()
        raise typer.Exit(code=1)

    task.assignee_id = user.id
    session.commit()
    typer.secho(f"Успешно: Задача №{task_id} назначена на {user.fullname}.", fg=typer.colors.GREEN)
    session.close()


@app.command("task-move")
def task_move(
        task_id: int = typer.Option(..., "--task-id", help="ID задачи"),
        status: str = typer.Option(..., "--status",
                                   help="Целевой статус (todo, inprogress, review, codereview, testing, done)")
) -> None:
    """Сменить статус задачи с валидацией через State Machine."""
    session = SessionLocal()
    task = session.get(Task, task_id)

    if not task:
        typer.secho("Ошибка: Задача не найдена.", fg=typer.colors.RED)
        session.close()
        raise typer.Exit(code=1)

    normalized_status = status.lower().replace(" ", "")

    status_map = {
        "todo": TaskStatus.TO_DO,
        "inprogress": TaskStatus.IN_PROGRESS,
        "codereview": TaskStatus.CODE_REVIEW,
        "review": TaskStatus.CODE_REVIEW,
        "testing": TaskStatus.TESTING,
        "done": TaskStatus.DONE
    }

    target_status = status_map.get(normalized_status)
    if not target_status:
        typer.secho(f"Ошибка: Неизвестный статус '{status}'. Доступные: todo, inprogress, review, testing, done.",
                    fg=typer.colors.RED)
        session.close()
        raise typer.Exit(code=1)

    try:
        old_status = task.status
        task.move_to_status(target_status)

        log = TaskLog(task_id=task.id, old_status=old_status, new_status=target_status)
        session.add(log)
        session.commit()

        typer.secho(f"Успешно: Статус задачи №{task_id} изменен на '{target_status.value}'.", fg=typer.colors.GREEN)
    except TaskTrackerError as b_err:
        typer.secho(f"Бизнес-ошибка: {b_err}", fg=typer.colors.YELLOW)
    finally:
        session.close()


@app.command("backlog")
def view_backlog(
        sort: str = typer.Option("priority", "--sort", help="Критерий сортировки (по умолчанию: priority)")
) -> None:
    """Посмотреть бэклог задач с аккуратным переносом длинных заголовков по словам."""
    session = SessionLocal()
    tasks = session.query(Task).all()

    if sort == "priority":
        #tasks = sorted(tasks, key=lambda t: t.priority, reverse=True)
        # Сортирует: 1. По весу приоритета (критичные выше) 2. По дедлайну (ближайшие выше)
        tasks = sorted(tasks, key=lambda t: (t.priority, -t.deadline.timestamp()), reverse=True)

    typer.echo(f"{'ID':<5} | {'Заголовок':<25} | {'Приоритет':<10} | {'Статус':<15} | {'Дедлайн':<12}")
    typer.echo("-" * 76)

    for t in tasks:
        title_lines = textwrap.wrap(t.title, width=25)

        if not title_lines:
            title_lines = [""]

        task_id = str(t.id)
        priority = t.priority.value
        status = t.status.value
        deadline = t.deadline.strftime('%Y-%m-%d')

        typer.echo(
            f"{task_id:<5} | "
            f"{title_lines[0]:<25} | "
            f"{priority:<10} | "
            f"{status:<15} | "
            f"{deadline:<12}"
        )

        for extra_line in title_lines[1:]:
            typer.echo(
                f"{'':<5} | "
                f"{extra_line:<25} | "
                f"{'':<10} | "
                f"{'':<15} | "
                f"{'':<12}"
            )

        typer.echo("-" * 76)

    session.close()


@app.command("timesheet")
def timesheet(
        week: int = typer.Option(..., "--week", help="Номер недели для отчета"),
        year: int = typer.Option(..., "--year", help="Год отчета"),
        output: str = typer.Option("timesheet.xlsx", "--output", help="Имя выходного Excel-файла")
) -> None:
    """Сгенерировать еженедельный Excel-отчет."""
    session = SessionLocal()
    try:
        generate_weekly_timesheet(session, year, week, output)
        typer.secho(f"Отчет успешно сохранен в файл {output}", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"Ошибка при генерации отчета: {e}", fg=typer.colors.RED)
    finally:
        session.close()


@app.command("report-all")
def report_all(
        output: str = typer.Option("all_tasks.xlsx", "--output", help="Имя выходного Excel-файла")
) -> None:
    """Сгенерировать единый Excel-отчет по абсолютно всем задачам из базы данных."""
    session = SessionLocal()
    try:
        generate_weekly_timesheet(session, year=0, week=0, output_path=output)
        typer.secho(f"Полный отчет успешно сохранен в файл {output}", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"Ошибка при генерации полного отчета: {e}", fg=typer.colors.RED)
    finally:
        session.close()


if __name__ == "__main__":
    app()