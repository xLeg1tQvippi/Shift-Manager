from db_operations.operations import EmployeeDatabase, DepartmentBase, JobBase, DataBaseOperations
from logging_configuration.logging_setup import setup_logging
from interfaces.console.main import ConsoleApp
from interfaces.gui_application.main import main_gui
# from interfaces.telegram_bot.main import ScheduleBot

from helping_tools import HelpingTools
import asyncio
import logging
import json
import dotenv, os


with open("db/employee_names.json", 'r', encoding='utf-8') as file:
    data: dict = json.load(file)

async def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    db_oper = DataBaseOperations()
    db = await db_oper.create_connection()
    helping_tools = HelpingTools()
    

    choose_interface = await helping_tools.menu_int_handler("Выберите интерфейс:\n1 - Консоль\n2 - Приложение\n>>> ")
    if choose_interface == 1:
        console_app = ConsoleApp(db=db)
        await console_app.arrangement_menu()
    elif choose_interface == 2:
        await main_gui(db=db)
    
    await db_oper.close_connection(db=db)


asyncio.run(main())