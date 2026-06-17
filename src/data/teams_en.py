"""Сопоставление английских названий сборных (football-data.org) с русскими из GROUPS.

Несколько вариантов написания на команду (Turkey/Türkiye, Czechia/Czech Republic и т.п.),
чтобы переживать разнобой в названиях у источника. Поиск — по нормализованному ключу.
"""

from __future__ import annotations

_RU_BY_EN_RAW: dict[str, str] = {
    "Mexico": "Мексика",
    "South Africa": "ЮАР",
    "Korea Republic": "Южная Корея",
    "South Korea": "Южная Корея",
    "Czechia": "Чехия",
    "Czech Republic": "Чехия",
    "Canada": "Канада",
    "Bosnia and Herzegovina": "Босния и Герцеговина",
    "Bosnia-Herzegovina": "Босния и Герцеговина",
    "Qatar": "Катар",
    "Switzerland": "Швейцария",
    "Brazil": "Бразилия",
    "Morocco": "Марокко",
    "Haiti": "Гаити",
    "Scotland": "Шотландия",
    "United States": "США",
    "USA": "США",
    "Paraguay": "Парагвай",
    "Australia": "Австралия",
    "Turkey": "Турция",
    "Türkiye": "Турция",
    "Turkiye": "Турция",
    "Germany": "Германия",
    "Curaçao": "Кюрасао",
    "Curacao": "Кюрасао",
    "Ivory Coast": "Кот-д'Ивуар",
    "Côte d'Ivoire": "Кот-д'Ивуар",
    "Cote d'Ivoire": "Кот-д'Ивуар",
    "Ecuador": "Эквадор",
    "Netherlands": "Нидерланды",
    "Japan": "Япония",
    "Sweden": "Швеция",
    "Tunisia": "Тунис",
    "Belgium": "Бельгия",
    "Egypt": "Египет",
    "Iran": "Иран",
    "New Zealand": "Новая Зеландия",
    "Spain": "Испания",
    "Cape Verde": "Кабо-Верде",
    "Cabo Verde": "Кабо-Верде",
    "Cape Verde Islands": "Кабо-Верде",
    "Saudi Arabia": "Саудовская Аравия",
    "Uruguay": "Уругвай",
    "France": "Франция",
    "Senegal": "Сенегал",
    "Iraq": "Ирак",
    "Norway": "Норвегия",
    "Argentina": "Аргентина",
    "Algeria": "Алжир",
    "Austria": "Австрия",
    "Jordan": "Иордания",
    "Portugal": "Португалия",
    "DR Congo": "ДР Конго",
    "Congo DR": "ДР Конго",
    "Democratic Republic of the Congo": "ДР Конго",
    "Uzbekistan": "Узбекистан",
    "Colombia": "Колумбия",
    "England": "Англия",
    "Croatia": "Хорватия",
    "Ghana": "Гана",
    "Panama": "Панама",
}


def _norm(name: str) -> str:
    return " ".join((name or "").split()).casefold()


_RU_BY_EN: dict[str, str] = {_norm(k): v for k, v in _RU_BY_EN_RAW.items()}


def ru_name(english: str) -> str | None:
    """Русское название сборной по английскому (или None, если не нашли)."""
    return _RU_BY_EN.get(_norm(english))
