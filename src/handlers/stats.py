"""Скрытая админская команда /stats: статистика по пользователям бота.

Доступ — только telegram_id из ADMIN_IDS (config). Для остальных команда
молча игнорируется (фоллбэк не сработает, т.к. фильтр Command уже совпал).

  /stats        — сводка: всего юзеров, сколько завершили, список (свежие сверху)
  /stats <id>   — детали одного пользователя (призёры + награды)
"""

from __future__ import annotations

import datetime

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import repo
from src.services.report_data import build_report_data
from src.services.stats import GROUP_MATCHES_TOTAL, collect_stats

router = Router()

OVERVIEW_LIMIT = 30  # сколько пользователей показывать в сводке


def _is_admin(message: Message) -> bool:
    return message.from_user is not None and message.from_user.id in settings.admin_id_set


def _who(username: str | None, telegram_id: int) -> str:
    return f"@{username}" if username else f"id{telegram_id}"


def _fmt_dt(value: object) -> str:
    return value.strftime("%d.%m.%Y %H:%M") if isinstance(value, datetime.datetime) else "—"


@router.message(Command("stats"))
async def cmd_stats(
    message: Message, command: CommandObject, session: AsyncSession
) -> None:
    if not _is_admin(message):
        return  # команда скрытая — для не-админов молчим
    arg = (command.args or "").strip()
    if arg:
        await _send_user_detail(message, session, arg)
    else:
        await _send_overview(message, session)


async def _send_overview(message: Message, session: AsyncSession) -> None:
    stats = await collect_stats(session, limit=OVERVIEW_LIMIT)
    lines = [
        "📊 <b>Статистика бота</b>",
        "",
        f"👥 Всего пользователей: <b>{stats.total_users}</b>",
        f"✅ Завершили прогноз: <b>{stats.completed}</b>",
    ]
    if stats.users:
        lines += ["", "<b>Кто заходил</b> (свежие сверху):"]
        for u in stats.users:
            if u.completed:
                state = f"🏆 {u.champion}"
            else:
                state = f"{u.group_done}/{GROUP_MATCHES_TOTAL} групп"
            lines.append(f"<code>{u.id}</code> {_who(u.username, u.telegram_id)} — {state}")
        shown = len(stats.users)
        if stats.total_users > shown:
            lines.append(f"… и ещё {stats.total_users - shown}")
    lines += ["", "Детали по юзеру: /stats &lt;id&gt;"]
    await message.answer("\n".join(lines))


async def _send_user_detail(message: Message, session: AsyncSession, arg: str) -> None:
    if not arg.isdigit():
        await message.answer("Укажи числовой id пользователя, например: /stats 2")
        return
    user_id = int(arg)
    user = await repo.get_user(session, user_id)
    if user is None:
        await message.answer(f"Пользователь #{user_id} не найден.")
        return

    data = await build_report_data(session, user_id)
    lines = [
        f"📋 <b>{_who(user.username, user.telegram_id)}</b> "
        f"(id {user.id}, tg <code>{user.telegram_id}</code>)",
        f"Зарегистрирован: {_fmt_dt(user.created_at)}",
        "",
        f"🏆 Чемпион: {data.champion}",
        f"🥈 Финалист: {data.runner_up}",
        f"🥉 3-е место: {data.third_place}",
    ]
    if data.awards:
        lines += ["", "<b>Награды:</b>"]
        lines += [f"• {label}: {value}" for label, value in data.awards]
    await message.answer("\n".join(lines))
