"""Справочные модели: группы, команды, игроки, расписание, структура сетки.

Эти данные статичны и заполняются сид-скриптом из данных ЧМ-2026.
"""

from __future__ import annotations

import datetime

from sqlalchemy import Date, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base
from src.models.enums import Position, Stage


class Group(Base):
    """Группа турнира (A–L)."""

    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    letter: Mapped[str] = mapped_column(String(1), unique=True)  # 'A'..'L'

    teams: Mapped[list[Team]] = relationship(back_populates="group")


class Team(Base):
    """Сборная — участник турнира."""

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)  # русское название
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    fifa_rank: Mapped[int | None] = mapped_column(Integer)  # для тай-брейков/жребия

    group: Mapped[Group] = relationship(back_populates="teams")
    players: Mapped[list[Player]] = relationship(back_populates="team")


class Player(Base):
    """Игрок сборной (из официальной заявки ЧМ-2026)."""

    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(96))  # русское написание
    position: Mapped[Position] = mapped_column(String(2))
    birth_date: Mapped[datetime.date | None] = mapped_column(Date)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))

    team: Mapped[Team] = relationship(back_populates="players")


class GroupMatch(Base):
    """Матч группового этапа (расписание)."""

    __tablename__ = "group_matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    match_number: Mapped[int] = mapped_column(Integer, unique=True)  # 1..72
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))

    group: Mapped[Group] = relationship()
    home_team: Mapped[Team] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped[Team] = relationship(foreign_keys=[away_team_id])


class BracketSlot(Base):
    """Статическая структура матча плей-офф (матчи 73–104).

    Описывает, откуда берутся участники: либо место в группе, либо победитель/
    проигравший предыдущего матча сетки. Конкретные команды для пользователя
    вычисляются на основе его прогноза (Фаза 3).
    """

    __tablename__ = "bracket_slots"

    match_number: Mapped[int] = mapped_column(SmallInteger, primary_key=True)  # 73..104
    stage: Mapped[Stage] = mapped_column(String(8))

    # Источник участников в человекочитаемом виде, напр. "W74" (победитель матча 74),
    # "L101" (проигравший 101), "1A" (1-е место группы A), "2B", "3X" (третье место).
    home_source: Mapped[str] = mapped_column(String(8))
    away_source: Mapped[str] = mapped_column(String(8))
