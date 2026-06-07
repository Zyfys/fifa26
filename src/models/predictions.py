"""Прогнозы пользователя: группы, плей-офф, награды, символическая сборная."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.models.enums import AwardType, Position


class GroupPrediction(Base):
    """Прогноз счёта одного группового матча."""

    __tablename__ = "predictions_group"
    __table_args__ = (UniqueConstraint("user_id", "group_match_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    group_match_id: Mapped[int] = mapped_column(ForeignKey("group_matches.id"))
    home_score: Mapped[int] = mapped_column(SmallInteger)
    away_score: Mapped[int] = mapped_column(SmallInteger)


class BracketPrediction(Base):
    """Прогноз матча плей-офф для пользователя.

    Команды резолвятся по ходу прохождения сетки, поэтому храним их явно
    вместе со счётом и тем, кто прошёл дальше (для ничьей — победитель по пенальти).
    """

    __tablename__ = "predictions_bracket"
    __table_args__ = (UniqueConstraint("user_id", "match_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    match_number: Mapped[int] = mapped_column(
        ForeignKey("bracket_slots.match_number"), index=True
    )  # 73..104
    home_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    away_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    home_score: Mapped[int | None] = mapped_column(SmallInteger)
    away_score: Mapped[int | None] = mapped_column(SmallInteger)
    winner_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))


class AwardPrediction(Base):
    """Прогноз индивидуальной/командной награды.

    Заполняется team_id ИЛИ player_id в зависимости от типа награды.
    int_value используется для прогноза числа голов (золотая бутса).
    """

    __tablename__ = "predictions_awards"
    __table_args__ = (UniqueConstraint("user_id", "award_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    award_type: Mapped[AwardType] = mapped_column(String(24))
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))
    int_value: Mapped[int | None] = mapped_column(Integer)  # число голов для бомбардира


class TeamOfTournamentPick(Base):
    """Один игрок в символической сборной пользователя (схема 4-3-3).

    На пользователя — 11 строк: 1×GK, 4×DF, 3×MF, 3×FW.
    slot_index различает позиции одной линии (напр. защитники 1..4).
    """

    __tablename__ = "predictions_tot"
    __table_args__ = (
        UniqueConstraint("user_id", "position", "slot_index"),
        UniqueConstraint("user_id", "player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    position: Mapped[Position] = mapped_column(String(2))
    slot_index: Mapped[int] = mapped_column(SmallInteger)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
