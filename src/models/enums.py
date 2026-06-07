"""Перечисления предметной области."""

import enum


class Position(enum.StrEnum):
    """Позиция игрока."""

    GK = "GK"  # вратарь
    DF = "DF"  # защитник
    MF = "MF"  # полузащитник
    FW = "FW"  # нападающий


class Stage(enum.StrEnum):
    """Стадия плей-офф."""

    R32 = "R32"  # 1/16 финала
    R16 = "R16"  # 1/8 финала
    QF = "QF"  # четвертьфинал
    SF = "SF"  # полуфинал
    THIRD = "THIRD"  # матч за 3-е место
    FINAL = "FINAL"  # финал


class AwardType(enum.StrEnum):
    """Тип индивидуального/командного прогноза-награды."""

    CHAMPION = "CHAMPION"  # чемпион
    RUNNER_UP = "RUNNER_UP"  # финалист (2-е место)
    THIRD_PLACE = "THIRD_PLACE"  # 3-е место
    TOP_SCORER = "TOP_SCORER"  # золотая бутса (+ число голов)
    BEST_PLAYER = "BEST_PLAYER"  # золотой мяч
    YOUNG_PLAYER = "YOUNG_PLAYER"  # молодой игрок
    BEST_GOALKEEPER = "BEST_GOALKEEPER"  # золотая перчатка
    BREAKTHROUGH = "BREAKTHROUGH"  # открытие турнира (игрок)
    SURPRISE_TEAM = "SURPRISE_TEAM"  # сборная-сенсация
    DISAPPOINTMENT_TEAM = "DISAPPOINTMENT_TEAM"  # команда-разочарование
