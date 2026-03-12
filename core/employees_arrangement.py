# file for creating an automatic job placer. (To each department.)
import asyncio
import json
import aiosqlite
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from colorama import Fore
import logging
from typing import Union
import arrow

from db_operations.operations import DataBaseOperations, EmployeeDatabase, DepartmentBase, JobBase, ScheduleBase, ScheduleEmployeesBase
from helping_tools import HelpingTools

class CompleterInputController:
    logger: logging = logging.getLogger(__name__)
    
    @classmethod
    async def selected_data_handler(cls, inputed_data: str, dataset: dict | list) -> bool | int:
        if inputed_data == "0":
            return 0 
            
        try:
            if inputed_data in dataset:
                return True
            
            return False
        
        except Exception as error:
            cls.logger.error(error, exc_info=True)
            return False



class EmployeeNameEditor:
    @staticmethod
    async def get_full_name(last_name: str | None, first_name: str | None, middle_name: str | None, user_id: int) -> dict:
        if not first_name:
            name_text = last_name or "Unknown"
        elif not last_name and not middle_name:
            name_text = first_name
        else:
            full_name = [first_name, last_name, middle_name]
            if all(full_name) and len("".join(full_name)) <= 12:
                name_text = " ".join(full_name)
            else:
                parts = [last_name]
                if last_name: parts.append(f"{first_name[0]}.")
                if middle_name: parts.append(f"{middle_name[0]}.")
                name_text = " ".join(parts)

        return {name_text: user_id}

class EmployeeOperations:
    def __init__(self, db: aiosqlite.Connection):
        self.employee_db = EmployeeDatabase(db=db)
        self.logger = logging.getLogger(__name__)
        self.helping_tools = HelpingTools()

    async def get_user_id_by_name(self, last_name: str, first_name: str, middle_name: str) -> int:
        try:
            return await self.employee_db.get_user_id_by_name(first_name=first_name, last_name=last_name, middle_name=middle_name)
        
        except Exception as error:
            self.logger.error(error)
        
    async def get_all_users(self) -> dict:
        data = await self.employee_db.fetch_all_users()
        return data
    
    async def create_employee_dict(self) -> dict[str, int]:
        try:
            employee_data: dict[str, str] = await self.get_all_users()
            employee_dict_with_id: dict[str, int] = {}
            
            for row in employee_data:
                employee_info: dict = await EmployeeNameEditor.get_full_name(row['last_name'], row['first_name'], row['middle_name'], user_id=row['user_id'])
                employee_dict_with_id.update(employee_info)
            else:
                return employee_dict_with_id

        except Exception as error:
            self.logger.error(error, exc_info=True)

    async def create_and_get_new_employee(self, inputed_name: str) -> Union[tuple[str, int], tuple[int, int]]:
        print(f"\n{Fore.CYAN}--- Регистрация нового сотрудника ---{Fore.RESET}")
        full_name_raw = inputed_name.strip()
        
        if not full_name_raw:
            return 0, 0

        parts = full_name_raw.split()
        ln = parts[0] if len(parts) > 0 else "Неизвестный"
        fn = parts[1] if len(parts) > 1 else None
        mn = parts[2] if len(parts) > 2 else None
        
        await self.employee_db.add_user(first_name=fn, last_name=ln, middle_name=mn)
        new_user_id: int = await self.employee_db.get_user_id_by_name(first_name=fn, last_name=ln, middle_name=mn)
        try:
            new_user_id: int = new_user_id['user_id']
        except Exception as error:
            self.logger.error(error)
            
        name_edit_result = await EmployeeNameEditor.get_full_name(ln, fn, mn, new_user_id)
        short_name = list(name_edit_result.keys())[0]

        print(f"{Fore.GREEN}(✓) Сотрудник '{short_name}' успешно добавлен.{Fore.RESET}")
        return short_name, new_user_id

    async def employee_selector(self) -> Union[str, int]:
        employee_dict: dict[str, int] = await self.create_employee_dict()
        employee_completer = await WordCompleteCreator.createCompleter(dataset=employee_dict.keys())
        
        chosen_employee: str = await PromptSession().prompt_async(
            f"Выберите сотрудника: (TAB - Выбор, 0 - Выход)\n>>> ", 
            completer=employee_completer
        )
        
        if chosen_employee == '0':
            return 0, 0
        
        if not await CompleterInputController.selected_data_handler(inputed_data=chosen_employee, dataset=employee_dict):
            print(f"(*) Сотрудника '{chosen_employee}' нет в базе данных.")
            add_employee: int = await self.helping_tools.menu_int_handler("(*) Желаете добавить?\n1 - Да\n2 - Нет\n>>> ")
            
            if add_employee == 1:
                new_name, new_id = await self.create_and_get_new_employee(chosen_employee)
                return new_name, new_id
            else:
                return 0, 0
        
        employee_id: int = employee_dict[chosen_employee]
        return chosen_employee, employee_id


