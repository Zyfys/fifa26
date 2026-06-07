"""Фаза 4: индивидуальные награды и символическая сборная 4-3-3."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import repo
from src.handlers.callbacks import accessible_message, guard_text_input
from src.handlers.states import Awards
from src.keyboards.common import (
    pdf_keyboard,
    player_picker_keyboard,
    team_picker_keyboard,
)
from src.services import playoff
from src.services.awards import (
    AWARD_DISPLAY,
    POSITION_LABEL,
    YOUNG_BORN_AFTER,
    Step,
    build_steps,
    steps_by_id,
)

router = Router()

MAX_GOALS = 30


async def _first_incomplete_step(session: AsyncSession, user_id: int) -> Step | None:
    awards = set(await repo.get_awards_map(session, user_id))
    tot_slots = await repo.get_tot_slots(session, user_id)
    for step in build_steps():
        if step.kind == "tot":
            done = (step.position, step.tot_slot) in tot_slots
        else:
            done = step.award_type in awards
        if not done:
            return step
    return None


async def _players_for_step(
    session: AsyncSession, user_id: int, step: Step, team_id: int
) -> list[tuple[int, str]]:
    players = await repo.list_players(
        session,
        team_id,
        position=step.position,
        born_after=YOUNG_BORN_AFTER if step.young else None,
    )
    if step.kind == "tot":
        used = await repo.get_tot_player_ids(session, user_id)
        players = [(pid, name) for pid, name in players if pid not in used]
    return players


async def send_next_step(
    message: Message, state: FSMContext, session: AsyncSession, user_id: int
) -> None:
    step = await _first_incomplete_step(session, user_id)
    if step is None:
        await state.clear()
        await message.answer(
            await render_awards_summary(session, user_id),
            reply_markup=pdf_keyboard(),
        )
        return

    teams = await repo.list_teams(session)
    await state.set_state(Awards.choosing_team)
    await state.update_data(step=step.id)
    hint = "Выбери команду:" if step.kind == "team" else "Выбери команду игрока:"
    await message.answer(
        f"<b>{step.title}</b>\n\n{hint}",
        reply_markup=team_picker_keyboard(teams),
    )


@router.callback_query(F.data == "to_awards")
async def on_to_awards(
    call: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    msg = await accessible_message(call)
    if msg is None:
        return
    user = await repo.get_or_create_user(
        session, call.from_user.id, call.from_user.username
    )
    if await playoff.get_champion_id(session, user.id) is None:
        await call.answer("Сначала заполни сетку плей-офф до финала.", show_alert=True)
        return
    await call.answer()
    await msg.answer("🎖 <b>Награды и символическая сборная</b>")
    await send_next_step(msg, state, session, user.id)


@router.callback_query(F.data == "noop")
async def on_noop(call: CallbackQuery) -> None:
    await call.answer()


# --- Выбор команды ---

@router.callback_query(Awards.choosing_team, F.data.startswith("pg:"))
async def on_team_page(call: CallbackQuery, session: AsyncSession) -> None:
    msg = await accessible_message(call)
    if msg is None:
        return
    page = int(call.data.split(":")[1])
    teams = await repo.list_teams(session)
    await msg.edit_reply_markup(reply_markup=team_picker_keyboard(teams, page))
    await call.answer()


@router.callback_query(Awards.choosing_team, F.data.startswith("tm:"))
async def on_team_pick(
    call: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    msg = await accessible_message(call)
    if msg is None:
        return
    team_id = int(call.data.split(":")[1])
    step = steps_by_id()[(await state.get_data())["step"]]
    user = await repo.get_or_create_user(
        session, call.from_user.id, call.from_user.username
    )
    teams = await repo.get_teams_map(session)

    if step.kind == "team":
        await repo.upsert_award(session, user.id, step.award_type, team_id=team_id)
        await session.commit()
        await call.answer()
        await msg.edit_text(f"{step.title}\n✅ {teams[team_id]}")
        await send_next_step(msg, state, session, user.id)
        return

    players = await _players_for_step(session, user.id, step, team_id)
    if not players:
        await call.answer(
            "В этой команде нет подходящих игроков — выбери другую.", show_alert=True
        )
        return
    await state.set_state(Awards.choosing_player)
    await state.update_data(step=step.id, team=team_id)
    await call.answer()
    await msg.edit_text(
        f"<b>{step.title}</b>\nКоманда: {teams[team_id]}. Теперь выбери игрока:",
        reply_markup=player_picker_keyboard(players),
    )


# --- Выбор игрока ---

@router.callback_query(Awards.choosing_player, F.data.startswith("ppg:"))
async def on_player_page(
    call: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    msg = await accessible_message(call)
    if msg is None:
        return
    page = int(call.data.split(":")[1])
    data = await state.get_data()
    step = steps_by_id()[data["step"]]
    user = await repo.get_or_create_user(
        session, call.from_user.id, call.from_user.username
    )
    players = await _players_for_step(session, user.id, step, data["team"])
    await msg.edit_reply_markup(reply_markup=player_picker_keyboard(players, page))
    await call.answer()


@router.callback_query(Awards.choosing_player, F.data.startswith("pl:"))
async def on_player_pick(
    call: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    msg = await accessible_message(call)
    if msg is None:
        return
    player_id = int(call.data.split(":")[1])
    step = steps_by_id()[(await state.get_data())["step"]]
    user = await repo.get_or_create_user(
        session, call.from_user.id, call.from_user.username
    )
    name = await repo.get_player_name(session, player_id) or "—"

    if step.kind == "player":
        await repo.upsert_award(session, user.id, step.award_type, player_id=player_id)
        await session.commit()
        await call.answer()
        await msg.edit_text(f"{step.title}\n✅ {name}")
        await send_next_step(msg, state, session, user.id)
        return

    if step.kind == "player_goals":
        await repo.upsert_award(session, user.id, step.award_type, player_id=player_id)
        await session.commit()
        await state.set_state(Awards.waiting_goals)
        await state.update_data(step=step.id, player=player_id)
        await call.answer()
        await msg.edit_text(
            f"{step.title}\n✅ {name}\n\nСколько голов он забьёт? Введите число:"
        )
        return

    # ToT
    await repo.upsert_tot_pick(
        session, user.id, step.position, step.tot_slot, player_id
    )
    await session.commit()
    await call.answer()
    await msg.edit_text(f"{step.title}\n✅ {name}")
    await send_next_step(msg, state, session, user.id)


@router.message(Awards.waiting_goals, F.text)
async def on_goals(message: Message, state: FSMContext, session: AsyncSession) -> None:
    text = (message.text or "").strip()
    valid = text.isdigit() and int(text) <= MAX_GOALS
    ok = await guard_text_input(
        message, state, valid=valid,
        error_message="Введите число голов (например 7).",
    )
    if not ok:
        return
    data = await state.get_data()
    user = await repo.get_or_create_user(
        session, message.from_user.id, message.from_user.username
    )
    await repo.upsert_award(
        session, user.id, "TOP_SCORER", player_id=data["player"], int_value=int(text)
    )
    await session.commit()
    await send_next_step(message, state, session, user.id)


# --- Итоговая сводка ---

async def render_awards_summary(session: AsyncSession, user_id: int) -> str:
    teams = await repo.get_teams_map(session)
    awards = await repo.get_awards_map(session, user_id)

    final = await repo.get_bracket_pred(session, user_id, playoff.FINAL_MATCH)
    third = await repo.get_bracket_pred(session, user_id, 103)

    def team_name(team_id: int | None) -> str:
        return teams.get(team_id, "—") if team_id else "—"

    champion = team_name(final.winner_team_id if final else None)
    runner_up = "—"
    if final and final.winner_team_id:
        runner_up = team_name(
            final.away_team_id
            if final.home_team_id == final.winner_team_id
            else final.home_team_id
        )
    third_place = team_name(third.winner_team_id if third else None)

    lines = [
        "🏅 <b>Итог твоего прогноза</b>",
        "",
        f"🏆 Чемпион: <b>{champion}</b>",
        f"🥈 Финалист: {runner_up}",
        f"🥉 3-е место: {third_place}",
        "",
    ]
    for award_type, label, kind in AWARD_DISPLAY:
        a = awards.get(award_type)
        if a is None:
            value = "—"
        elif kind == "team":
            value = team_name(a.team_id)
        else:
            value = await repo.get_player_name(session, a.player_id) or "—"
            if kind == "player_goals" and a.int_value is not None:
                value += f" ({a.int_value} голов)"
        lines.append(f"{label}: <b>{value}</b>")

    # Символическая сборная.
    picks = await repo.get_tot_picks(session, user_id)
    by_pos: dict[str, list[str]] = {"GK": [], "DF": [], "MF": [], "FW": []}
    for p in picks:
        nm = await repo.get_player_name(session, p.player_id) or "—"
        by_pos.setdefault(p.position, []).append(nm)
    lines.append("")
    lines.append("👕 <b>Символическая сборная (4-3-3)</b>")
    for pos in ("GK", "DF", "MF", "FW"):
        if by_pos.get(pos):
            lines.append(f"{POSITION_LABEL[pos].capitalize()}: {', '.join(by_pos[pos])}")

    lines.append("")
    lines.append("Готово! Дальше — генерация PDF-отчёта (Фаза 5).")
    return "\n".join(lines)
