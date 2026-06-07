"""Плей-офф: прогноз матчей сетки от 1/16 до финала."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.wc2026 import BRACKET, team_label
from src.db import repo
from src.handlers.callbacks import accessible_message, guard_text_input
from src.handlers.states import Playoff
from src.keyboards.common import (
    awards_start_keyboard,
    score_keyboard,
    winner_keyboard,
)
from src.services import bracket, playoff
from src.services.scores import parse_score, score_error_message

router = Router()

STAGE_BY_NUM: dict[int, str] = {num: stage for stage, num, _h, _a in BRACKET}


def _stage_name(match_number: int) -> str:
    return bracket.STAGE_NAMES[STAGE_BY_NUM[match_number]]


async def send_next_bracket_match(
    message: Message, state: FSMContext, session: AsyncSession, user_id: int
) -> None:
    """Показать следующий матч сетки или финальный итог."""
    await playoff.resolve_bracket(session, user_id)
    await session.commit()

    match = await repo.get_next_bracket_match(session, user_id)
    if match is None:
        await state.clear()
        await message.answer(
            await _final_summary(session, user_id),
            reply_markup=awards_start_keyboard(),
        )
        return

    teams = await repo.get_teams_map(session)
    await state.set_state(Playoff.waiting_score)
    await state.update_data(bm=match.match_number)
    await message.answer(
        f"🏆 <b>{_stage_name(match.match_number)}</b>\n\n"
        f"🆚 <b>{team_label(teams[match.home_team_id])}</b> — "
        f"<b>{team_label(teams[match.away_team_id])}</b>\n\n"
        f"Выбери счёт кнопкой или введи свой (например <code>3:2</code> или <code>4-4</code>)",
        reply_markup=score_keyboard("ps"),
    )


@router.callback_query(F.data == "to_playoff")
async def on_to_playoff(
    call: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    msg = await accessible_message(call)
    if msg is None:
        return
    user = await repo.get_or_create_user(
        session, call.from_user.id, call.from_user.username
    )
    # В плей-офф можно только после полностью заполненного группового этапа.
    if await repo.count_group_predictions(session, user.id) < repo.GROUP_MATCHES_TOTAL:
        await call.answer("Сначала заполните все матчи групп.", show_alert=True)
        return
    await call.answer()
    await msg.answer("🏆 <b>Плей-офф!</b> Заполни сетку до финала.")
    await send_next_bracket_match(msg, state, session, user.id)


async def _apply_bracket_score(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    tg_user,
    home: int,
    away: int,
) -> None:
    """Сохранить счёт матча сетки; при ничьей спросить, кто прошёл."""
    data = await state.get_data()
    match_number = data.get("bm")
    user = await repo.get_or_create_user(session, tg_user.id, tg_user.username)
    pred = await repo.get_bracket_pred(session, user.id, match_number)
    if pred is None:
        await message.answer("Что-то пошло не так, /start.")
        await state.clear()
        return

    teams = await repo.get_teams_map(session)
    if home != away:
        winner_id = pred.home_team_id if home > away else pred.away_team_id
        await repo.set_bracket_result(
            session, user.id, match_number, home, away, winner_id
        )
        await session.commit()
        await send_next_bracket_match(message, state, session, user.id)
        return

    # Ничья — нужен прошедший дальше.
    await state.set_state(Playoff.waiting_winner)
    await state.update_data(bm=match_number, bh=home, ba=away)
    await message.answer(
        f"⚖️ Ничья {home}:{away}. Кто прошёл дальше (серия пенальти)?",
        reply_markup=winner_keyboard(
            teams[pred.home_team_id], teams[pred.away_team_id]
        ),
    )


@router.message(Playoff.waiting_score, F.text)
async def on_bracket_score(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    parsed = parse_score(message.text)
    ok = await guard_text_input(
        message, state, valid=parsed is not None,
        error_message=score_error_message(message.text),
    )
    if not ok:
        return
    home, away = parsed
    await _apply_bracket_score(message, state, session, message.from_user, home, away)


@router.callback_query(Playoff.waiting_score, F.data.startswith("ps:"))
async def on_bracket_score_button(
    call: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    msg = await accessible_message(call)
    if msg is None:
        return
    _, home, away = call.data.split(":")
    await msg.edit_reply_markup(reply_markup=None)
    await call.answer()
    await _apply_bracket_score(msg, state, session, call.from_user, int(home), int(away))


@router.callback_query(Playoff.waiting_score, F.data == "psc")
async def on_bracket_score_custom(call: CallbackQuery) -> None:
    msg = await accessible_message(call)
    if msg is None:
        return
    await call.answer()
    await msg.answer(
        "✍️ Введи счёт текстом, например <code>3:2</code> или <code>4-4</code>"
    )


@router.callback_query(Playoff.waiting_winner, F.data.startswith("bwin:"))
async def on_bracket_winner(
    call: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    msg = await accessible_message(call)
    if msg is None:
        return
    data = await state.get_data()
    match_number, home, away = data.get("bm"), data.get("bh"), data.get("ba")
    user = await repo.get_or_create_user(
        session, call.from_user.id, call.from_user.username
    )
    pred = await repo.get_bracket_pred(session, user.id, match_number)
    if pred is None:
        await call.answer()
        await state.clear()
        return

    side = call.data.split(":")[1]
    winner_id = pred.home_team_id if side == "H" else pred.away_team_id
    await repo.set_bracket_result(session, user.id, match_number, home, away, winner_id)
    await session.commit()
    await call.answer()
    teams = await repo.get_teams_map(session)
    await msg.answer(f"➡️ Прошла команда <b>{teams[winner_id]}</b>")
    await send_next_bracket_match(msg, state, session, user.id)


async def _final_summary(session: AsyncSession, user_id: int) -> str:
    teams = await repo.get_teams_map(session)
    final = await repo.get_bracket_pred(session, user_id, playoff.FINAL_MATCH)
    third = await repo.get_bracket_pred(session, user_id, 103)

    def name(team_id: int | None) -> str:
        return teams.get(team_id, "—") if team_id else "—"

    champion = name(final.winner_team_id if final else None)
    runner_up = "—"
    if final and final.winner_team_id:
        runner_up = name(
            final.away_team_id
            if final.home_team_id == final.winner_team_id
            else final.home_team_id
        )
    third_place = name(third.winner_team_id if third else None)

    return (
        "🎉 <b>Сетка заполнена!</b>\n\n"
        f"🏆 Чемпион мира 2026: <b>{champion}</b>\n"
        f"🥈 Финалист: {runner_up}\n"
        f"🥉 3-е место: {third_place}\n\n"
        "Дальше — индивидуальные награды и символическая сборная (Фаза 4)."
    )
