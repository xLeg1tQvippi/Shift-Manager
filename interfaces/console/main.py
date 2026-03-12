from db_operations.operations import EmployeeDatabase, DepartmentBase, JobBase, DataBaseOperations, ScheduleBase, ScheduleEmployeesBase, DayOffSetterBase
from core.employees_arrangement import EmployeeOperations, DepartmentOperations, JobPlaceOperations, CompleterInputController, DateOperations, ScheduleOperations, ScheduleEmployeesOperations

import aiosqlite
import asyncio
import logging
import json
from typing import Union
from colorama import Fore

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from logging_configuration.logging_setup import setup_logging
from lexicon_folder import lexicon
from helping_tools import HelpingTools
import json
import pyperclip
import arrow

class ConsoleApp:
    def __init__(self, db = aiosqlite.Connection):
        super().__init__()
        setup_logging()
        self.logger: logging = logging.getLogger(__name__)    
        self.employee_ops = EmployeeOperations(db=db)
        self.department_ops = DepartmentOperations(db=db)
        self.job_ops = JobPlaceOperations(db=db)
        self.schedule_employees_base = ScheduleEmployeesBase(db=db)
        self.schedule_base = ScheduleBase(db=db)
        self.helping_tools = HelpingTools()
        self.schedule_ops = ScheduleOperations(db=db)
        self.schedule_employees_ops = ScheduleEmployeesOperations(db=db)
        self.day_off_setter_base = DayOffSetterBase(db=db)
        self.arrangement_creator = ArrangementCreator(employee_ops=self.employee_ops, job_ops=self.job_ops, department_ops=self.department_ops, schedule_employees_base=self.schedule_employees_base, schedule_base=self.schedule_base, schedule_ops=self.schedule_ops, schedule_employees_ops=self.schedule_employees_ops, day_off_setter_base=self.day_off_setter_base)
        self.max_department_employees: int = 0
    
    async def arrangement_menu(self):
        # main menu of creating arrangement for schedule.
        # 1. show arrangment (on specific date. (With word compeleter based on created already.))
        # 2. create arrangment
        # 3. leave.
        await self.helping_tools.clear_console()
        while True:
            try:
                menu_chose: int = await self.helping_tools.menu_int_handler(text=lexicon.ARRANGEMENT_MENU, min_value=0, max_value=2)
                
                if menu_chose == 0:
                    break
                
                elif menu_chose == 1:
                    schedule_data: dict[str, str | int] = await self.schedule_ops.schedule_selector()
                    if not schedule_data:
                        continue
                    result = await self.schedule_employees_ops.show_all_employees_by_schedule(schedule_id=schedule_data['id'], shift_date_start=schedule_data['date'], department_name=schedule_data['name'], shift_type=schedule_data['shift_type'])
                    pyperclip.copy(result)
                    print('copied.')
                    
                elif menu_chose == 2:
                    await self.arrangement_creator.menu()

                
            except Exception as error:
                self.logger.error(error, exc_info=True)

