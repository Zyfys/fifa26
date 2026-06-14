"""Админ: ввод реальных результатов матчей (источник истины для точности).

Два пути: автопоиск Tavily→Groq с подтверждением и ручной ввод по матчам кнопками.
Плюс дневной фоновый автопоиск, присылающий админу черновик на подтверждение.
Доступ — только ADMIN_IDS (как /stats); для остальных команда молча игнорируется.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from dataclasses import asdict

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import CallbackQuery, Message, User
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.data.wc2026 import team_label
from src.db import repo
from src.db.session import async_session
from src.handlers.callbacks import accessible_message
from src.handlers.states import Results
from src.keyboards.common import (
    results_confirm_keyboard,
    results_entry_keyboard,
    score_keyboard,
)
from src.services.results_ingest import IngestResult, fetch_candidates
from src.services.scores import parse_score, score_error_message

logger = logging.getLogger(__name__)
router = Router()

GROUP_TOTAL = repo.GROUP_MATCHES_TOTAL


def _is_admin(user: User | None) -> bool:
    return user is not None and user.id in settings.admin_id_set


@router.message(Command("results"))
async def cmd_results(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message.from_user):
        return  # скрытая админская команда
    done = await repo.count_actual_results(session)
    await message.answer(
        f"🧮 <b>Реальные результаты</b>\n\nВнесено: <b>{done}/{GROUP_TOTAL}</b>\n\n"
        "Как внести результаты?",
        reply_markup=results_entry_keyboard(with_fetch=settings.autofetch_enabled),
    )


# --- Путь Tavily/Groq: автопоиск → подтверждение ---

@router.callback_query(F.data == "res:fetch")
async def on_res_fetch(
    call: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    if not _is_admin(call.from_user):
        await call.answer()
        return
    msg = await accessible_message(call)
    if msg is None:
        return
    await call.answer("Ищу результаты…")
    ingest = await fetch_candidates(session)
    await _present_draft(call.bot, state, msg.chat.id, ingest)


def _render_draft(ingest: IngestResult) -> str:
    lines = ["🌐 <b>Нашёл результаты</b> (черновик):", "<pre>"]
    for m in ingest.matched:
        lines.append(f"{m.home} {m.home_score}:{m.away_score} {m.away}")
    lines.append("</pre>")
    if ingest.unmatched:
        lines.append("")
        lines.append("⚠️ Не распознал (при необходимости введи вручную):")
        for u in ingest.unmatched:
            p = u.parsed
            lines.append(f"• {p.home} {p.home_score}:{p.away_score} {p.away} — {u.reason}")
    lines.append("")
    lines.append(f"Сохранить {len(ingest.matched)} результат(ов)?")
    return "\n".join(lines)


async def _present_draft(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    ingest: IngestResult,
    *,
    notify_empty: bool = True,
) -> None:
    if not ingest.matched:
        if notify_empty:
            note = ingest.note or "ничего не нашёл. Попробуй вручную: /results"
            await bot.send_message(chat_id, f"🌐 {note}")
        return
    await state.set_state(Results.confirming)
    await state.update_data(draft=[asdict(m) for m in ingest.matched])
    await bot.send_message(
        chat_id, _render_draft(ingest), reply_markup=results_confirm_keyboard()
    )


@router.callback_query(Results.confirming, F.data == "res:save")
async def on_res_save(
    call: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    if not _is_admin(call.from_user):
        await call.answer()
        return
    msg = await accessible_message(call)
    if msg is None:
        return
    data = await state.get_data()
    draft = data.get("draft") or []
    for d in draft:
        await repo.upsert_actual_result(
            session, d["match_number"], d["home_score"], d["away_score"]
        )
    await session.commit()
    await state.clear()
    done = await repo.count_actual_results(session)
    await call.answer("Сохранено")
    await msg.edit_reply_markup(reply_markup=None)
    await msg.answer(f"✅ Сохранено: {len(draft)}. Внесено всего: {done}/{GROUP_TOTAL}.")


@router.callback_query(F.data == "res:cancel")
async def on_res_cancel(call: CallbackQuery, state: FSMContext) -> None:
    msg = await accessible_message(call)
    if msg is None:
        return
    await state.clear()
    await call.answer("Отменено")
    await msg.edit_reply_markup(reply_markup=None)


# --- Путь ручного ввода по матчам ---

@router.callback_query(F.data == "res:manual")
async def on_res_manual(
    call: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    if not _is_admin(call.from_user):
        await call.answer()
        return
    msg = await accessible_message(call)
    if msg is None:
        return
    await call.answer()
    await _send_next_manual(msg, state, session)


async def _send_next_manual(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    matches = await repo.get_unfilled_group_matches(session)
    if not matches:
        await state.clear()
        await message.answer(f"✅ Все {GROUP_TOTAL} матчей внесены.")
        return
    m = matches[0]
    await state.set_state(Results.manual_score)
    await state.update_data(match_number=m.match_number)
    done = await repo.count_actual_results(session)
    await message.answer(
        f"🔢 Реальный счёт · внесено {done}/{GROUP_TOTAL}\n"
        f"Группа {m.group.letter}, матч {m.match_number}\n\n"
        f"🆚 <b>{team_label(m.home_team.name)}</b> — "
        f"<b>{team_label(m.away_team.name)}</b>\n\n"
        "Выбери счёт кнопкой или введи свой (например <code>2:1</code>)",
        reply_markup=score_keyboard("rs"),
    )


async def _save_manual(
    message: Message, state: FSMContext, session: AsyncSession, home: int, away: int
) -> None:
    data = await state.get_data()
    number = data.get("match_number")
    if number is None:
        await state.clear()
        await message.answer("Сбой состояния, начни заново: /results")
        return
    await repo.upsert_actual_result(session, number, home, away)
    await session.commit()
    await _send_next_manual(message, state, session)


@router.callback_query(Results.manual_score, F.data.startswith("rs:"))
async def on_manual_button(
    call: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    if not _is_admin(call.from_user):
        await call.answer()
        return
    msg = await accessible_message(call)
    if msg is None:
        return
    _, home, away = call.data.split(":")
    await msg.edit_reply_markup(reply_markup=None)
    await call.answer()
    await _save_manual(msg, state, session, int(home), int(away))


@router.callback_query(Results.manual_score, F.data == "rsc")
async def on_manual_custom(call: CallbackQuery) -> None:
    msg = await accessible_message(call)
    if msg is None:
        return
    await call.answer()
    await msg.answer("✍️ Введи счёт текстом, например <code>2:1</code>")


@router.message(Results.manual_score, F.text)
async def on_manual_text(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    if not _is_admin(message.from_user):
        return
    parsed = parse_score(message.text)
    if parsed is None:
        await message.answer(score_error_message(message.text))
        return
    home, away = parsed
    await _save_manual(message, state, session, home, away)


# --- Дневной фоновый автопоиск ---

def _seconds_until_hour(hour: int) -> float:
    now = datetime.datetime.now()
    target = now.replace(hour=hour % 24, minute=0, second=0, microsecond=0)
    if target <= now:
        target += datetime.timedelta(days=1)
    return (target - now).total_seconds()


async def autofetch_loop(bot: Bot, dp: Dispatcher) -> None:
    """Раз в сутки ищет результаты и шлёт первому админу черновик на подтверждение."""
    if not settings.autofetch_enabled:
        logger.info("Автопоиск результатов выключен (нет ключей Tavily/Groq или админов).")
        return
    admin_id = sorted(settings.admin_id_set)[0]
    while True:
        await asyncio.sleep(_seconds_until_hour(settings.results_fetch_hour))
        try:
            async with async_session() as session:
                ingest = await fetch_candidates(session)
            key = StorageKey(bot_id=bot.id, chat_id=admin_id, user_id=admin_id)
            state = FSMContext(storage=dp.storage, key=key)
            await _present_draft(bot, state, admin_id, ingest, notify_empty=False)
        except Exception:  # noqa: BLE001 — цикл не должен падать
            logger.exception("Автопоиск результатов: ошибка цикла")
