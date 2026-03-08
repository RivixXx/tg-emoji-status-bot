"""
Karina AI: Task Commands
Команды бота для управления задачами, проектами и спринтами
"""
import logging
from datetime import datetime, timezone, timedelta
from telethon import events, Button
from typing import Optional

from brains.tasks import (
    create_task, get_task, get_user_tasks, update_task, complete_task, delete_task,
    get_overdue_tasks, get_tasks_by_due_date, get_productivity_stats,
    start_work_on_task, TaskStatus, TaskPriority, format_task_for_display
)
from brains.projects import (
    create_project, get_project, get_user_projects, update_project,
    archive_project, complete_project, get_project_stats, get_active_projects,
    ProjectStatus, ProjectPriority, format_project_for_display
)
from brains.sprints import (
    create_sprint, get_sprint, get_user_sprints, start_sprint, complete_sprint,
    add_task_to_sprint, get_sprint_tasks, get_sprint_stats, get_active_sprint,
    get_daily_goals, create_daily_goals, update_daily_goal_completion, set_evening_review,
    SprintStatus
)

logger = logging.getLogger(__name__)


# ============================================================================
# РЕГИСТРАЦИЯ КОМАНД
# ============================================================================

def register_task_commands(bot, my_id: int):
    """Регистрирует все команды для управления задачами"""

    # ------------------------------------------------------------------------
    # /tasks - Список задач
    # ------------------------------------------------------------------------
    @bot.on(events.NewMessage(pattern='/tasks', chats=my_id))
    async def cmd_tasks(event):
        """Показывает список задач"""
        args = event.text.split()
        status_filter = None
        show_completed = False

        # Парсим аргументы
        if len(args) > 1:
            arg = args[1].lower()
            if arg == 'all':
                show_completed = True
            elif arg == 'todo':
                status_filter = TaskStatus.TODO
            elif arg == 'in_progress':
                status_filter = TaskStatus.IN_PROGRESS
            elif arg == 'done':
                status_filter = TaskStatus.DONE

        user_id = my_id
        tasks = await get_user_tasks(
            user_id,
            status=status_filter,
            limit=20,
            include_completed=show_completed
        )

        if not tasks:
            await event.respond("📋 У тебя нет задач!\n\nДобавь первую: `/task create <название>`")
            return

        # Формируем сообщение
        status_groups = {}
        for task in tasks:
            if task.status not in status_groups:
                status_groups[task.status] = []
            status_groups[task.status].append(task)

        message = "📋 **Мои задачи**\n\n"

        status_names = {
            TaskStatus.TODO: "⏳ К выполнению",
            TaskStatus.IN_PROGRESS: "🔄 В работе",
            TaskStatus.REVIEW: "👀 На проверке",
            TaskStatus.DONE: "✅ Выполнено",
        }

        for status, status_tasks in status_groups.items():
            if len(status_tasks) <= 5:  # Показываем только если не много
                message += f"\n{status_names.get(status, '📝')} ({len(status_tasks)}):\n"
                for task in status_tasks[:5]:
                    due = ""
                    if task.due_date:
                        if task.is_overdue():
                            due = " 🔴"
                        else:
                            due = f" 📅{task.due_date.strftime('%d.%m')}"
                    message += f"  • {task.title}{due}\n"

        if len(tasks) > 10:
            message += f"\n_...и ещё {len(tasks) - 10} задач_"

        message += "\n\nℹ️ Управление: `/task create`, `/task done <id>`, `/tasks done`"

        await event.respond(message)

    # ------------------------------------------------------------------------
    # /task - Управление конкретной задачей
    # ------------------------------------------------------------------------
    @bot.on(events.NewMessage(pattern=r'/task(\s+.*)?', chats=my_id))
    async def cmd_task(event):
        """Управление задачей"""
        text = event.text
        args = text.split(maxsplit=2)

        if len(args) < 2:
            await event.respond("""
📝 **Команды для задач:**

`/task create <название>` — Создать задачу
`/task <id>` — Показать задачу
`/task done <id>` — Завершить задачу
`/task start <id>` — Начать выполнение
`/task edit <id> <новое название>` — Редактировать
`/task delete <id>` — Удалить задачу
`/task add <id> <проект_id>` — Добавить в проект

**Фильтры:**
`/tasks` — Все активные
`/tasks todo` — К выполнению
`/tasks in_progress` — В работе
`/tasks done` — Выполненные
`/tasks all` — Все включая выполненные
""")
            return

        command = args[1]
        user_id = my_id

        # Создание задачи
        if command == 'create':
            if len(args) < 3:
                await event.respond("❌ Укажи название задачи: `/task create <название>`")
                return

            title = args[2]
            task = await create_task(user_id, title)

            if task:
                await event.respond(
                    f"✅ **Задача создана**\n\n{format_task_for_display(task)}",
                    buttons=[[Button.inline("🔄 Начать", b=f"task_start_{task.id}")]]
                )
            else:
                await event.respond("❌ Не удалось создать задачу")
            return

        # Просмотр задачи
        if command.isdigit():
            task_id = int(command)
            task = await get_task(task_id, user_id)

            if not task:
                await event.respond("❌ Задача не найдена")
                return

            message = format_task_for_display(task, show_description=True)

            # Добавляем статистику проекта если есть
            if task.project_id:
                try:
                    project_stats = await get_project_stats(task.project_id, user_id)
                    message += f"\n\n📊 **Прогресс проекта:** {project_stats.get('completion_percent', 0)}%"
                except:
                    pass

            buttons = [
                [Button.inline("🔄 Начать", b=f"task_start_{task.id}")] if task.status == TaskStatus.TODO else [],
                [Button.inline("✅ Завершить", b=f"task_done_{task.id}")] if task.status != TaskStatus.DONE else [],
                [Button.inline("🗑 Удалить", b=f"task_delete_{task.id}")],
            ]
            buttons = [b for b in buttons if b]  # Убираем пустые

            await event.respond(message, buttons=buttons if buttons else None)
            return

        # Завершить задачу
        if command == 'done':
            if len(args) < 3 or not args[2].isdigit():
                await event.respond("❌ Укажи ID: `/task done <id>`")
                return

            task_id = int(args[2])
            task = await complete_task(task_id, user_id)

            if task:
                await event.respond(f"✅ **Задача завершена!**\n\n{task.title}")
            else:
                await event.respond("❌ Не удалось завершить задачу")
            return

        # Начать задачу
        if command == 'start':
            if len(args) < 3 or not args[2].isdigit():
                await event.respond("❌ Укажи ID: `/task start <id>`")
                return

            task_id = int(args[2])
            task = await start_work_on_task(task_id, user_id)

            if task:
                await event.respond(f"🔄 **Начал работу над задачей:** {task.title}")
            else:
                await event.respond("❌ Не удалось начать задачу")
            return

        # Удалить задачу
        if command == 'delete':
            if len(args) < 3 or not args[2].isdigit():
                await event.respond("❌ Укажи ID: `/task delete <id>`")
                return

            task_id = int(args[2])
            success = await delete_task(task_id, user_id)

            if success:
                await event.respond("🗑️ **Задача удалена**")
            else:
                await event.respond("❌ Не удалось удалить задачу")
            return

        # Редактировать задачу
        if command == 'edit':
            if len(args) < 4:
                await event.respond("❌ Использование: `/task edit <id> <новое название>`")
                return

            task_id = int(args[2])
            new_title = args[3]

            task = await update_task(task_id, user_id, {"title": new_title})

            if task:
                await event.respond(f"✅ **Задача обновлена:** {task.title}")
            else:
                await event.respond("❌ Не удалось обновить задачу")
            return

        await event.respond("❌ Неизвестная команда. Используйте `/task` для справки")

    # ------------------------------------------------------------------------
    # /projects - Список проектов
    # ------------------------------------------------------------------------
    @bot.on(events.NewMessage(pattern='/projects', chats=my_id))
    async def cmd_projects(event):
        """Показывает список проектов"""
        user_id = my_id
        projects = await get_user_projects(user_id, limit=20)

        if not projects:
            await event.respond("📁 У тебя нет проектов!\n\nСоздай первый: `/project create <название>`")
            return

        message = "📁 **Мои проекты**\n\n"

        for project in projects[:10]:
            message += format_project_for_display(project) + "\n\n"

        if len(projects) > 10:
            message += f"_...и ещё {len(projects) - 10} проектов_"

        message += "\n\nℹ️ Управление: `/project create`, `/project <id>`"

        await event.respond(message)

    # ------------------------------------------------------------------------
    # /project - Управление проектом
    # ------------------------------------------------------------------------
    @bot.on(events.NewMessage(pattern=r'/project(\s+.*)?', chats=my_id))
    async def cmd_project(event):
        """Управление проектом"""
        text = event.text
        args = text.split(maxsplit=2)

        if len(args) < 2:
            await event.respond("""
📁 **Команды для проектов:**

`/project create <название>` — Создать проект
`/project <id>` — Показать проект
`/project archive <id>` — Архивировать
`/project complete <id>` — Завершить
`/project delete <id>` — Удалить
""")
            return

        command = args[1]
        user_id = my_id

        # Создание проекта
        if command == 'create':
            if len(args) < 3:
                await event.respond("❌ Укажи название: `/project create <название>`")
                return

            title = args[2]
            project = await create_project(user_id, title)

            if project:
                await event.respond(
                    f"✅ **Проект создан**\n\n{format_project_for_display(project)}",
                    buttons=[[Button.inline("➕ Добавить задачу", b=f"project_add_task_{project.id}")]]
                )
            else:
                await event.respond("❌ Не удалось создать проект")
            return

        # Просмотр проекта
        if command.isdigit():
            project_id = int(command)
            project = await get_project(project_id, user_id)

            if not project:
                await event.respond("❌ Проект не найден")
                return

            message = format_project_for_display(project, show_stats=True)

            # Статистика
            stats = await get_project_stats(project_id, user_id)
            message += f"\n\n📊 **Статистика:**\n"
            message += f"• Задач: {stats.get('total_tasks', 0)}\n"
            message += f"• Выполнено: {stats.get('completed_tasks', 0)}\n"
            message += f"• Прогресс: {stats.get('completion_percent', 0)}%"

            buttons = [
                [Button.inline("✅ Завершить", b=f"project_complete_{project.id}")],
                [Button.inline("🗄️ Архивировать", b=f"project_archive_{project.id}")],
            ]

            await event.respond(message, buttons=buttons)
            return

        # Архивировать
        if command == 'archive':
            if len(args) < 3 or not args[2].isdigit():
                await event.respond("❌ Укажи ID: `/project archive <id>`")
                return

            project_id = int(args[2])
            project = await archive_project(project_id, user_id)

            if project:
                await event.respond(f"🗄️ **Проект архивирован:** {project.name}")
            else:
                await event.respond("❌ Не удалось архивировать проект")
            return

        # Завершить
        if command == 'complete':
            if len(args) < 3 or not args[2].isdigit():
                await event.respond("❌ Укажи ID: `/project complete <id>`")
                return

            project_id = int(args[2])
            project = await complete_project(project_id, user_id)

            if project:
                await event.respond(f"✅ **Проект завершён:** {project.name}")
            else:
                await event.respond("❌ Не удалось завершить проект")
            return

        # Удалить
        if command == 'delete':
            if len(args) < 3 or not args[2].isdigit():
                await event.respond("❌ Укажи ID: `/project delete <id>`")
                return

            project_id = int(args[2])
            success = await delete_project(project_id, user_id)

            if success:
                await event.respond("🗑️ **Проект удалён**")
            else:
                await event.respond("❌ Не удалось удалить проект")
            return

        await event.respond("❌ Неизвестная команда. Используйте `/project` для справки")

    # ------------------------------------------------------------------------
    # /sprints - Список спринтов
    # ------------------------------------------------------------------------
    @bot.on(events.NewMessage(pattern='/sprints', chats=my_id))
    async def cmd_sprints(event):
        """Показывает список спринтов"""
        user_id = my_id
        sprints = await get_user_sprints(user_id, limit=10)

        if not sprints:
            await event.respond("🏃 У тебя нет спринтов!\n\nСоздай первый: `/sprint create <название>`")
            return

        message = "🏃 **Мои спринты**\n\n"

        for sprint in sprints:
            status_emoji = {"planning": "📋", "active": "🏃", "completed": "✅", "archived": "🗄️"}
            emoji = status_emoji.get(sprint.status.value, "📋")

            days_left = sprint.days_remaining()
            message += f"{emoji} **{sprint.name}**\n"
            message += f"📅 {sprint.start_date} — {sprint.end_date}"
            if days_left > 0:
                message += f" (осталось {days_left} дн.)"
            message += f"\n🎯 {sprint.goal[:100] if sprint.goal else 'Без цели'}\n\n"

        message += "\nℹ️ Управление: `/sprint create`, `/sprint <id>`"

        await event.respond(message)

    # ------------------------------------------------------------------------
    # /sprint - Управление спринтом
    # ------------------------------------------------------------------------
    @bot.on(events.NewMessage(pattern=r'/sprint(\s+.*)?', chats=my_id))
    async def cmd_sprint(event):
        """Управление спринтом"""
        text = event.text
        args = text.split(maxsplit=2)

        if len(args) < 2:
            await event.respond("""
🏃 **Команды для спринтов:**

`/sprint create <название>` — Создать спринт (14 дней)
`/sprint <id>` — Показать спринт
`/sprint start <id>` — Начать спринт
`/sprint complete <id>` — Завершить спринт
`/sprint add <task_id>` — Добавить задачу
""")
            return

        command = args[1]
        user_id = my_id

        # Создание спринта
        if command == 'create':
            name = args[2] if len(args) > 2 else f"Спринт {datetime.now().strftime('%Y-%m')}"
            start = date.today()
            end = start + timedelta(days=14)

            sprint = await create_sprint(user_id, name, start, end, goal="")

            if sprint:
                await event.respond(
                    f"✅ **Спринт создан**\n\n🏃 {sprint.name}\n📅 {start} — {end} (14 дней)",
                    buttons=[[Button.inline("▶️ Начать", b=f"sprint_start_{sprint.id}")]]
                )
            else:
                await event.respond("❌ Не удалось создать спринт")
            return

        # Начало спринта
        if command == 'start':
            if len(args) < 3 or not args[2].isdigit():
                await event.respond("❌ Укажи ID: `/sprint start <id>`")
                return

            sprint_id = int(args[2])
            sprint = await start_sprint(sprint_id, user_id)

            if sprint:
                await event.respond(f"🏃 **Спринт начался:** {sprint.name}")
            else:
                await event.respond("❌ Не удалось начать спринт")
            return

        # Завершение спринта
        if command == 'complete':
            if len(args) < 3 or not args[2].isdigit():
                await event.respond("❌ Укажи ID: `/sprint complete <id>`")
                return

            sprint_id = int(args[2])
            sprint = await complete_sprint(sprint_id, user_id)

            if sprint:
                await event.respond(f"✅ **Спринт завершён:** {sprint.name}")
            else:
                await event.respond("❌ Не удалось завершить спринт")
            return

        await event.respond("❌ Неизвестная команда. Используйте `/sprint` для справки")

    # ------------------------------------------------------------------------
    # /goals - Ежедневные цели
    # ------------------------------------------------------------------------
    @bot.on(events.NewMessage(pattern='/goals', chats=my_id))
    async def cmd_goals(event):
        """Показывает цели на сегодня"""
        user_id = my_id
        from datetime import date
        
        daily = await get_daily_goals(user_id, date.today())

        if not daily or not daily.goals:
            await event.respond("""
🎯 **Цели на сегодня**

У тебя пока нет целей на сегодня!

Добавь: `/goal add <цель>`
Или создай сразу несколько: `/goals plan <цель1>, <цель2>, ...`
""")
            return

        message = "🎯 **Цели на сегодня**\n\n"

        for i, (goal, completed) in enumerate(zip(daily.goals, daily.completed), 1):
            checkbox = "✅" if completed else "⬜"
            message += f"{checkbox} **{i}.** {goal}\n"

        message += f"\n📊 Выполнение: {daily.completion_percent()}%"

        buttons = []
        for i in range(len(daily.goals)):
            if not daily.completed[i]:
                buttons.append([Button.inline(f"✅ Цель {i+1}", b=f"goal_complete_{i}")])

        if buttons:
            buttons.append([Button.inline("📝 Вечерний обзор", b"evening_review")])

        await event.respond(message, buttons=buttons if buttons else None)

    # ------------------------------------------------------------------------
    # /goal - Управление целями
    # ------------------------------------------------------------------------
    @bot.on(events.NewMessage(pattern=r'/goal(\s+.*)?', chats=my_id))
    async def cmd_goal(event):
        """Управление ежедневными целями"""
        text = event.text
        args = text.split(maxsplit=2)

        if len(args) < 2:
            await event.respond("""
🎯 **Команды для целей:**

`/goal add <цель>` — Добавить цель
`/goal done <номер>` — Отметить выполненной
`/goals` — Показать цели на сегодня
`/goals plan <ц1>, <ц2>` — Запланировать несколько
""")
            return

        command = args[1]
        user_id = my_id
        from datetime import date

        # Добавить цель
        if command == 'add':
            if len(args) < 3:
                await event.respond("❌ Укажи цель: `/goal add <цель>`")
                return

            goal_text = args[2]
            daily = await get_daily_goals(user_id, date.today())

            if not daily:
                daily = await create_daily_goals(user_id, [goal_text], date.today())
            else:
                if len(daily.goals) >= 10:
                    await event.respond("❌ Максимум 10 целей в день")
                    return
                daily.goals.append(goal_text)
                daily.completed.append(False)
                # Обновляем через БД
                await create_daily_goals(user_id, daily.goals, date.today())

            await event.respond(f"✅ **Цель добавлена:** {goal_text}")
            return

        # Отметить выполненной
        if command == 'done':
            if len(args) < 3 or not args[2].isdigit():
                await event.respond("❌ Укажи номер: `/goal done <номер>`")
                return

            goal_num = int(args[2]) - 1
            daily = await get_daily_goals(user_id, date.today())

            if not daily:
                await event.respond("❌ Нет целей на сегодня")
                return

            if goal_num < 0 or goal_num >= len(daily.completed):
                await event.respond("❌ Неверный номер цели")
                return

            await update_daily_goal_completion(user_id, goal_num, True, date.today())
            await event.respond(f"✅ **Цель выполнена:** {daily.goals[goal_num]}")
            return

        await event.respond("❌ Неизвестная команда")

    # ------------------------------------------------------------------------
    # /stats - Статистика продуктивности
    # ------------------------------------------------------------------------
    @bot.on(events.NewMessage(pattern='/stats', chats=my_id))
    async def cmd_stats(event):
        """Показывает статистику продуктивности"""
        user_id = my_id
        stats = await get_productivity_stats(user_id, days=7)

        if not stats:
            await event.respond("❌ Не удалось получить статистику")
            return

        message = "📊 **Продуктивность (7 дней)**\n\n"
        message += f"📋 Задач всего: {stats.get('total_tasks', 0)}\n"
        message += f"✅ Выполнено: {stats.get('completed_tasks', 0)}\n"
        message += f"🔄 В работе: {stats.get('in_progress_tasks', 0)}\n"
        message += f"🔴 Просрочено: {stats.get('overdue_tasks', 0)}\n"
        message += f"\n📈 Процент выполнения: {stats.get('completion_rate', 0)}%"

        # Активные проекты
        active_projects = await get_active_projects(user_id)
        message += f"\n\n📁 Активных проектов: {len(active_projects)}"

        # Активный спринт
        active_sprint = await get_active_sprint(user_id)
        if active_sprint:
            days_left = active_sprint.days_remaining()
            message += f"\n🏃 Активный спринт: {active_sprint.name} (осталось {days_left} дн.)"

        await event.respond(message)

    logger.info("✅ Task commands registered")


# Импортируем date для команд
from datetime import date