class ArrangementCreator:
    def __init__(self, employee_ops: EmployeeOperations, department_ops: DepartmentOperations, job_ops: JobPlaceOperations, schedule_employees_base: ScheduleEmployeesBase, schedule_base: ScheduleBase, schedule_ops: ScheduleOperations, schedule_employees_ops: ScheduleEmployeesOperations, day_off_setter_base: DayOffSetterBase):
        self.logger: logging = logging.getLogger(__file__)
        self.helping_tools = HelpingTools()
        self.employee_ops = employee_ops
        self.department_ops = department_ops
        self.job_ops = job_ops
        self.schedule_employees_base = schedule_employees_base
        self.schedule_base = schedule_base
        self.schedule_ops = schedule_ops
        self.schedule_employees_ops = schedule_employees_ops
        self.day_off_setter_base = day_off_setter_base
        
        self.department_id: int = 0
        self.department_name: str | None = None
        self.shift_type: str | None = None
        self.shift_start_time: str | None = None
        self.shift_start_date: str | None = None
        self.current_schedule_id: int | None = None
    
    async def change_copied_schedule_data_menu(self, schedule_id: int):
        try:
            while True:
                choice = await self.helping_tools.menu_int_handler(lexicon.CHANGE_ARRANGEMENT_DATA_MENU, min_value=0, max_value=3)
                
                if choice == 0:
                    break
                
                elif choice == 1:
                    new_time = await DateOperations.time_selector(shift_type="Default")
                    await self.schedule_base.update_schedule_info(schedule_id=schedule_id, start_time=new_time, date=self.shift_start_date, department_id=self.department_id)
                    await self.schedule_employees_base.update_all_employees_start_time(schedule_id=schedule_id, new_start_time=new_time)
                    print(f"{Fore.GREEN}(✓) Время начала смены обновлено для всех.{Fore.RESET}")
                
                elif choice == 2:
                    print("1 - День\n2 - Ночь")
                    shift_choice = await self.helping_tools.menu_int_handler(">>> ", min_value=1, max_value=2)
                    new_shift = "Day" if shift_choice == 1 else "Night"
                    await self.schedule_base.update_schedule_info(schedule_id=schedule_id, shift_type=new_shift, date=self.shift_start_date, department_id=self.department_id)
                    print(f"{Fore.GREEN}(✓) Тип смены изменен на: {new_shift}.{Fore.RESET}")
                    
                elif choice == 3:
                    confirm = input(f"{Fore.YELLOW}(?) Вы уверены, что хотите сбросить все позиции? (1 - Да): {Fore.RESET}")
                    if confirm == "1":
                        await self.schedule_employees_base.reset_all_job_places_to_all_employees(schedule_id=schedule_id)
                        print(f"{Fore.GREEN}(✓) Все рабочие места обнулены.{Fore.RESET}")

        except Exception as error:
            self.logger.error(f"Ошибка в меню изменения копии: {error}", exc_info=True)

    async def copy_schedule_to_new_date(self):
        try:
            print(f"{Fore.CYAN}--- Копирование расписания ---{Fore.RESET}")
            
            source_schedule = await self.schedule_ops.schedule_selector()
            if not source_schedule: return

            target_date = await DateOperations.date_selector()
            
            new_id = await self.schedule_base.duplicate_schedule_header(
                old_schedule_id=source_schedule['id'], 
                new_date=target_date
            )

            await self.schedule_employees_base.copy_employees_between_schedules(
                from_id=source_schedule['id'], 
                to_id=new_id
            )
            
            print(f"{Fore.GREEN}(✓) Расписание участка '{source_schedule['name']}' успешно скопировано на {target_date}{Fore.RESET}")
            
            # Вызываем меню правки сразу после копирования
            await self.change_copied_schedule_data_menu(schedule_id=new_id)
            
        except Exception as error:
            self.logger.error(error, exc_info=True)

        
    async def show_schedule(self, department_id: int = None):
        # shows a full schedule.
        try:
            await self.schedule_base.get_all_departments_schedule()
        
        except Exception as error:
            self.logger.error(error, exc_info=True)
            
        else:
            pass
    
    async def choose_department(self) -> Union[str, int]:
        try:
            if self.shift_start_date != None:
                self.department_name, self.department_id = await self.department_ops.department_selector()
            else:
                print("(!) Ошибка. Выбрите дату создания расстановки.")
                return
            
        except Exception as error:
            self.logger.error(error, exc_info=True)
            
        else:
            print("Участок успешно выбран.")

    async def choose_shift_start_time(self, shift_type: str):
        try:
            self.shift_start_time = await DateOperations.time_selector(shift_type=shift_type)
        
        except Exception as error:
            self.logger.error(error, exc_info=True)
        
        finally:
            print(f"Время {self.shift_start_time} успешно установлено.")

    async def choose_shift(self) -> str:
        try:
            shift_choose: int = await self.helping_tools.menu_int_handler(lexicon.CHOOSE_SHIFT_TYPE_MENU, min_value=0, max_value=2)

            if shift_choose == 0:
                return
            
            elif shift_choose == 1:
                self.shift_type = 'Day'
            
            elif shift_choose == 2:
                self.shift_type = 'Night'
            
        except Exception as error:
            self.logger.error(error, exc_info=True)
            
        finally:
            print(f"Смена успешно выбрана. ({self.shift_type})")

    async def get_schedule_id_by_department(self, department_id: int, date: str, shift_type: str):
        try:
            print(f"before updating schedule id: {self.current_schedule_id}")
            self.current_schedule_id: int = await self.schedule_base.get_schedule_id(date=date, department_id=department_id, shift_type=shift_type)
            print(f"recieved from function, updated schedule id: {self.current_schedule_id}")
        except Exception as error:
            self.logger.error(error, exc_info=True)

    async def create_schedule_department(self, date: str, dept_id: int, shift_type: str, start_time: str, end_time: str | None = None):
        try:
            await self.schedule_base.add_department_schedule(date=date, department_id=dept_id, shift_type=shift_type, start_time=start_time, end_time=end_time)
            
        except Exception as error:
            self.logger.error(error, exc_info=True)
        
        else:
            self.logger.info("department was successfully created in schedule table.")

    async def change_start_time_for_employee(self, employee_name: str, shift_type: str) -> str:
        try:
            print(f"(?) Изменение времени выхода на работу, для сотрудника: {Fore.LIGHTWHITE_EX}{employee_name}{Fore.RESET}")
            return await DateOperations.time_selector(shift_type=shift_type)
        
        except Exception as error:
            self.logger.error(error)
    
    async def choose_job_position(self, employee_name: str, department_id: int) -> str:
        try:
            job_position: str = await self.job_ops.job_position_selector(department_id)
            if not job_position:
                raise
            
            elif job_position == 0:
                return 0
            #todo CREATE DATA VALIDATOR, IF USER ACCIDENTLY JOINT THIS FUNCTION.
            
        except Exception as error:
            self.logger.info(error)
            print(f"(*) Позиция не была установлена, по причине отсутствия позиций на данном участке.")
            return 0
        
        else:
            print(f"(*) Позиция '{Fore.LIGHTWHITE_EX}{job_position}{Fore.RESET}' успешно выбрана для сотрудника '{Fore.LIGHTWHITE_EX}{employee_name}{Fore.RESET}'")
            return job_position
    
    async def show_employee_stats(self, employee_stats: dict[str, str]):
        try:
            status = employee_stats[0]
            work_streak = employee_stats[1]
            last_activity = employee_stats[2]
            last_date = arrow.get(last_activity)
            days_diff = (arrow.now() - last_date).days
                
            print(f"(>) {Fore.LIGHTWHITE_EX}Статистика{Fore.RESET}")
            print(f"(*) Статус: {Fore.GREEN if status == 'Working' else Fore.RED}{status}{Fore.RESET}")
            if status == 'Working':
                print(f"(*) Дней отработано: {Fore.YELLOW}{work_streak}{Fore.RESET} (С последнего выхода на работу.)")
            else:
                print(f"(*) На выходном с {last_date.format('DD.MM')} (отдыхает {Fore.LIGHTWHITE_EX}{days_diff}{Fore.RESET} дн.)")
                    
        except Exception as error:
            # self.logger.error(error, exc_info=True)
            print("(!) У сотрудника отсутствует статистика.")
        else:
            print('-'*15)
    async def job_position_menu_and_change_time(self, employee_name: str, department_name: str, department_id: int, shift_type: str, shift_start_time: str, employee_stats: dict[str, str], job_position: str | None = None) -> dict[str, str]:
        
        employee_additional_data = {"job_position": None, "start_time": self.shift_start_time}
        employee_additional_data['job_position'] = job_position
    
        while True:
            try:
                print(f"\n{'-'*len(employee_name)}\n(>) {Fore.LIGHTWHITE_EX}{employee_name}{Fore.RESET}\n(*) Участок: {department_name}\n(*) Позиция: {"Не установлена" if employee_additional_data['job_position'] == None else employee_additional_data['job_position']}\n(*) Выход: {shift_start_time if employee_additional_data['start_time'] == None else employee_additional_data['start_time']}\n{'-'*len(employee_name)}")
                await self.show_employee_stats(employee_stats)
                job_menu_choice: int = await self.helping_tools.menu_int_handler(text=lexicon.JOB_POSITION_MENU, min_value=0, max_value=2)
                
                if job_menu_choice == 0:
                    break
                
                elif job_menu_choice == 1:
                    # choosing job position
                    job_position: str = await self.choose_job_position(employee_name=employee_name, department_id=department_id)
                    if job_position and job_position != 0:
                        employee_additional_data["job_position"] = job_position
                    
                elif job_menu_choice == 2:
                    # changing start time for the employee.
                    changed_start_time: str = await self.change_start_time_for_employee(employee_name=employee_name, shift_type=shift_type)
                    employee_additional_data["start_time"] = changed_start_time
        
            except Exception as error:
                self.logger.error(error)

        return employee_additional_data
    
    async def add_employee_to_schedule(self, schedule_id: int, user_id: int, additonal_employee_data: dict[str, str]):
        try:
            await self.schedule_employees_base.add_employee_to_schedule(schedule_id=schedule_id, user_id=user_id, job_place=additonal_employee_data['job_position'], start_time=additonal_employee_data['start_time'])
        
        except Exception as error:
            self.logger.error(error, exc_info=True)
            
        else:
            print(f"{Fore.GREEN}(✓) Сотрудник был успешно добавлен на участок.{Fore.RESET}")
    
    async def create_arrangement(self, department_name: str, department_id: int, date: str):
        if department_name == None or department_id == 0:
            print("(!) Участок не выбран. Пожалуста выберите участок чтобы добавить сотрудников.")
            return
        
        print(f"Участок: {Fore.LIGHTWHITE_EX}{department_name}{Fore.RESET}")
        if self.shift_type == None:
            await self.choose_shift()
            if not await self.schedule_base.check_if_schedule_exists(date=date, department_id=department_id, shift_type=self.shift_type):
                return 
        
        
        if self.shift_start_time == None:
            print(f"{Fore.YELLOW}(!) Пожалуйста, перед выбором сотрудников для участка, установите время выхода на участок {Fore.LIGHTWHITE_EX}{self.department_name}{Fore.RESET}")
            await self.choose_shift_start_time(shift_type=self.shift_type)
        
        # before start we add data to schedule table DB.
        try:
            await self.create_schedule_department(dept_id=department_id, date=date, shift_type=self.shift_type, start_time=self.shift_start_time)
        except Exception as error:
            pass
        
        while True:
            try:
                print(f"(*) Участок: {Fore.LIGHTWHITE_EX}{department_name}{Fore.RESET}\n(*) Смена: {Fore.LIGHTWHITE_EX}{self.shift_type}{Fore.RESET}\n(*) Выход: {Fore.LIGHTWHITE_EX}{self.shift_start_time}{Fore.RESET}\n")
                
                employee_name, employee_id = await self.employee_ops.employee_selector()
                if employee_name == 0 and employee_id == 0:
                    return
                # here we will instantly add an employee to schedule.
                # we're adding: employee_id / name + shift_type, shift_starting_time & schedule_id. Taken by department creation
                employee_stats: dict[str, str] = await self.day_off_setter_base.get_employee_stats(employee_id)
                employee_additional_data: dict[str, str] = await self.job_position_menu_and_change_time(employee_name, department_name, department_id, self.shift_type, self.shift_start_time, employee_stats=employee_stats)
                # job_position
                # start_time
                        
                await self.get_schedule_id_by_department(department_id, date, shift_type=self.shift_type)
                
            except Exception as error:
                self.logger.error(error, exc_info=True)
                continue
            
            else:
                await self.add_employee_to_schedule(schedule_id=self.current_schedule_id, user_id=employee_id, additonal_employee_data=employee_additional_data)
                await self.day_off_setter_base.increment_work_streak(user_id=employee_id, shift_date=date)
                
    async def change_employee_data_menu(self, employee_name: str, employee_id: int, schedule_id: int, schedule_data: dict[str, str]):
        try:
            while True:
                print(f"\n{Fore.CYAN}Управление сотрудником: {Fore.WHITE}{employee_name}{Fore.RESET}")
                print(f"1. Изменить время и позицию\n2. Убрать сотрудника из расстановки\n3. Переместить в другой участок\n4. Установить выходной сотруднику\n0. Назад")
                
                
                choice = await self.helping_tools.menu_int_handler(">>> ", min_value=0, max_value=4)

                employee_data: dict[str, str] = await self.schedule_employees_base.get_employee_current_info(schedule_data['id'], user_id=employee_id)
                employee_stats: dict[str, str] = await self.day_off_setter_base.get_employee_stats(employee_id)
                
                if choice == 1:
                    # Вызываем меню изменения позиции и времени, которое мы писали ранее
                    new_data = await self.job_position_menu_and_change_time(employee_name, department_name=employee_data['department_name'], department_id=schedule_data['department_id'], shift_type=employee_data['shift_type'], shift_start_time=employee_data['shift_start_time'], job_position=employee_data['job_position'], employee_stats=employee_stats)
                    print(f'SCHEDULE ID BEFORE EMPLOYEE DATA ADDITION: LOCAL: {schedule_id}, INNER_DATA: {schedule_data['id']} OUTER: {self.current_schedule_id}')
                    await self.schedule_employees_base.update_employee_in_schedule(
                        schedule_id=schedule_id, 
                        user_id=employee_id, 
                        job_place=new_data['job_position'], 
                        start_time=new_data['start_time']
                    )
                    print(f"{Fore.GREEN}(✓) Данные обновлены.{Fore.RESET}")

                elif choice == 2:
                    # Просто удаляем запись из schedule_employees для этого schedule_id
                    confirm = input(f"Удалить {employee_name} из текущего расписания? (1 - Да): ")
                    if confirm == "1":
                        await self.schedule_employees_base.delete_employee_from_schedule(schedule_id, employee_id)
                        print(f"{Fore.YELLOW}(!) Сотрудник убран из списка.{Fore.RESET}")
                        break

                elif choice == 3:
                    new_dept_name, new_dept_id = await self.department_ops.department_selector()
                                    
                    new_schedule_id = await self.schedule_base.get_schedule_id(schedule_data['date'], new_dept_id)
                    
                    if new_schedule_id is None:
                        print(f"(!) Расписание для '{new_dept_name}' на {self.shift_start_date} еще не создано.")
                        confirm_create = input("Создать его сейчас? (1 - Да, 0 - Отмена): ")
                        if confirm_create == "1":
                            await self.choose_shift_start_time(shift_type=await self.choose_shift())
                            await self.create_schedule_department(date=schedule_data['date'], dept_id=new_dept_id, shift_type=schedule_data['shift_type'], start_time=schedule_data['start_time'])
                            new_schedule_id = await self.schedule_base.get_schedule_id(schedule_data['date'], new_dept_id)
                        else:
                            continue

                    if new_schedule_id == schedule_id:
                        print(f"{Fore.YELLOW}(!) Сотрудник уже находится на этом участке.{Fore.RESET}")
                        continue

                    await self.schedule_employees_base.move_employee(
                        old_sid=schedule_id, 
                        new_sid=new_schedule_id, 
                        user_id=employee_id
                    )
                    print(f"{Fore.GREEN}(✔) Перемещено в {new_dept_name}{Fore.RESET}")
                    break

                elif choice == 4:
                    # putting an employee to day off status.
                    # add employee to day off table
                    await self.day_off_setter_base.put_employee_to_day_off(employee_id)
                    await self.schedule_employees_base.delete_employee_from_schedule(schedule_id, employee_id)

                    print(f"(*) Сотрудник {Fore.LIGHTWHITE_EX}{employee_name}{Fore.RESET} был успешно переведён на выходной.")                
                    return
                
                elif choice == 0:
                    break

        except Exception as error:
            self.logger.error(f"Ошибка в меню изменения данных: {error}", exc_info=True)
            
    async def change_schedule_menu(self, schedule_data: dict):
        try:
            while True:
                await self.schedule_employees_ops.show_all_employees_by_schedule(
                        schedule_id=schedule_data['id'], 
                        shift_date_start=schedule_data['date'], 
                        department_name=schedule_data['name'], 
                        shift_type=schedule_data['shift_type']
                    )
                
                self.shift_type = schedule_data['shift_type']
                self.shift_start_time = schedule_data['start_time']
                self.current_schedule_id = schedule_data['id']
            
                print(f"\n{Fore.WHITE}Меню управления участком: {Fore.YELLOW}{schedule_data['name']}{Fore.WHITE}")
                print(f"(*) Дата: {schedule_data['date']}\n(*) Смена: {schedule_data['shift_type']}\n(*) Сотрудников: not set")
                print(f"\n1 - Добавить сотрудников\n2 - Изменить/Удалить сотрудников\n3 - Удалить всё расписание участка\n0 - Назад")
                
                choice = await self.helping_tools.menu_int_handler(">>> ", min_value=0, max_value=3)

                print(f"BEFORE FUNCTION: {self.current_schedule_id}")
                print(f"BEFORE FUCNTION, LOCAL: {schedule_data['id']}")
                if choice == 0:
                    break
                
                                
                elif choice == 1:
                    await self.create_arrangement(
                        department_name=schedule_data['name'], 
                        department_id=schedule_data['department_id'],
                        date=schedule_data['date']
                    )

                elif choice == 2:
                    await self.schedule_employees_ops.show_all_employees_by_schedule(
                        schedule_id=schedule_data['id'], 
                        shift_date_start=schedule_data['date'], 
                        department_name=schedule_data['name'], 
                        shift_type=schedule_data['shift_type']
                    )
                    
                    employee_name, employee_id = await self.schedule_employees_ops.employee_selector_by_schedule(
                        schedule_id=schedule_data['id']
                    )
                    
                    if employee_name == 0:
                        print(f"{Fore.YELLOW}(!) На участке нет сотрудников для изменения.{Fore.RESET}")
                        continue
                        
                    await self.change_employee_data_menu(
                        employee_name=employee_name, 
                        employee_id=employee_id, 
                        schedule_id=self.current_schedule_id, 
                        schedule_data=schedule_data
                    )

                elif choice == 3:
                    confirm = await self.helping_tools.menu_int_handler(f"{Fore.RED}(!) ВНИМАНИЕ: Это удалит весь участок и всех привязанных сотрудников. Подтвердить? (1 - Да, 2 - Нет): {Fore.RESET}", min_value=1, max_value=2)
                    if confirm == "1":
                        await self.schedule_base.delete_schedule(schedule_data['id'])
                        print(f"{Fore.GREEN}(✓) Расписание участка успешно удалено.{Fore.RESET}")
                        return
                    else:
                        print("(?) Удаление участка отменено.")
                        
                        
        except Exception as error:
            self.logger.error(f"Ошибка в change_schedule_menu: {error}", exc_info=True)

    async def change_arrangements_menu(self):
        try:
            # Выбираем расписание (участок + дата)
            schedule_data = await self.schedule_ops.schedule_selector()
            if not schedule_data:
                print("(?) Получен код выхода или неверный ввод.")
                return
            
            await self.change_schedule_menu(schedule_data=schedule_data)
            
        except Exception as error:
            self.logger.error(error, exc_info=True)
    
    async def drop_local_var_stats(self):
        self.department_id: int = 0
        self.department_name: str | None = None
        self.shift_type: str | None = None
        self.shift_start_time: str | None = None
        self.shift_start_date: str | None = None
        self.current_schedule_id: int | None = None
        
    async def create_arrangement_by_copying_another(self):
        await self.copy_schedule_to_new_date()
    
    async def create_new_arrangement_menu(self):
        while True:
            menu_choice: int = await self.helping_tools.menu_int_handler(lexicon.OUTER_ARRANGEMENT_MENU, min_value=0, max_value=3)
            if menu_choice == 0:
                break
            
            elif menu_choice == 1:
                self.shift_start_date: str = await DateOperations.date_selector()
            
            elif menu_choice == 2:
                await self.choose_department()
            
            elif menu_choice == 3:
                await self.create_arrangement(department_name=self.department_name, department_id=self.department_id, date=self.shift_start_date)

    
    async def create_arrangement_menu(self):
        await self.drop_local_var_stats()
        while True:
            menu_choice: int = await self.helping_tools.menu_int_handler(lexicon.CREATE_ARRANGEMENT_MENU, min_value=0, max_value=2)
            if menu_choice == 0:
                break
            
            elif menu_choice == 1:
                await self.create_arrangement_by_copying_another()
                
            elif menu_choice == 2:
                await self.create_new_arrangement_menu()
                
    async def menu(self):
        while True:
            menu_choice: int = await self.helping_tools.menu_int_handler(lexicon.INNER_ARRANGEMENT_MENU, min_value=0, max_value=2)
            if menu_choice == 0:
                break
            
            elif menu_choice == 1:
                await self.change_arrangements_menu()
            
            elif menu_choice == 2:
                await self.create_arrangement_menu()
        
if __name__ == "__main__":
    console_app = ConsoleApp()
    asyncio.run(console_app.main())