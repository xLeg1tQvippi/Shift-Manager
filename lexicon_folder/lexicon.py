from pathlib import Path

db_name = "employee_schedule.db"
config_file_name = 'logging_config.yaml'

DB_DATA = {"db_name": db_name,
           "db_path": Path(__file__).parent.parent / f'database/{db_name}'}

LOGGING = {"config_file_name:": config_file_name,
           "config_path": Path(__file__).parent.parent / f"logging_configuration/{config_file_name}"}

ARRANGEMENT = {"path": Path(__file__).parent.parent / f"database/employee_arrangement.json"}

ARRANGEMENT_MENU = f"Меню расстановки\n1 - Показать расстановку\n2 - Создать/Изменить расстановку.\n0 - Выход\n>>> "

OUTER_ARRANGEMENT_MENU = f"Меню создания расстановки\n1 - Выбрать дату для расстановки\n2 - Выбрать участок\n3 - Выбрать сотрудников на участок\n0 - Выход\n>>> "
INNER_ARRANGEMENT_MENU = f"Меню расстановок\n1 - Изменить текущие расстановки\n2 - Создание новой расстановки\n0 - Выход\n>>> "

CHOOSE_SHIFT_TYPE_MENU = f"Меню выбора смены\n1 - Дневная\n2 - Ночная\n0 - Выход\n>>> "

JOB_POSITION_MENU = f"Меню сотрудника\n1 - Добавить позицию\n2 - Изменить время выхода на работу\n0 - Завершить\n>>> "

CREATE_ARRANGEMENT_MENU = "Меню создания расстановок\n1 - Создание расстановки путём копирования другой расстановки\n2 - Создать расстановку с нуля\n0 - Вернуться\n>>> "

CHANGE_ARRANGEMENT_DATA_MENU = "Управление копированной расстановкой\n1 - Изменить время начала смены\n2 - Изменить смену (День/Ночь)\n3 - Сбросить все позиции у всех сотрудников\n0 - Выход\n>>> "

EXCEL_PATH_SAVE = Path(__file__).parent.parent / "excel_data/"