class DepartmentOperations:
    def __init__(self, db: aiosqlite.Connection):
        self.logger = logging.getLogger(__name__)
        self.department_base = DepartmentBase(db=db)
        
    async def get_all_departments(self) -> dict:
        try:
            departments: dict[int, str] = await self.department_base.get_all_departments()
            
        except Exception as error:
            self.logger.error(error, exc_info=True)
        
        else:
            return departments
    
    async def create_departments_dict(self) -> dict[str, int]:
        departments_dict: dict[str, int] = {}
        departments: dict = await self.get_all_departments()
        for id, name in departments:
            departments_dict[name] = id
            
        else:
            return departments_dict
    
    async def department_selector(self) -> Union[str, int]:
        try:
            departments_dict: dict[str, int] = await self.create_departments_dict()
            department_completer: WordCompleter = await WordCompleteCreator.createCompleter(dataset=departments_dict.keys())
            chosen_department: str = await PromptSession().prompt_async(f"Выберите участок: (TAB - Выбор, 0 - Выход)\n>>> ", completer=department_completer)
            department_id: int = departments_dict[chosen_department]
            
            if chosen_department == '0':
                return '0', '0'
            
        except Exception as error:
            self.logger.error(error, exc_info=True)

        else:
            return chosen_department, department_id
    
class JobPlaceOperations:
    def __init__(self, db: aiosqlite.Connection):
        self.logger: logging = logging.getLogger(__name__)
        self.job_base = JobBase(db=db)
        self.db = db
        
    async def add_new_job_position(self, job_name: str, department_id: int):
        return await self.job_base.add_job_position(job_name, department_id)

    async def delete_job_position(self, job_name: str, department_id: int):
        return await self.job_base.delete_job_position(job_name, department_id)
    
    async def create_job_position_dict(self, chosen_department_id: int) -> dict[str, int]:
        try:
            job_positions_list: list[str] = []
            job_positions: list = await self.job_base.get_all_job_positions(chosen_department_id)
            for job_pos in job_positions:
                job_positions_list.append(job_pos['job_name'])
            else:
                return job_positions_list
        
        except Exception as error:
            self.logger.error(error, exc_info=True)
            return []
    
    async def job_position_selector(self, chosen_department_id: int) -> str | None | int:
        try: 
            job_position_list: list[str] = await self.create_job_position_dict(chosen_department_id=chosen_department_id)
            if job_position_list:
                job_position_completer: WordCompleter = await WordCompleteCreator.createCompleter(dataset=job_position_list)
                chosen_job_position = await PromptSession().prompt_async(f"Выберите позицию: (TAB - Выбор, 0 - Выход)\n>>> ", completer=job_position_completer)
                if chosen_job_position == '0':
                    return 0   
            else:
                raise
            
        except Exception as error:
            print("(!) Ошибка. Для данного участка нету созданных позиций.")
            return False
        else:
            return chosen_job_position


