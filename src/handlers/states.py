"""FSM-состояния бота."""

from aiogram.fsm.state import State, StatesGroup


class GroupStage(StatesGroup):
    """Ввод счёта группового матча."""

    waiting_score = State()


class Playoff(StatesGroup):
    """Прогноз матчей плей-офф."""

    waiting_score = State()
    waiting_winner = State()  # выбор прошедшего при ничьей


class Awards(StatesGroup):
    """Награды и символическая сборная (Фаза 4)."""

    choosing_team = State()
    choosing_player = State()
    waiting_goals = State()  # число голов бомбардира


class Results(StatesGroup):
    """Админ: ручной ввод реальных результатов матчей по матчам."""

    manual_score = State()  # ручной ввод счёта по матчам
