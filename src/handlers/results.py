"""Реальные результаты матчей (источник истины для точности прогнозов).

Автоматика:
  • вечером — фоновый автопоиск Tavily→Groq, СРАЗУ пишет распознанные результаты;
  • утром — рассылка каждому игроку сводки «его прогноз vs реальный счёт».
Админ (ADMIN_IDS):
  • /results — найти и записать сейчас (то же, но по кнопке) или ввести/исправить вручную.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.data.wc2026 import team_label
from src.db import repo
from src.db.session import async_session
from src.handlers.callbacks import accessible_message
from src.handlers.states import Results
from src.keyboards.common import (
    results_entry_keyboard,
    results_reset_confirm_keyboard,
    score_keyboard,
)
from src.services.digest import send_daily_digests
from src.services.results_ingest import IngestResult, auto_ingest
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
        "Внеси счёт вручную:",
        reply_markup=results_entry_keyboard(
            with_fetch=settings.autofetch_enabled and settings.results_auto,
            with_reset=done > 0,
        ),
    )


def _render_ingest_report(ingest: IngestResult) -> str:
    if not ingest.matched and not ingest.unmatched:
        return f"🌐 {ingest.note or 'ничего не нашёл.'}"
    lines: list[str] = []
    if ingest.matched:
        lines.append(f"✅ <b>Записал {len(ingest.matched)}:</b>")
        lines += [f"{m.home} {m.home_score}:{m.away_score} {m.away}" for m in ingest.matched]
    if ingest.unmatched:
        lines.append("")
        lines.append("⚠️ Не распознал (внеси вручную: /results):")
        for u in ingest.unmatched:
            p = u.parsed
            lines.append(f"• {p.home} {p.home_score}:{p.away_score} {p.away} — {u.reason}")
    return "\n".join(lines)


@router.callback_query(F.data == "res:fetch")
async def on_res_fetch(call: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(call.from_user):
        await call.answer()
        return
    msg = await accessible_message(call)
    if msg is None:
        return
    await call.answer("Ищу и записываю…")
    ingest = await auto_ingest(session)
    await msg.answer(_render_ingest_report(ingest))


# --- Сброс всех результатов ---

@router.callback_query(F.data == "res:reset")
async def on_res_reset(call: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(call.from_user):
        await call.answer()
        return
    msg = await accessible_message(call)
    if msg is None:
        return
    done = await repo.count_actual_results(session)
    await call.answer()
    await msg.answer(
        f"⚠️ Удалить все внесённые результаты ({done})? Это сбросит точность и рейтинг.",
        reply_markup=results_reset_confirm_keyboard(),
    )


@router.callback_query(F.data == "res:reset_yes")
async def on_res_reset_yes(call: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(call.from_user):
        await call.answer()
        return
    msg = await accessible_message(call)
    if msg is None:
        return
    deleted = await repo.clear_actual_results(session)
    await session.commit()
    await call.answer("Сброшено")
    await msg.edit_text(f"🗑 Удалено результатов: {deleted}. Внесено 0/{GROUP_TOTAL}.")


@router.callback_query(F.data == "res:reset_no")
async def on_res_reset_no(call: CallbackQuery) -> None:
    msg = await accessible_message(call)
    if msg is None:
        return
    await call.answer()
    await msg.edit_text("Отменено — результаты целы.")


# --- Ручной ввод/исправление по матчам ---

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


# --- Дневные фоновые задачи ---

def _seconds_until_hour(hour: int) -> float:
    """Секунд до ближайшего наступления `hour:00` в зоне settings.schedule_tz."""
    try:
        now = datetime.datetime.now(ZoneInfo(settings.schedule_tz))
    except ZoneInfoNotFoundError:
        now = datetime.datetime.now()
    target = now.replace(hour=hour % 24, minute=0, second=0, microsecond=0)
    if target <= now:
        target += datetime.timedelta(days=1)
    return (target - now).total_seconds()


async def ingest_loop(bot: Bot) -> None:
    """Вечером: автопоиск результатов и автозапись. Шлёт админу краткий отчёт."""
    if not (settings.autofetch_enabled and settings.results_auto):
        logger.info("Авто-запись результатов выключена (RESULTS_AUTO=false или нет ключей).")
        return
    admin_id = sorted(settings.admin_id_set)[0]
    while True:
        await asyncio.sleep(_seconds_until_hour(settings.results_fetch_hour))
        try:
            async with async_session() as session:
                ingest = await auto_ingest(session)
            if ingest.matched or ingest.unmatched:
                try:
                    await bot.send_message(admin_id, _render_ingest_report(ingest))
                except TelegramAPIError:
                    logger.warning("Не доставил отчёт автозаписи админу")
        except Exception:  # noqa: BLE001 — цикл не должен падать
            logger.exception("Автозапись результатов: ошибка цикла")


async def digest_loop(bot: Bot) -> None:
    """Утром: рассылка каждому игроку его сводки по новым результатам."""
    if not settings.results_auto:
        logger.info("Утренняя рассылка выключена (RESULTS_AUTO=false).")
        return
    while True:
        await asyncio.sleep(_seconds_until_hour(settings.digest_hour))
        try:
            async with async_session() as session:
                sent = await send_daily_digests(bot, session)
            if sent:
                logger.info("Утренняя сводка отправлена: %s игрокам", sent)
        except Exception:  # noqa: BLE001 — цикл не должен падать
            logger.exception("Утренняя сводка: ошибка цикла")