class DateOperations:
    logger: logging = logging.getLogger(__name__)
    
    @classmethod
    async def _time_validator(cls, time_str: str) -> bool:
        try:
            arrow.get(time_str, ["H:mm", "HH:mm"])
            cls.logger.info(f"time successfully validated. ({time_str})")
            return True
        except Exception as error:
            cls.logger.error(error, exc_info=True)
            return False

    @classmethod
    async def _get_time(cls, choose_time: str, time_list: list[str]) -> str:
        if choose_time in time_list:
            return choose_time
        return choose_time

    @classmethod
    async def time_selector(cls, shift_type: str):
        try:
            shift_start_times = {
                "Day": ["7:00", "8:00", "9:00"], 
                "Night": ["18:00", "19:00", "20:00"]
            }
            
            available_times = shift_start_times.get(shift_type, [])
            
            while True:
                time_completer = await WordCompleteCreator.createCompleter(available_times)
                choose_time = await PromptSession().prompt_async(
                    f"Выберите время начала смены ({shift_type}) или введите своё (ЧЧ:ММ):\n>>> ", 
                    completer=time_completer
                )
                
                final_time = await cls._get_time(choose_time, available_times)
                is_valid = await cls._time_validator(final_time)
                
                if is_valid:
                    print(f"Выбранное время: {final_time}")
                    return final_time
                else:
                    print("Неверный формат времени. Используйте ЧЧ:ММ (пример: 8:00)")
                    continue

        except Exception as error:
            cls.logger.error(error, exc_info=True)
    
    @classmethod
    async def _data_validator(cls, date: str) -> bool:
        try:
            arrow.get(date, 'YYYY-MM-DD')
        
        except Exception as error:
            cls.logger.error(error, exc_info=True)
            return False
        
        else:
            cls.logger.info(f"date successfully validated. ({date})")
            return True
    
    @classmethod
    async def _get_date(cls, choose_date: str, date_dict: dict[str, arrow.Arrow]):
        if choose_date in date_dict:
            return date_dict[choose_date].format('YYYY-MM-DD')
        
        return choose_date

    @classmethod
    async def date_selector(cls):
        try:
            # we need to create a selector
            today = arrow.now()
            yesterday = today.shift(days=-1)
            tomorrow = today.shift(days=+1)
            
            date_dict = {"Сегодня": today, "Вчера": yesterday, "Завтра": tomorrow}
            date_list = [f"{date_name, "|", date_value}" for date_name, date_value in date_dict.items()]
            while True:
                date_completer = await WordCompleteCreator.createCompleter(date_dict.keys())
                choose_date: arrow = await PromptSession().prompt_async("Выберите дату (Либо введите свою: ГГГГ-ММ-ДД):\n>>> ", completer=date_completer)
                get_date = await DateOperations._get_date(choose_date=choose_date, date_dict=date_dict)
                date_valid: bool = await DateOperations._data_validator(get_date)
                if date_valid:
                    print(f"Выбранная дата: {get_date}")
                    return get_date
                else:
                    print("Повторите попытку. Введенная дата не верная. Прверьте структуру (ГГГГ-ММ-ДД)")
                    continue
                
        except Exception as error:
            cls.logger.error(error, exc_info=True)

class ScheduleOperations:
    def __init__(self, db: aiosqlite.Connection):
        self.logger: logging = logging.getLogger(__name__)
        self.schedule_base = ScheduleBase(db=db)
        self.department_base = DepartmentBase(db=db)

    async def get_all_schedules(self):
        try:
            schedules: list[dict[str, str]] = await self.schedule_base.get_all_departments_schedule()
            return schedules
        
        except Exception as error:
            self.logger.error(error, exc_info=True)
            return []

    async def create_schedule_list(self) -> dict:
        try:
            schedules = await self.get_all_schedules()
            display_dict = {}
            
            count = 0            
            for schedule in schedules:
                schedule_dict = {}
                display_parts = []
                for key in schedule.keys():
                    if schedule[key] and key != "department_id" and key != "id":
                        display_parts.append(str(schedule[key]))
                    schedule_dict[key] = schedule[key]
                count += 1
                display_parts.insert(0, str(count))
                display_string = " | ".join(display_parts)
                display_dict[display_string] = schedule_dict
                
            return display_dict
                    
        except Exception as error:
            print("(!) Расстановок еще не создано. Невозможно извлечь из Базы Данных.")
            return {}
    
    async def schedule_selector(self):
        try:
            schedule_display_dict = await self.create_schedule_list()
            turned_schedule_list: list = list(schedule_display_dict.keys())
            if schedule_display_dict:
                schedule_completer = await WordCompleteCreator.createCompleter(dataset=turned_schedule_list)
                chosen_display = await PromptSession().prompt_async(
                    "Выберите расписание (TAB - Выбор, 0 - Выход):\n>>> ", 
                    completer=schedule_completer
                )
                
                if chosen_display == "0":
                    return None
                    
                inputValidation: bool = await CompleterInputController.selected_data_handler(inputed_data=chosen_display, dataset=schedule_display_dict)
                if inputValidation:
                    chosen_schedule = schedule_display_dict.get(chosen_display)
                    return chosen_schedule
            else:
                print("(!) Список расписаний пуст.")
                return None
        
        except Exception as error:
            self.logger.error(error, exc_info=True)
            return None

