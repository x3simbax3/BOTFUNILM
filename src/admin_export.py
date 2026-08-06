"""Build the administrator user export as an in-memory Excel file."""

from __future__ import annotations

from dataclasses import astuple
from io import BytesIO

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font

from src.database.admin import AdminExportUser

HEADERS = (
    "Telegram ID",
    "Username",
    "Имя",
    "Активен",
    "Новости включены",
    "Первый запуск",
    "Последний /start",
    "Последняя активность",
    "Записей в библиотеке",
    "Хочу посмотреть",
    "Смотрю",
    "Просмотрено",
    "Отложено",
    "С оценкой",
    "Отслеживается",
)


def build_users_workbook(users: tuple[AdminExportUser, ...]) -> bytes:
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Пользователи")
    header = []
    for value in HEADERS:
        cell = WriteOnlyCell(sheet, value=value)
        cell.font = Font(bold=True)
        header.append(cell)
    sheet.append(header)
    for user in users:
        values = list(astuple(user))
        display_name = WriteOnlyCell(sheet, value=user.display_name)
        display_name.data_type = "s"
        values[2] = display_name
        values[3] = "Да" if user.is_active else "Нет"
        values[4] = "Да" if user.news_enabled else "Нет"
        sheet.append(values)

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


__all__ = ("build_users_workbook",)
