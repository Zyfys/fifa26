"""Импорт всех моделей, чтобы их видела декларативная база (и Alembic autogenerate)."""

from src.models.predictions import (
    AwardPrediction,
    BracketPrediction,
    GroupPrediction,
    TeamOfTournamentPick,
)
from src.models.reference import BracketSlot, Group, GroupMatch, Player, Team
from src.models.user import User

__all__ = [
    "Group",
    "Team",
    "Player",
    "GroupMatch",
    "BracketSlot",
    "User",
    "GroupPrediction",
    "BracketPrediction",
    "AwardPrediction",
    "TeamOfTournamentPick",
]