class ScheduleEmployeesOperations:
    def __init__(self, db: aiosqlite.Connection):
        self.logger: logging = logging.getLogger(__name__)
        self.employees_schedule_base = ScheduleEmployeesBase(db=db)
        self.employees_ops = EmployeeOperations(db=db)
    
    async def create_employees_list(self, schedule_id: int) -> Union[dict[str, dict[str, str, str]]]:
        try:
            full_employees_dict: dict[str, str, str] = {}
            employees_data: list[dict[str, str]] = await self.employees_schedule_base.get_all_employees_by_schedule(schedule_id=schedule_id)
        
            self.employees_ops #TODO make a fetching data by username, get id
            
            if not employees_data:
                print("(!) Невозможно извлечь сотрудников данного участка из базы данных. (Добавьте сотрудников сначала.)")
                return {}
            
            for employee_data in employees_data:
                employee_data = dict(employee_data)
                # print(employee_data); input('stop')
                name_dict = await EmployeeNameEditor.get_full_name(
                    last_name=employee_data.get('last_name'),
                    first_name=employee_data.get('first_name'),
                    middle_name=employee_data.get('middle_name'),
                    user_id=employee_data.get('user_id')
                    )
                shorted_name: str = list(name_dict.keys())[0]
                name_dict[shorted_name] = [employee_data.get('last_name'), employee_data.get("first_name"), employee_data.get("middle_name")]
                full_employees_dict.update(name_dict)
        
        except Exception as error:
            self.logger.error(error, exc_info=True)
        
        else:
            self.logger.info("creating an employee list by schedule complete.")
            return full_employees_dict
    
    async def employee_selector_by_schedule(self, schedule_id: int) -> Union[str, int]:
        try:
            full_employees_dict = await self.create_employees_list(schedule_id=schedule_id)
            if not full_employees_dict:
                return 0, 0
            
            employees_completer: WordCompleter = await WordCompleteCreator.createCompleter(dataset=full_employees_dict.keys())
            
            while True:
                chosen_employee = await PromptSession().prompt_async(f"Выберите сотрудника для изменения: (TAB - Выбор, 0 - Выход)\n>>> ", completer=employees_completer)
                if chosen_employee == '0':
                    print("(!) Получен кода выхода при выборке сотрудников для изменения.")
                    return 0, 0
                chosen_employee_handler: bool = await CompleterInputController.selected_data_handler(inputed_data=chosen_employee, dataset=full_employees_dict)
                if chosen_employee_handler == 0:
                    return 0, 0
                
                if chosen_employee_handler:
                    # if the inputed employee is correct we return it.
                    employee_id: int = await self.employees_ops.get_user_id_by_name(last_name=full_employees_dict[chosen_employee][0], first_name=full_employees_dict[chosen_employee][1], middle_name=full_employees_dict[chosen_employee][2])
                    return chosen_employee, list(employee_id)[0]
                
                else:
                    print("(!) Введенный сотрдуник не найден. Повторите попытку.")
                    continue
            
        except Exception as error:
            self.logger.error(error, exc_info=True)
        
    async def show_all_employees_by_schedule(self, schedule_id: int, shift_date_start: str, department_name: str, shift_type: str):
        try:
            employees_data = await self.employees_schedule_base.get_all_employees_by_schedule(schedule_id=schedule_id)
            
            if not employees_data:
                return "Нет данных для вывода"

            # Группируем сотрудников по времени выхода (start_time)
            grouped_data = {}
            for row in employees_data:
                emp = dict(row)
                t = emp.get('start_time') or "Время не указано"
                if t not in grouped_data:
                    grouped_data[t] = []
                grouped_data[t].append(emp)

            output = [f"{shift_date_start}", ""]
            
            for start_time, employees in grouped_data.items():
                
                output.append(f"Расписание на {department_name} | {"День" if shift_type == 'Day' else "Ночь"}")
                output.append("-" * 20)
                
                for i, emp in enumerate(employees, 1):
                    name_dict = await EmployeeNameEditor.get_full_name(
                        last_name=emp.get('last_name'),
                        first_name=emp.get('first_name'),
                        middle_name=emp.get('middle_name'),
                        user_id=emp.get('user_id')
                    )
                    display_name = list(name_dict.keys())[0]
                    job = emp.get('job_place') or ""
                    
                    job_text = f" ({job})" if job else ""
                    output.append(f"{start_time} | {i}. {display_name}{job_text}")
                
                output.append("-" * 20)
            
            #todo here
            final_text = "\n".join(output)
            print(final_text)
            return final_text

        except Exception as error:
            self.logger.error(error, exc_info=True)


class WordCompleteCreator:
    logger: logging = logging.getLogger(__name__)

    @classmethod
    async def createCompleter(cls, dataset: list) -> WordCompleter:
        try:
            completer = WordCompleter(dataset, ignore_case=True, match_middle=True, sentence=True)

        except Exception:
            cls.logger.error(exc_info=True)
            return None
        
        else:
            return completer

if __name__ == "__main__":
    empl = EmployeeOperations()
    asyncio.run(empl.get_all_users())