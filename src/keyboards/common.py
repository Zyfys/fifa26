"""Инлайн-клавиатуры бота."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def start_keyboard(
    *, has_progress: bool, has_predictions: bool = False
) -> InlineKeyboardMarkup:
    """Кнопка начала/продолжения прогноза (+ «Мои прогнозы», если есть что показать)."""
    text = "▶️ Продолжить прогноз" if has_progress else "⚽ Начать прогноз"
    builder = InlineKeyboardBuilder()
    builder.button(text=text, callback_data="begin")
    if has_predictions:
        builder.button(text="📋 Мои прогнозы", callback_data="my_open")
    builder.adjust(1)
    return builder.as_markup()


# Самые частые футбольные счёта (со стороны хозяев).
POPULAR_SCORES: list[tuple[int, int]] = [(1, 0), (2, 1), (1, 1), (2, 0), (0, 0), (0, 1)]


def score_keyboard(prefix: str, *, can_go_back: bool = False) -> InlineKeyboardMarkup:
    """Кнопки популярных счётов + «свой счёт» (+ опционально «назад»).

    Счёт: callback "<prefix>:<h>:<a>"; свой счёт: "<prefix>c"; назад: "edit_prev".
    """
    builder = InlineKeyboardBuilder()
    for home, away in POPULAR_SCORES:
        builder.button(text=f"{home}:{away}", callback_data=f"{prefix}:{home}:{away}")
    builder.button(text="✍️ Свой счёт", callback_data=f"{prefix}c")
    sizes = [3, 3, 1]
    if can_go_back:
        builder.button(text="⬅️ Изменить предыдущий", callback_data="edit_prev")
        sizes.append(1)
    builder.adjust(*sizes)
    return builder.as_markup()


def group_done_keyboard() -> InlineKeyboardMarkup:
    """После завершения группового этапа."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Показать таблицы групп", callback_data="show_tables")
    builder.button(text="📋 Мои прогнозы", callback_data="my_open")
    builder.button(text="🏆 Перейти к плей-офф", callback_data="to_playoff")
    builder.adjust(1)
    return builder.as_markup()


def my_forecast_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню просмотра «Мои прогнозы»: группы / плей-офф / точность."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⚽ Группы", callback_data="myf:groups")
    builder.button(text="🏆 Плей-офф", callback_data="myf:playoff")
    builder.button(text="🎯 Моя точность", callback_data="myf:accuracy")
    builder.adjust(1)
    return builder.as_markup()


def results_entry_keyboard(
    *, with_fetch: bool, with_reset: bool = False
) -> InlineKeyboardMarkup:
    """Админ: ручной ввод реальных результатов (поиск с автозаписью / по матчам / сброс)."""
    builder = InlineKeyboardBuilder()
    if with_fetch:
        builder.button(text="🌐 Найти и записать сейчас", callback_data="res:fetch")
    builder.button(text="🔢 По матчам", callback_data="res:manual")
    if with_reset:
        builder.button(text="🗑 Сбросить все результаты", callback_data="res:reset")
    builder.adjust(1)
    return builder.as_markup()


def results_reset_confirm_keyboard() -> InlineKeyboardMarkup:
    """Админ: подтверждение удаления всех реальных результатов."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Да, удалить все", callback_data="res:reset_yes")
    builder.button(text="Отмена", callback_data="res:reset_no")
    builder.adjust(1)
    return builder.as_markup()


PER_PAGE = 12


def _paginated(
    items: list[tuple[int, str]],
    page: int,
    pick_prefix: str,
    nav_prefix: str,
) -> InlineKeyboardMarkup:
    pages = max(1, (len(items) + PER_PAGE - 1) // PER_PAGE)
    page = max(0, min(page, pages - 1))
    chunk = items[page * PER_PAGE : (page + 1) * PER_PAGE]
    builder = InlineKeyboardBuilder()
    for item_id, name in chunk:
        builder.button(text=name, callback_data=f"{pick_prefix}:{item_id}")
    builder.adjust(2)

    if pages > 1:
        nav = InlineKeyboardBuilder()
        nav.button(
            text="◀️" if page > 0 else "·",
            callback_data=f"{nav_prefix}:{page - 1}" if page > 0 else "noop",
        )
        nav.button(text=f"{page + 1}/{pages}", callback_data="noop")
        nav.button(
            text="▶️" if page < pages - 1 else "·",
            callback_data=f"{nav_prefix}:{page + 1}" if page < pages - 1 else "noop",
        )
        nav.adjust(3)
        builder.attach(nav)
    return builder.as_markup()


def team_picker_keyboard(
    teams: list[tuple[int, str]], page: int = 0
) -> InlineKeyboardMarkup:
    """Пагинированный выбор команды (callback tm:<id>, навигация pg:<page>)."""
    return _paginated(teams, page, pick_prefix="tm", nav_prefix="pg")


def player_picker_keyboard(
    players: list[tuple[int, str]], page: int = 0
) -> InlineKeyboardMarkup:
    """Пагинированный выбор игрока (callback pl:<id>, навигация ppg:<page>)."""
    return _paginated(players, page, pick_prefix="pl", nav_prefix="ppg")


def winner_keyboard(home_name: str, away_name: str) -> InlineKeyboardMarkup:
    """Выбор прошедшей команды при ничьей в плей-офф (серия пенальти)."""
    builder = InlineKeyboardBuilder()
    builder.button(text=f"✅ {home_name}", callback_data="bwin:H")
    builder.button(text=f"✅ {away_name}", callback_data="bwin:A")
    builder.adjust(1)
    return builder.as_markup()


def awards_start_keyboard() -> InlineKeyboardMarkup:
    """Переход к наградам после заполнения сетки."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🎖 Перейти к наградам", callback_data="to_awards")
    return builder.as_markup()


def pdf_keyboard() -> InlineKeyboardMarkup:
    """Скачать итоговый PDF-отчёт."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📄 Скачать PDF-отчёт", callback_data="to_pdf")
    return builder.as_markup()


def reset_confirm_keyboard() -> InlineKeyboardMarkup:
    """Подтверждение сброса прогноза."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Да, сбросить", callback_data="reset_yes")
    builder.button(text="Отмена", callback_data="reset_no")
    builder.adjust(1)
    return builder.as_markup()
