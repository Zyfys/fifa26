"""Просмотр «Мои прогнозы»: спрогнозированные счета матчей (read-only).

Меню с двумя разделами — групповой этап и плей-офф. Показывает только
собственный прогноз пользователя (без сравнения с реальными результатами).
"""

from __future__ import annotations

from itertools import groupby

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import repo
from src.handlers.callbacks import accessible_message
from src.keyboards.common import my_forecast_menu_keyboard
from src.services.bracket import STAGE_BY_NUM, STAGE_NAMES, STAGE_ORDER

router = Router()

_MENU_TEXT = "📋 <b>Твой прогноз</b>\n\nВыбери раздел:"
_NO_FORECAST = "У тебя ещё нет прогноза. Нажми /start, чтобы начать."
_MAX_LEN = 3800  # запас до лимита Telegram (4096) при склейке блоков


async def show_my_menu(
    message: Message, session: AsyncSession, user_id: int
) -> None:
    """Показать меню разделов прогноза или подсказку, если прогноза ещё нет."""
    if await repo.count_group_predictions(session, user_id) == 0:
        await message.answer(_NO_FORECAST)
        return
    await message.answer(_MENU_TEXT, reply_markup=my_forecast_menu_keyboard())


@router.message(Command("my"))
async def cmd_my(message: Message, session: AsyncSession) -> None:
    user = await repo.get_or_create_user(
        session, message.from_user.id, message.from_user.username
    )
    await session.commit()
    await show_my_menu(message, session, user.id)


@router.callback_query(F.data == "my_open")
async def on_my_open(call: CallbackQuery, session: AsyncSession) -> None:
    msg = await accessible_message(call)
    if msg is None:
        return
    user = await repo.get_or_create_user(
        session, call.from_user.id, call.from_user.username
    )
    await call.answer()
    await show_my_menu(msg, session, user.id)


@router.callback_query(F.data == "myf:groups")
async def on_my_groups(call: CallbackQuery, session: AsyncSession) -> None:
    msg = await accessible_message(call)
    if msg is None:
        return
    user = await repo.get_or_create_user(
        session, call.from_user.id, call.from_user.username
    )
    await call.answer()
    blocks = await _format_group_predictions(session, user.id)
    await _send_blocks(
        msg,
        "⚽ <b>Группы — твой прогноз</b>",
        blocks,
        "Ты ещё не заполнял групповые матчи.",
    )


@router.callback_query(F.data == "myf:playoff")
async def on_my_playoff(call: CallbackQuery, session: AsyncSession) -> None:
    msg = await accessible_message(call)
    if msg is None:
        return
    user = await repo.get_or_create_user(
        session, call.from_user.id, call.from_user.username
    )
    await call.answer()
    blocks = await _format_playoff_predictions(session, user.id)
    await _send_blocks(
        msg,
        "🏆 <b>Плей-офф — твой прогноз</b>",
        blocks,
        "Плей-офф ещё не заполнен.",
    )


# --- Форматирование ---

async def _format_group_predictions(
    session: AsyncSession, user_id: int
) -> list[str]:
    """`<pre>`-блоки спрогнозированных счётов по группам (по одному на группу)."""
    rows = await repo.get_group_predictions(session, user_id)
    blocks: list[str] = []
    for letter, items in groupby(rows, key=lambda r: r[0]):
        lines = [f"{home} {hs}:{as_} {away}" for _l, home, away, hs, as_ in items]
        blocks.append(
            f"<b>Группа {letter}</b>\n<pre>\n" + "\n".join(lines) + "\n</pre>"
        )
    return blocks


async def _format_playoff_predictions(
    session: AsyncSession, user_id: int
) -> list[str]:
    """`<pre>`-блоки прогнозов плей-офф по раундам.

    Счёт показывает победителя сам по себе; при ничьей (серия пенальти)
    добавляется пометка «(пен. ✅ <команда>)». Матчи без счёта помечаются.
    """
    preds = await repo.get_bracket_preds(session, user_id)
    teams = await repo.get_teams_map(session)
    blocks: list[str] = []
    for stage in STAGE_ORDER:
        lines: list[str] = []
        for num in sorted(n for n in preds if STAGE_BY_NUM.get(n) == stage):
            p = preds[num]
            if p.home_team_id is None or p.away_team_id is None:
                continue  # участники ещё не определены
            home = teams.get(p.home_team_id, "—")
            away = teams.get(p.away_team_id, "—")
            if p.home_score is None or p.away_score is None:
                lines.append(f"{home} — {away} (не заполнено)")
                continue
            line = f"{home} {p.home_score}:{p.away_score} {away}"
            if p.home_score == p.away_score and p.winner_team_id:
                line += f" (пен. ✅ {teams.get(p.winner_team_id, '—')})"
            lines.append(line)
        if lines:
            blocks.append(
                f"<b>{STAGE_NAMES[stage]}</b>\n<pre>\n" + "\n".join(lines) + "\n</pre>"
            )
    return blocks


async def _send_blocks(
    message: Message, header: str, blocks: list[str], empty: str
) -> None:
    """Отправить блоки, склеивая их и разбивая на несколько сообщений по лимиту."""
    if not blocks:
        await message.answer(f"{header}\n\n{empty}")
        return
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for block in blocks:
        if current and length + len(block) + 2 > _MAX_LEN:
            chunks.append("\n\n".join(current))
            current, length = [], 0
        current.append(block)
        length += len(block) + 2
    if current:
        chunks.append("\n\n".join(current))
    for i, chunk in enumerate(chunks):
        await message.answer(f"{header}\n\n{chunk}" if i == 0 else chunk)
