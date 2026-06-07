"""Групповой этап: ввод счёта матчей и показ таблиц."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.wc2026 import team_label
from src.db import repo
from src.handlers.callbacks import accessible_message, guard_text_input
from src.handlers.states import GroupStage
from src.keyboards.common import group_done_keyboard, score_keyboard
from src.services.scores import (
    MAX_SCORE,
    SCORE_RE,
    parse_score,
    score_error_message,
)
from src.services.standings import (
    THIRD_PLACES_QUALIFY,
    StandingRow,
    compute_standings,
    rank_third_places,
)

router = Router()

# Реэкспорт для обратной совместимости (используется в playoff.py и тестах).
__all__ = ["MAX_SCORE", "SCORE_RE", "router"]


def _match_prompt(match, current_number: int) -> str:
    return (
        f"⚽ <b>Группа {match.group.letter}</b> · "
        f"матч {current_number}/{repo.GROUP_MATCHES_TOTAL}\n\n"
        f"🆚 <b>{team_label(match.home_team.name)}</b> — "
        f"<b>{team_label(match.away_team.name)}</b>\n\n"
        f"Выбери счёт кнопкой или введи свой (например <code>3:2</code> или <code>4-4</code>)"
    )


async def send_next_match(
    message: Message, state: FSMContext, session: AsyncSession, user_id: int
) -> None:
    """Показать следующий незаполненный матч или завершить групповой этап."""
    match = await repo.get_next_group_match(session, user_id)
    if match is None:
        await state.clear()
        thirds = await render_third_places(session, user_id)
        await message.answer(
            "🎉 <b>Групповой этап заполнен!</b>\n\n"
            f"{thirds}\n\n"
            "Можно посмотреть все таблицы групп. Дальше — плей-офф (скоро).",
            reply_markup=group_done_keyboard(),
        )
        return

    answered = await repo.count_group_predictions(session, user_id)
    await state.set_state(GroupStage.waiting_score)
    await state.update_data(match_id=match.id)
    await message.answer(
        _match_prompt(match, answered + 1),
        reply_markup=score_keyboard("gs", can_go_back=match.match_number > 1),
    )


async def _apply_group_score(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    tg_user,
    home: int,
    away: int,
) -> None:
    """Сохранить счёт текущего группового матча и перейти к следующему."""
    data = await state.get_data()
    match_id = data.get("match_id")
    if match_id is None:
        await message.answer("Что-то пошло не так, начните заново: /start")
        await state.clear()
        return

    user = await repo.get_or_create_user(session, tg_user.id, tg_user.username)
    match = await repo.get_group_match(session, match_id)
    await repo.upsert_group_prediction(session, user.id, match_id, home, away)
    await session.commit()

    # Если группа полностью заполнена — показываем её итоговую таблицу.
    if match is not None and await repo.is_group_complete(
        session, match.group_id, user.id
    ):
        table = await render_group_table(
            session, match.group_id, match.group.letter, user.id
        )
        await message.answer(
            f"✅ <b>Группа {match.group.letter} заполнена!</b> Итоговая таблица:\n\n"
            f"{table}\n\n{_LEGEND}"
        )

    await send_next_match(message, state, session, user.id)


@router.message(GroupStage.waiting_score, F.text)
async def on_score(message: Message, state: FSMContext, session: AsyncSession) -> None:
    parsed = parse_score(message.text)
    ok = await guard_text_input(
        message, state, valid=parsed is not None,
        error_message=score_error_message(message.text),
    )
    if not ok:
        return
    home, away = parsed
    await _apply_group_score(message, state, session, message.from_user, home, away)


@router.callback_query(GroupStage.waiting_score, F.data.startswith("gs:"))
async def on_score_button(
    call: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    msg = await accessible_message(call)
    if msg is None:
        return
    _, home, away = call.data.split(":")
    await msg.edit_reply_markup(reply_markup=None)
    await call.answer()
    await _apply_group_score(msg, state, session, call.from_user, int(home), int(away))


@router.callback_query(GroupStage.waiting_score, F.data == "gsc")
async def on_score_custom(call: CallbackQuery) -> None:
    msg = await accessible_message(call)
    if msg is None:
        return
    await call.answer()
    await msg.answer(
        "✍️ Введи счёт текстом, например <code>3:2</code> или <code>4-4</code>"
    )


@router.callback_query(F.data == "edit_prev")
async def on_edit_prev(
    call: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    msg = await accessible_message(call)
    if msg is None:
        return
    data = await state.get_data()
    current = await repo.get_group_match(session, data.get("match_id", 0))
    prev = (
        await repo.get_prev_group_match(session, current.match_number)
        if current
        else None
    )
    if prev is None:
        await call.answer("Это первый матч — назад нельзя.")
        return
    await state.update_data(match_id=prev.id)
    await msg.answer(
        "✏️ Исправление предыдущего матча.\n\n"
        f"🆚 <b>{team_label(prev.home_team.name)}</b> — "
        f"<b>{team_label(prev.away_team.name)}</b>\n\n"
        "Выбери новый счёт кнопкой или введи свой",
        reply_markup=score_keyboard("gs", can_go_back=prev.match_number > 1),
    )
    await call.answer()


@router.callback_query(F.data == "show_tables")
async def on_show_tables(call: CallbackQuery, session: AsyncSession) -> None:
    msg = await accessible_message(call)
    if msg is None:
        return
    user = await repo.get_or_create_user(
        session, call.from_user.id, call.from_user.username
    )
    text = await render_all_tables(session, user.id)
    await msg.answer(text)
    await call.answer()


# --- Отрисовка таблиц ---

def _format_group(letter: str, rows: list[StandingRow]) -> str:
    lines = [f"<b>Группа {letter}</b>", "<pre>"]
    lines.append("№ Команда           И  О  РМ")
    marks = {0: "✅", 1: "✅", 2: "🟡"}
    for i, r in enumerate(rows):
        mark = marks.get(i, "  ")
        name = r.team_name[:15].ljust(15)
        lines.append(f"{i + 1}{mark}{name} {r.played} {r.points:2} {r.gd:+d}")
    lines.append("</pre>")
    return "\n".join(lines)


_LEGEND = "✅ — в плей-офф, 🟡 — претендент на лучшее 3-е место"


async def render_group_table(
    session: AsyncSession, group_id: int, letter: str, user_id: int
) -> str:
    """Отрисовать таблицу одной группы."""
    teams = await repo.get_group_teams(session, group_id)
    results = await repo.get_group_results(session, group_id, user_id)
    rows = compute_standings(teams, results)
    return _format_group(letter, rows)


async def render_third_places(session: AsyncSession, user_id: int) -> str:
    """Ранжирование команд на 3-х местах: кто из них выходит в плей-офф."""
    groups = await repo.get_all_groups(session)
    thirds: list[tuple[str, StandingRow]] = []
    for g in groups:
        teams = await repo.get_group_teams(session, g.id)
        results = await repo.get_group_results(session, g.id, user_id)
        rows = compute_standings(teams, results)
        if len(rows) >= 3:
            thirds.append((g.letter, rows[2]))

    ranked = rank_third_places(thirds)
    lines = [
        f"🥉 <b>Лучшие третьи места</b> (проходят {THIRD_PLACES_QUALIFY} из {len(ranked)}):",
        "<pre>",
        "    Гр Команда          О  РМ",
    ]
    for i, (letter, r) in enumerate(ranked):
        mark = "✅" if i < THIRD_PLACES_QUALIFY else "❌"
        name = r.team_name[:15].ljust(15)
        lines.append(f"{mark} {letter}  {name} {r.points:2} {r.gd:+d}")
    lines.append("</pre>")
    return "\n".join(lines)


async def render_all_tables(session: AsyncSession, user_id: int) -> str:
    groups = await repo.get_all_groups(session)
    blocks = [
        await render_group_table(session, g.id, g.letter, user_id) for g in groups
    ]
    thirds = await render_third_places(session, user_id)
    return (
        "📊 <b>Таблицы групп</b>\n\n"
        + "\n\n".join(blocks)
        + "\n\n"
        + _LEGEND
        + "\n\n"
        + thirds
    )
