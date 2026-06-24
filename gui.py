import customtkinter as ctk
from datetime import datetime, UTC
from typing import List, Any, Optional
from tkinter import filedialog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import (
    Base, Task, User, TaskLog, TaskStatus, TaskPriority,
    TaskTrackerError, ALLOWED_TRANSITIONS
)
from reporter import generate_weekly_timesheet

DATABASE_URL = "sqlite:///task_tracker.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class TaskTrackerGUI(ctk.CTk):  # type: ignore[misc]
    def __init__(self) -> None:
        super().__init__()

        self.title("Система управления задачами (Task Tracker GUI)")
        self.geometry("1450x780")
        self.minsize(1350, 600)

        # --- ЛЕВАЯ ПАНЕЛЬ ---
        self.left_panel = ctk.CTkFrame(self, width=410, corner_radius=0)
        self.left_panel.pack(side="left", fill="y", padx=0, pady=0)
        self.left_panel.pack_propagate(False)

        self.lbl_title = ctk.CTkLabel(self.left_panel, text="Панель управления", font=ctk.CTkFont(size=18, weight="bold"))
        self.lbl_title.pack(padx=20, pady=10)

        # Форма пользователя
        self.user_frame = ctk.CTkFrame(self.left_panel)
        self.user_frame.pack(padx=15, pady=5, fill="x")

        self.lbl_user_form = ctk.CTkLabel(self.user_frame, text="Новый исполнитель", font=ctk.CTkFont(weight="bold"))
        self.lbl_user_form.pack(padx=10, pady=2)

        self.entry_user_name = ctk.CTkEntry(self.user_frame, placeholder_text="ФИО сотрудника")
        self.entry_user_name.pack(padx=10, pady=3, fill="x")

        self.entry_user_role = ctk.CTkEntry(self.user_frame, placeholder_text="Роль (Разработчик, Тестировщик)")
        self.entry_user_role.pack(padx=10, pady=3, fill="x")

        self.btn_add_user = ctk.CTkButton(self.user_frame, text="Создать пользователя", fg_color="purple", hover_color="indigo", command=self.add_user)
        self.btn_add_user.pack(padx=10, pady=6, fill="x")

        # Форма задачи
        self.form_frame = ctk.CTkFrame(self.left_panel)
        self.form_frame.pack(padx=15, pady=5, fill="x")

        self.lbl_form = ctk.CTkLabel(self.form_frame, text="Новая задача", font=ctk.CTkFont(weight="bold"))
        self.lbl_form.pack(padx=10, pady=2)

        self.entry_task_title = ctk.CTkEntry(self.form_frame, placeholder_text="Название задачи")
        self.entry_task_title.pack(padx=10, pady=3, fill="x")

        self.combo_priority = ctk.CTkComboBox(self.form_frame, values=[p.value for p in TaskPriority])
        self.combo_priority.set(TaskPriority.LOW.value)
        self.combo_priority.pack(padx=10, pady=3, fill="x")

        self.combo_task_assignee = ctk.CTkComboBox(self.form_frame, values=["Не назначен"])
        self.combo_task_assignee.set("Не назначен")
        self.combo_task_assignee.pack(padx=10, pady=3, fill="x")

        self.entry_deadline = ctk.CTkEntry(self.form_frame, placeholder_text="Дедлайн (ГГГГ-ММ-ДД)")
        self.entry_deadline.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.entry_deadline.pack(padx=10, pady=3, fill="x")

        self.btn_add_task = ctk.CTkButton(self.form_frame, text="Добавить в бэклог", command=self.add_task)
        self.btn_add_task.pack(padx=10, pady=8, fill="x")

        # Форма отчетов
        self.report_frame = ctk.CTkFrame(self.left_panel)
        self.report_frame.pack(padx=15, pady=5, fill="x")

        self.lbl_report = ctk.CTkLabel(self.report_frame, text="Параметры еженедельного отчета", font=ctk.CTkFont(weight="bold"))
        self.lbl_report.pack(padx=10, pady=2)

        self.dates_frame = ctk.CTkFrame(self.report_frame, fg_color="transparent")
        self.dates_frame.pack(fill="x", padx=10, pady=3)

        current_year, current_week, _ = datetime.now().isocalendar()

        self.entry_report_year = ctk.CTkEntry(self.dates_frame, placeholder_text="Год", width=80)
        self.entry_report_year.insert(0, str(current_year))
        self.entry_report_year.pack(side="left", padx=(0, 10))

        self.entry_report_week = ctk.CTkEntry(self.dates_frame, placeholder_text="Неделя", width=80)
        self.entry_report_week.insert(0, str(current_week))
        self.entry_report_week.pack(side="left")

        self.btn_report_week = ctk.CTkButton(self.report_frame, text="Выгрузить неделю по выбору", fg_color="#1f538d", hover_color="#14375e", command=self.export_weekly_excel)
        self.btn_report_week.pack(padx=10, pady=4, fill="x")

        self.btn_report_all = ctk.CTkButton(self.report_frame, text="Выгрузить ВСЕ задачи базы", fg_color="green", hover_color="darkgreen", command=self.export_all_excel)
        self.btn_report_all.pack(padx=10, pady=4, fill="x")

        # Текстовая таблица пользователей
        self.users_list_frame = ctk.CTkFrame(self.left_panel)
        self.users_list_frame.pack(padx=15, pady=5, fill="both", expand=True)

        self.lbl_users_list = ctk.CTkLabel(self.users_list_frame, text="Список исполнителей в БД", font=ctk.CTkFont(weight="bold"))
        self.lbl_users_list.pack(padx=10, pady=2)

        self.txt_users_table = ctk.CTkTextbox(self.users_list_frame, font=ctk.CTkFont(family="Courier", size=11), wrap="none", activate_scrollbars=True)
        self.txt_users_table.pack(padx=10, pady=5, fill="both", expand=True)
        self.txt_users_table.configure(state="disabled")

        # --- ПРАВАЯ ПАНЕЛЬ ---
        self.right_panel = ctk.CTkFrame(self)
        self.right_panel.pack(side="right", fill="both", expand=True, padx=15, pady=15)

        # Контейнер для строки заголовка бэклога и нового Чекбокса (в одну строчку)
        self.top_backlog_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        self.top_backlog_frame.pack(fill="x", padx=10, pady=10)

        self.lbl_backlog = ctk.CTkLabel(self.top_backlog_frame, text="Текущий Бэклог (Сортировка по приоритету)", font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_backlog.pack(side="left", anchor="w")

        # 🔥 ДОРАБОТКА: Интерактивный чекбокс скрытия выполненных задач
        self.check_hide_done = ctk.CTkCheckBox(self.top_backlog_frame, text="Скрыть завершенные (Done)", font=ctk.CTkFont(size=12), command=self.refresh_backlog_view)
        self.check_hide_done.pack(side="right", anchor="e", padx=15)

        # Шапка Бэклога
        self.headers_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        self.headers_frame.pack(fill="x", padx=25, pady=0)

        ctk.CTkLabel(self.headers_frame, text="ID", font=ctk.CTkFont(family="Courier", weight="bold"), width=35, anchor="w").pack(side="left")
        ctk.CTkFrame(self.headers_frame, width=1, height=20, fg_color="#555555").pack(side="left", padx=5)

        ctk.CTkLabel(self.headers_frame, text="Заголовок задачи", font=ctk.CTkFont(family="Courier", weight="bold"), width=165, anchor="w").pack(side="left")
        ctk.CTkFrame(self.headers_frame, width=1, height=20, fg_color="#555555").pack(side="left", padx=5)

        ctk.CTkLabel(self.headers_frame, text="Исполнитель задачи", font=ctk.CTkFont(family="Courier", weight="bold"), width=160, anchor="w").pack(side="left")
        ctk.CTkFrame(self.headers_frame, width=1, height=20, fg_color="#555555").pack(side="left", padx=5)

        ctk.CTkLabel(self.headers_frame, text="Приоритет", font=ctk.CTkFont(family="Courier", weight="bold"), width=90, anchor="w").pack(side="left")
        ctk.CTkFrame(self.headers_frame, width=1, height=20, fg_color="#555555").pack(side="left", padx=5)

        ctk.CTkLabel(self.headers_frame, text="Дедлайн", font=ctk.CTkFont(family="Courier", weight="bold"), width=95, anchor="w").pack(side="left")
        ctk.CTkFrame(self.headers_frame, width=1, height=20, fg_color="#555555").pack(side="left", padx=5)

        ctk.CTkLabel(self.headers_frame, text="Дата закрытия", font=ctk.CTkFont(family="Courier", weight="bold"), width=110, anchor="w").pack(side="left")
        ctk.CTkFrame(self.headers_frame, width=1, height=20, fg_color="#555555").pack(side="left", padx=5)

        ctk.CTkLabel(self.headers_frame, text="Текущий статус / Смена этапа ЖЦ", font=ctk.CTkFont(family="Courier", weight="bold"), width=140, anchor="e").pack(side="right", padx=10)

        self.scrollable_frame = ctk.CTkScrollableFrame(self.right_panel)
        self.scrollable_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.lbl_status_msg = ctk.CTkLabel(self.left_panel, text="Система готова", text_color="gray")
        self.lbl_status_msg.pack(side="bottom", padx=20, pady=5)

        self.refresh_backlog_view()
        self.refresh_users_view()

    def show_msg(self, text: str, color: str = "gray") -> None:
        self.lbl_status_msg.configure(text=text, text_color=color)

    def refresh_users_view(self) -> None:
        """Обновление текстовой таблицы исполнителей без переносов и обновление выпадающих списков."""
        self.txt_users_table.configure(state="normal")
        self.txt_users_table.delete("1.0", "end")

        session = SessionLocal()
        users = session.query(User).order_by(User.id).all()

        table_content = f"{'ID':<3} | {'Имя / ФИО сотрудника':<22} | {'Роль':<16}\n"
        table_content += "-" * 48 + "\n"

        for u in users:
            name_short = u.fullname[:22]
            role_short = u.role[:16]
            table_content += f"{u.id:<3} | {name_short:<22} | {role_short:<16}\n"

        if not users:
            table_content += "База исполнителей пуста.\n"

        self.txt_users_table.insert("1.0", table_content)
        self.txt_users_table.configure(state="disabled")

        user_options = ["Не назначен"] + [f"{u.id}: {u.fullname[:15]}" for u in users]
        self.combo_task_assignee.configure(values=user_options)

        session.close()

    def refresh_backlog_view(self) -> None:
        """Перерисовка бэклога с фильтрацией выполненных задач по чекбоксу и сеткой границ."""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        session = SessionLocal()
        all_users = session.query(User).order_by(User.id).all()
        user_options = ["Не назначен"] + [f"{u.id}: {u.fullname[:15]}" for u in all_users]

        tasks = session.query(Task).all()
        tasks = sorted(tasks, key=lambda t: (t.priority, -t.deadline.timestamp()), reverse=True)

        now_date = datetime.now(UTC).replace(tzinfo=None)

        # Считываем состояние чекбокса (1 — включен, 0 — выключен)
        hide_done = self.check_hide_done.get() == 1

        for task in tasks:
            # 🔥 ДОРАБОТКА: если флажок нажат и задача завершена, просто пропускаем её
            if hide_done and task.status == TaskStatus.DONE:
                continue

            text_color = "#FFFFFF"
            closed_at_str = "-"

            closed_log = session.query(TaskLog).filter(
                TaskLog.task_id == task.id,
                TaskLog.new_status == TaskStatus.DONE
            ).order_by(TaskLog.changed_at.desc()).first()

            if task.status != TaskStatus.DONE:
                if task.deadline < now_date:
                    text_color = "#FF8A8A"
                elif now_date < task.deadline <= (now_date + datetime.min.resolution.__class__(days=1)):
                    text_color = "#FFE082"
            else:
                if closed_log:
                    closed_at_str = closed_log.changed_at.strftime('%Y-%m-%d %H:%M')
                    if closed_log.changed_at < task.deadline:
                        text_color = "#A5D6A7"
                    else:
                        text_color = "#FF8A8A"

            task_frame = ctk.CTkFrame(self.scrollable_frame, height=50)
            task_frame.pack(fill="x", padx=5, pady=3)
            task_frame.pack_propagate(False)

            # --- ID ---
            lbl_id = ctk.CTkLabel(task_frame, text=f"#{task.id}", font=ctk.CTkFont(family="Courier"), width=35,
                                  anchor="w", text_color=text_color)
            lbl_id.pack(side="left", padx=(10, 0), pady=10)
            ctk.CTkFrame(task_frame, width=1, fg_color="#444444").pack(side="left", padx=5, fill="y", pady=4)

            # --- ЗАГОЛОВОК ---
            txt_title = ctk.CTkTextbox(
                task_frame,
                width=165,
                height=42,
                font=ctk.CTkFont(family="Courier", size=13),
                wrap="word",
                fg_color="transparent",
                text_color=text_color,
                activate_scrollbars=False
            )
            txt_title.pack(side="left", pady=4)
            txt_title.insert("1.0", task.title)
            txt_title.configure(state="disabled")
            ctk.CTkFrame(task_frame, width=1, fg_color="#444444").pack(side="left", padx=5, fill="y", pady=4)

            # --- ВЫПАДАЮЩИЙ СПИСОК ИСПОЛНИТЕЛЕЙ ---
            combo_user = ctk.CTkComboBox(
                task_frame,
                values=user_options,
                width=160,
                height=24,
                command=lambda val, t_id=task.id: self.on_user_combobox_change(t_id, val)
            )
            if task.assignee:
                combo_user.set(f"{task.assignee.id}: {task.assignee.fullname[:15]}")
            else:
                combo_user.set("Не назначен")
            combo_user.pack(side="left", pady=13)

            if task.status == TaskStatus.DONE:
                combo_user.configure(state="disabled")

            ctk.CTkFrame(task_frame, width=1, fg_color="#444444").pack(side="left", padx=5, fill="y", pady=4)

            # --- ПРИОРИТЕТ ---
            lbl_priority = ctk.CTkLabel(task_frame, text=task.priority.value, font=ctk.CTkFont(family="Courier"),
                                        width=90, anchor="w", text_color=text_color)
            lbl_priority.pack(side="left", pady=10)
            ctk.CTkFrame(task_frame, width=1, fg_color="#444444").pack(side="left", padx=5, fill="y", pady=4)

            # --- ДЕДЛАЙН ---
            lbl_deadline = ctk.CTkLabel(task_frame, text=task.deadline.strftime('%Y-%m-%d'),
                                        font=ctk.CTkFont(family="Courier"), width=95, anchor="w", text_color=text_color)
            lbl_deadline.pack(side="left", pady=10)
            ctk.CTkFrame(task_frame, width=1, fg_color="#444444").pack(side="left", padx=5, fill="y", pady=4)

            # --- ДАТА ЗАКРЫТИЯ ---
            lbl_closed = ctk.CTkLabel(task_frame, text=closed_at_str, font=ctk.CTkFont(family="Courier"), width=110,
                                      anchor="w", text_color=text_color)
            lbl_closed.pack(side="left", pady=10)
            ctk.CTkFrame(task_frame, width=1, fg_color="#444444").pack(side="left", padx=5, fill="y", pady=4)

            # --- ВЫПАДАЮЩИЙ СПИСОК СТАТУСОВ ---
            allowed_next: List[TaskStatus] = ALLOWED_TRANSITIONS.get(task.status, [])
            combo_values = [task.status.value] + [status.value for status in allowed_next]

            combo_status = ctk.CTkComboBox(
                task_frame,
                values=combo_values,
                width=140,
                height=24,
                command=lambda val, t_id=task.id: self.on_status_combobox_change(t_id, val)
            )
            combo_status.set(task.status.value)
            combo_status.pack(side="right", padx=10, pady=13)

            if task.status == TaskStatus.DONE:
                combo_status.configure(state="disabled")

        session.close()

    def on_user_combobox_change(self, task_id: int, selected_value: str) -> None:
        """Обработчик динамического изменения исполнителя через выпадающий список."""
        session = SessionLocal()
        task = session.get(Task, task_id)
        if not task:
            session.close()
            return

        try:
            if selected_value == "Не назначен":
                if task.status == TaskStatus.IN_PROGRESS:
                    self.show_msg("Ошибка: Нельзя убрать исполнителя у задачи в In Progress!", "red")
                    self.refresh_backlog_view()
                    session.close()
                    return
                task.assignee_id = None
                self.show_msg(f"С задачи #{task_id} снят исполнитель", "green")
            else:
                user_id = int(selected_value.split(":")[0])
                task.assignee_id = user_id
                self.show_msg(f"Задача #{task_id} назначена на пользователя ID: {user_id}", "green")

            session.commit()
        except Exception as e:
            self.show_msg(f"Ошибка смены исполнителя: {e}", "red")
        finally:
            session.close()
            self.refresh_backlog_view()

    def on_status_combobox_change(self, task_id: int, selected_value: str) -> None:
        """Обработчик изменения статуса задачи."""
        session = SessionLocal()
        task = session.get(Task, task_id)
        if not task:
            session.close()
            return

        if task.status.value == selected_value:
            session.close()
            return

        target_status = None
        for status in TaskStatus:
            if status.value == selected_value:
                target_status = status
                break

        if not target_status:
            session.close()
            return

        try:
            if target_status == TaskStatus.IN_PROGRESS and not task.assignee_id:
                first_user = session.query(User).first()
                if not first_user:
                    self.show_msg("Ошибка: Сначала создайте исполнителя!", "red")
                    self.refresh_backlog_view()
                    session.close()
                    return
                task.assignee_id = first_user.id

            old_status = task.status
            task.move_to_status(target_status)

            log = TaskLog(task_id=task.id, old_status=old_status, new_status=target_status)
            session.add(log)
            session.commit()

            self.show_msg(f"Статус задачи #{task_id} изменен на {target_status.value}", "green")
        except TaskTrackerError as b_err:
            self.show_msg(f"Запрещено: {b_err}", "orange")
        except Exception as e:
            self.show_msg(f"Ошибка системы: {e}", "red")
        finally:
            session.close()
            self.refresh_backlog_view()

    def add_user(self) -> None:
        """Обработчик создания нового пользователя в базе данных SQLite."""
        name = self.entry_user_name.get().strip()
        role = self.entry_user_role.get().strip()

        if not name or not role:
            self.show_msg("Ошибка: Заполните ФИО и Роль сотрудника!", "red")
            return

        session = SessionLocal()
        try:
            user = User(fullname=name, role=role)
            session.add(user)
            session.commit()

            self.entry_user_name.delete(0, "end")
            self.entry_user_role.delete(0, "end")
            self.show_msg(f"Сотрудник {name} (ID: {user.id}) добавлен!", "green")
            self.refresh_users_view()
            self.refresh_backlog_view()
        except Exception as e:
            self.show_msg(f"Ошибка БД: {e}", "red")
        finally:
            session.close()

    def add_task(self) -> None:
        """Обработчик добавления новой задачи с привязкой выбранного исполнителя."""
        title = self.entry_task_title.get().strip()
        priority_str = self.combo_priority.get()
        selected_user_str = self.combo_task_assignee.get()
        deadline_str = self.entry_deadline.get().strip()

        if not title or not deadline_str:
            self.show_msg("Ошибка: Заполните поля формы!", "red")
            return

        session = SessionLocal()
        try:
            parsed_deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
            task_priority = TaskPriority(priority_str)

            assignee_id: Optional[int] = None
            if selected_user_str != "Не назначен":
                assignee_id = int(selected_user_str.split(":")[0])

            new_task = Task(
                title=title,
                priority=task_priority,
                deadline=parsed_deadline,
                status=TaskStatus.TO_DO,
                assignee_id=assignee_id
            )
            session.add(new_task)
            session.commit()

            log = TaskLog(task_id=new_task.id, old_status=None, new_status=TaskStatus.TO_DO)
            session.add(log)
            session.commit()

            self.entry_task_title.delete(0, "end")
            self.combo_task_assignee.set("Не назначен")
            self.show_msg(f"Задача #{new_task.id} успешно добавлена!", "green")
            self.refresh_backlog_view()

        except ValueError:
            self.show_msg("Ошибка: Неверный формат даты!", "red")
        except Exception as e:
            self.show_msg(f"Ошибка БД: {e}", "red")
        finally:
            session.close()

    def export_weekly_excel(self) -> None:
        """Экспорт отчета за выбранный год и неделю с ручным указанием имени файла."""
        year_str = self.entry_report_year.get().strip()
        week_str = self.entry_report_week.get().strip()

        if not year_str or not week_str:
            self.show_msg("Ошибка: Укажите Год и Неделю для отчета!", "red")
            return

        try:
            year = int(year_str)
            week = int(week_str)
        except ValueError:
            self.show_msg("Ошибка: Год и Неделя должны быть числами!", "red")
            return

        file_path = filedialog.asksaveasfilename(
            initialfile=f"report_timesheet_{year}_week_{week}.xlsx",
            defaultextension=".xlsx",
            filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")]
        )

        if not file_path:
            return

        session = SessionLocal()
        try:
            generate_weekly_timesheet(session, year=year, week=week, output_path=file_path)
            self.show_msg(f"Отчет за неделю {week} сохранен!", "green")
        except Exception as e:
            self.show_msg(f"Ошибка отчета: {e}", "red")
        finally:
            session.close()

    def export_all_excel(self) -> None:
        """Выгрузка абсолютно всех задач с ручным указанием имени файла."""
        file_path = filedialog.asksaveasfilename(
            initialfile="report_all_tasks_full.xlsx",
            defaultextension=".xlsx",
            filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")]
        )

        if not file_path:
            return

        session = SessionLocal()
        try:
            generate_weekly_timesheet(session, year=0, week=0, output_path=file_path)
            self.show_msg("Полный отчет по всей базе сохранен!", "green")
        except Exception as e:
            self.show_msg(f"Ошибка отчета: {e}", "red")
        finally:
            session.close()


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    app = TaskTrackerGUI()
    app.mainloop()
