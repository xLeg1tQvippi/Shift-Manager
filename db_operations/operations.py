import aiosqlite
import asyncio
import logging
import bcrypt
from pydantic import ValidationError

from db_operations.validators import Validator
from lexicon_folder import DB_DATA

class DataBaseOperations:
    logger = logging.getLogger("DataBaseOperations")
    
    def __init__(self):
        pass
    
    @classmethod
    async def create_connection(cls) -> aiosqlite.Connection:
        # creates a DB connection
        try:
            db_connection: aiosqlite.Connection = await aiosqlite.connect(DB_DATA['db_path'])
            
            await db_connection.execute("SELECT 1")
            
            await db_connection.execute("PRAGMA journal_mode=WAL;")
            await db_connection.execute("PRAGMA foreign_keys = ON;")
            
            db_connection.row_factory = aiosqlite.Row
            
        except Exception as error:
            cls.logger.error("Connection to DB", exc_info=True)
            try:
                await db_connection.close()
            
            except Exception:
                cls.logger.info("unable to close db session.")
            
            raise ConnectionError("Unable to connect to Data Base")

        else:
            return db_connection
    
    @classmethod
    async def close_connection(cls, db: aiosqlite.Connection):
        try:
            await db.close()
        
        except Exception as error:
            cls.logger.error("error occured during closing DB connection.", exc_info=True)
        
        else:
            cls.logger.info("(>) db connection successfully closed.")
        
class EmployeeDatabase(DataBaseOperations):
    def __init__(self, db: aiosqlite.Connection):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.db = db
        
    async def get_employees_with_location(self, target_date: str):
        # Достаем ФИО, статы и название участка, если он есть на эту дату
        cursor = await self.db.execute("""
            SELECT e.user_id, e.first_name, e.last_name, e.middle_name, 
                   ea.status, ea.work_streak, ea.last_activity,
                   d.name as current_dept
            FROM employees e
            LEFT JOIN employee_attendance ea ON e.user_id = ea.user_id
            LEFT JOIN schedule_employees se ON e.user_id = se.user_id
            LEFT JOIN schedule s ON se.schedule_id = s.id AND s.date = ?
            LEFT JOIN departments d ON s.department_id = d.id
        """, (target_date,))
        return await cursor.fetchall()


    # function for gui only.
    async def get_employees_with_status(self):
        cursor = await self.db.execute("""
            SELECT e.user_id, e.first_name, e.last_name, e.middle_name, 
                ea.status, ea.work_streak, ea.last_activity
            FROM employees e
            LEFT JOIN employee_attendance ea ON e.user_id = ea.user_id
        """)
        return await cursor.fetchall()

    async def get_user_id_by_name(self, first_name: str, last_name: str = None, middle_name: str = None) -> int:
        try:
            cursor = await self.db.execute("""
                SELECT user_id FROM employees 
                WHERE first_name = ? AND last_name IS ? AND middle_name IS ? 
                LIMIT 1
            """, (first_name, last_name, middle_name))

            row = await cursor.fetchone()
            
            if row:
                return row['user_id']
            return None
        
        except Exception as error:
            self.logger.error(f"Ошибка при поиске ID пользователя: {error}")
            return None

    async def add_user(self, first_name: str, last_name: str = None, middle_name: str = None):
        try:            
            cursor = await self.db.execute(
                "INSERT INTO employees (first_name, last_name, middle_name) VALUES (?, ?, ?)",
                (first_name, last_name, middle_name)
            )
            await self.db.commit()
            return cursor.lastrowid 
        except Exception:
            self.logger.error("Ошибка при добавлении сотрудника", exc_info=True)
            return None

    # gui methods:

    async def get_employee_full_info(self, user_id: int):
        """Получаем всё о сотруднике для правки ФИО"""
        try:
            cursor = await self.db.execute("SELECT * FROM employees WHERE user_id = ?", (user_id,))
            return await cursor.fetchone()
        except Exception as e:
            self.logger.error(f"Ошибка получения инфо по ID {user_id}: {e}")
            return None

    async def update_employee_name(self, user_id: int, fn: str, ln: str, mn: str):
        """Обновляем ФИО сотрудника"""
        try:
            await self.db.execute("""
                UPDATE employees 
                SET first_name = ?, last_name = ?, middle_name = ? 
                WHERE user_id = ?
            """, (fn, ln, mn, user_id))
            await self.db.commit()
            return True
        except Exception as e:
            self.logger.error(f"Ошибка обновления ФИО: {e}")
            return False

    async def delete_employee_completely(self, user_id: int):
        """Полное удаление из базы (включая статы и историю)"""
        try:
            await self.db.execute("DELETE FROM employees WHERE user_id = ?", (user_id,))
            await self.db.execute("DELETE FROM employee_attendance WHERE user_id = ?", (user_id,))
            await self.db.execute("DELETE FROM employee_history WHERE user_id = ?", (user_id,))
            
            await self.db.commit()
            return True
        except Exception as e:
            self.logger.error(f"Ошибка удаления сотрудника {user_id}: {e}")
            return False

    async def get_employee_history(self, user_id: int):
        cursor = await self.db.execute("""
            SELECT work_date, department_name, job_place, shift_type 
            FROM employee_history 
            WHERE user_id = ? 
            ORDER BY work_date DESC LIMIT 10
        """, (user_id,))
        return await cursor.fetchall()

    async def get_full_data_for_report(self, schedule_id: int):
        try:
            cursor = await self.db.execute("""
                SELECT e.last_name, e.first_name, e.middle_name, 
                    se.job_place, se.start_time, se.shift_type
                FROM schedule_employees se
                JOIN employees e ON se.user_id = e.user_id
                WHERE se.schedule_id = ?
                -- ТЕПЕРЬ СОРТИРУЕМ ПО ТОМУ, ЧТО ТЫ ПЕРЕТАЩИЛ МЫШКОЙ
                ORDER BY se.sort_order ASC 
            """, (schedule_id,))
            return await cursor.fetchall()
        except Exception as e:
            self.logger.error(f"Ошибка получения данных для отчета: {e}")
            return []

    async def fetch_all_users(self) -> list:
        try:
            cursor = await self.db.execute("SELECT * FROM employees ORDER BY last_name ASC")
            return await cursor.fetchall()
        except Exception:
            return []

class JobBase(DataBaseOperations):
    def __init__(self, db: aiosqlite.Connection):
        super().__init__()
        self.db = db

    async def delete_job_position(self, job_name: str, department_id: int) -> bool:
        try:
            await self.db.execute(
                "DELETE FROM job_position WHERE job_name = ? AND department_id = ?",
                (job_name, department_id)
            )
            await self.db.commit()
            self.logger.info(f"Позиция '{job_name}' удалена для участка {department_id}")
            return True
        except Exception as error:
            self.logger.error(f"Ошибка удаления позиции: {error}")
            return False


    async def get_all_job_positions(self, department_id: int) -> dict:
        try:
            cursor = await self.db.execute("SELECT job_name FROM job_position WHERE department_id = ?",
                                           (department_id,))
            
            job_position_data = await cursor.fetchall()

            if not job_position_data:
                raise
            
        except Exception as error:
            self.logger.error(error)
            return []
        
        else:
            return job_position_data

    async def job_position_exists(self, job_position_name: str, department_id: int) -> bool:
        try:
            # Ищем СТРОГОЕ совпадение по имени И по ID участка
            cursor = await self.db.execute(
                'SELECT job_name FROM job_position WHERE job_name = ? AND department_id = ?',
                (job_position_name, department_id)
            )
            
            job_row = await cursor.fetchone()
            
            # Если нашли — значит такая позиция НА ЭТОМ участке уже есть
            if job_row:
                self.logger.info(f"Позиция '{job_position_name}' уже есть на участке {department_id}")
                return True
            
            return False
            
        except Exception:
            return False


    async def add_job_position(self, job_position_name: str, department_id: int) -> None | bool:
        try:
            job_existence_status: bool = await self.job_position_exists(job_position_name=job_position_name, department_id=department_id)
            self.logger.info(f"job_existence status: {job_existence_status}")

            if job_existence_status:
                return
            
            await self.db.execute("INSERT INTO job_position (job_name, department_id) VALUES (?, ?)",
                             (job_position_name, department_id))
            
            await self.db.commit()

            self.logger.info(f"job position '{job_position_name}' was successfully added to DB with ID: {department_id}.")
            
        except Exception as error:
            self.logger.error("error occured during job_position addition to DB.", exc_info=True)
            return None
        
        else:
            self.logger.info("Data was successfully updated to job position data.")
            return True
        
class DepartmentBase(DataBaseOperations):
    def __init__(self, db: aiosqlite.Connection):
        super().__init__()
        self.logger: logging = logging.getLogger(__name__)
        self.db = db
    
    async def get_all_departments(self) -> dict:
        try:
            cursor = await self.db.execute("SELECT id, name FROM departments")
            departments_data: dict = await cursor.fetchall()
            if not departments_data:
                raise
                
        except Exception as error:
            self.logger.error(error, exc_info=True)
            return None
        
        else:
            return departments_data
            
    async def get_department_id_by_name(self, department_name: str) -> int:
        try:            
            cursor = await self.db.execute("SELECT id FROM departments WHERE name = ?",
                                      (department_name,))
            
            department = await cursor.fetchone()
            if not department_name:
                self.logger.info(f"department with such name ({department_name}) does not exists in DB.")
                return 0
            
        except Exception:
            pass
        
        else:
            self.logger.info(f"department id with department name ({department_name}) was successfully fetched. (id: {department['id']})")
            return department['id']
    
    async def department_exists(self, department_name: str) -> bool:
        try:            
            cursor = await self.db.execute("SELECT name FROM departments WHERE name = ?",
                       (department_name,))

            data = await cursor.fetchone()
            if not data:
                raise

        except Exception:
            self.logger.info(f"department {department_name} does not exists in DB.")
            return False
    
        else:
            self.logger.info(f"(>) department {department_name} exists in DB (fetched from DB: {data['name']})")
            return True
                       
    async def add_department(self, department_name: str):
        try:
            if not await self.department_exists(department_name=department_name):                
                await self.db.execute("INSERT INTO departments (name) VALUES (?)",
                                 (department_name,))
                
                await self.db.commit()
                self.logger.info(f"(>) department {department_name} was successfully added to DB.")

        except Exception:
            self.logger.error(exc_info=True)
            

class ScheduleEmployeesBase(DataBaseOperations):
    def __init__(self, db: aiosqlite.Connection):
        super().__init__()
        self.logger: logging = logging.getLogger(__name__)
        self.db = db

    async def remove_from_all_schedules_on_date(self, user_id: int, target_date: str):
        try:
            # Удаляем записи, где ID расписания совпадает с датой
            await self.db.execute("""
                DELETE FROM schedule_employees 
                WHERE user_id = ? AND schedule_id IN (SELECT id FROM schedule WHERE date = ?)
            """, (user_id, target_date))
            await self.db.commit()
        except Exception as e:
            self.logger.error(f"Ошибка при очистке старых назначений: {e}")


    async def log_to_history(self, user_id: int, date: str, dept_name: str, job: str, shift: str):
        try:
            await self.db.execute("""
                INSERT INTO employee_history (user_id, work_date, department_name, job_place, shift_type)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, date, dept_name, job, shift))
            await self.db.commit()
            self.logger.info(f"Запись в историю для ID {user_id} добавлена.")
        except Exception as error:
            self.logger.error(f"Ошибка записи в историю: {error}")

    async def add_employee_to_schedule(self, schedule_id, user_id, job_place, start_time, shift_type, date, dept_name):
        # Добавляем shift_type в INSERT
        await self.db.execute("""
            INSERT INTO schedule_employees (schedule_id, user_id, job_place, start_time, shift_type)
            VALUES (?, ?, ?, ?, ?)
        """, (schedule_id, user_id, job_place, start_time, shift_type))
        
        await self.log_to_history(user_id, date, dept_name, job_place, shift_type)
        
    async def delete_employee_from_schedule(self, schedule_id: int, user_id: int, schedule_date: str):
        try:
            await self.db.execute(
                "DELETE FROM schedule_employees WHERE schedule_id = ? AND user_id = ?",
                (schedule_id, user_id)
            )

            import arrow
            today = arrow.now().format('YYYY-MM-DD')
            
            if schedule_date > today:
                await self.db.execute("""
                    DELETE FROM employee_history 
                    WHERE user_id = ? AND work_date = ?
                """, (user_id, schedule_date))
                print(f"🗑️ Будущая работа {schedule_date} удалена из истории {user_id}")

            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Ошибка при удалении: {e}")

    
    async def reset_all_job_places_to_all_employees(self, schedule_id: int):
        try:
            await self.db.execute("""
                UPDATE schedule_employees 
                SET job_place = NULL 
                WHERE schedule_id = ?
            """, (schedule_id,))
            
            await self.db.commit()
            self.logger.info(f"Positions for schedule {schedule_id} were successfully reset.")
            return True
            
        except Exception as error:
            self.logger.error(f"Error resetting job places: {error}", exc_info=True)
            return False
    
    async def update_all_employees_start_time(self, schedule_id: int, new_start_time: str):
        try:
            # Обновляем время начала у всех, кто привязан к этому ID расписания
            await self.db.execute("""
                UPDATE schedule_employees 
                SET start_time = ? 
                WHERE schedule_id = ?
            """, (new_start_time, schedule_id))
            
            await self.db.commit()
            self.logger.info(f"Время выхода обновлено для всех сотрудников в расписании {schedule_id}")
            return True
            
        except Exception as error:
            self.logger.error(f"Ошибка при массовом обновлении времени сотрудников: {error}", exc_info=True)
            return False

    async def copy_employees_between_schedules(self, from_id: int, to_id: int, target_date: str):
        try:
            await self.db.execute("""
                INSERT OR IGNORE INTO schedule_employees (schedule_id, user_id, job_place, start_time)
                SELECT ?, user_id, job_place, start_time
                FROM schedule_employees
                WHERE schedule_id = ?
            """, (to_id, from_id))


            await self.db.execute("""
                INSERT INTO employee_history (user_id, work_date, department_name, job_place, shift_type)
                SELECT se.user_id, ?, d.name, se.job_place, s.shift_type
                FROM schedule_employees se
                JOIN schedule s ON se.schedule_id = s.id
                JOIN departments d ON s.department_id = d.id
                WHERE se.schedule_id = ?
            """, (target_date, to_id))


            await self.db.execute("""
                UPDATE employee_attendance 
                SET work_streak = work_streak + 1,
                    status = 'Working',
                    last_activity = ?
                WHERE user_id IN (SELECT user_id FROM schedule_employees WHERE schedule_id = ?)
                AND (last_activity IS NULL OR last_activity < ?)
            """, (target_date, to_id, target_date))
            
            await self.db.commit()
            return True
        except Exception as error:
            self.logger.error(f"Ошибка массового копирования, истории и стриков: {error}")
            return False


    async def get_employee_current_info(self, schedule_id: int, user_id: int) -> dict[str, str | int]:
        try:
            cursor = await self.db.execute("""
                SELECT 
                    s.id as schedule_id, 
                    s.date as shift_start_date, 
                    d.name as department_name, 
                    s.shift_type, 
                    se.start_time as shift_start_time,
                    se.job_place
                FROM schedule s
                JOIN departments d ON s.department_id = d.id
                JOIN schedule_employees se ON s.id = se.schedule_id
                WHERE s.id = ? AND se.user_id = ?
            """, (schedule_id, user_id))
            
            row = await cursor.fetchone()
            if not row:
                return {}
        
        except Exception as error:
            self.logger.error(error)
            return {}
        else:
            self.logger.info("Data was successfully fetched from Database")
            return dict(row)
    
    async def move_employee(self, old_sid: int, new_sid: int, user_id: int):
        try:
            check = await self.db.execute(
                "SELECT 1 FROM schedule_employees WHERE schedule_id = ? AND user_id = ?",
                (new_sid, user_id)
            )
            if await check.fetchone():
                print(f"(!) Сотрудник уже записан в целевое расписание.")
                return False

            await self.db.execute("""
                UPDATE schedule_employees 
                SET schedule_id = ? 
                WHERE schedule_id = ? AND user_id = ?
            """, (new_sid, old_sid, user_id))
            
            await self.db.commit()
            return True
            
        except Exception as error:
            print(f"Ошибка при перемещении в БД: {error}")
            return False

    
    async def update_employee_in_schedule(self, job_place: str, start_time: str, schedule_id: int, user_id: int):
        try:
            await self.db.execute("""
                            UPDATE schedule_employees SET job_place = ?, start_time = ? WHERE schedule_id = ? AND user_id = ?
                            """, (job_place, start_time, schedule_id, user_id))

            await self.db.commit()
            
        except Exception as error:
            self.logger.error(error, exc_info=True)

    async def move_employee_to_new_schedule(self, schedule_id: int, user_id: int):
        try:
            await self.db.execute("""
                            UPDATE schedule_employees SET schedule_id = ? WHERE schedule_id = ? AND user_id = ?
                            """, (schedule_id, user_id))

            await self.db.commit()
            
        except Exception as error:
            self.logger.error(error, exc_info=True)
            
    async def get_all_employees_by_schedule(self, schedule_id: int) -> list:
        try:
        # Добавь ORDER BY в конец запроса:
            cursor = await self.db.execute("""
                SELECT e.user_id, e.first_name, e.last_name, e.middle_name, 
                    se.job_place, se.start_time, se.shift_type 
                FROM schedule_employees se
                JOIN employees e ON se.user_id = e.user_id
                WHERE se.schedule_id = ?
                ORDER BY se.sort_order ASC  -- ВОТ ТУТ ГЛАВНОЕ
            """, (schedule_id,))

            return await cursor.fetchall()
        except Exception as e:
            self.logger.error(f"Ошибка получения сотрудников: {e}")
            return []

class DayOffSetterBase(DataBaseOperations):
    def __init__(self, db: aiosqlite.Connection):
        super().__init__()
        self.logger: logging = logging.getLogger(__file__)
        self.db = db

    async def init_employee_stats(self, user_id: int):
        await self.db.execute("""
            INSERT OR IGNORE INTO employee_attendance (user_id, status, work_streak, last_activity)
            VALUES (?, 'Working', 0, NULL)
        """, (user_id,))
        await self.db.commit()

    async def put_employee_to_day_off(self, user_id: int):
        try:
            await self.init_employee_stats(user_id)
            await self.db.execute("""
                UPDATE employee_attendance 
                SET status = 'Day Off', 
                    work_streak = 0, 
                    last_activity = date('now')
                WHERE user_id = ?
            """, (user_id,))
            await self.db.commit()
            return True
        except Exception as error:
            self.logger.error(f"Ошибка при сбросе стрика (ID: {user_id}): {error}")
            return False

    async def increment_work_streak(self, user_id: int, shift_date: str):
        try:
            await self.init_employee_stats(user_id)
            await self.db.execute("""
                UPDATE employee_attendance 
                SET work_streak = work_streak + 1,
                    status = 'Working',
                    last_activity = ?
                WHERE user_id = ? AND (last_activity IS NULL OR last_activity < ?)
            """, (shift_date, user_id, shift_date))
            await self.db.commit()
        except Exception as error:
            self.logger.error(f"Ошибка при инкременте стрика (ID: {user_id}): {error}")

    async def get_employee_stats(self, user_id: int):
        cursor = await self.db.execute("""
            SELECT status, work_streak, last_activity 
            FROM employee_attendance WHERE user_id = ?
        """, (user_id,))
        employee_status = await cursor.fetchone()
        
        if not employee_status:
            return None
        
        else:
            return employee_status


class ScheduleBase(DataBaseOperations):
    def __init__(self, db: aiosqlite.Connection):
        super().__init__()
        self.logger: logging = logging.getLogger(__file__)
        self.db = db

    async def get_all_schedules_with_stats(self):
            """Возвращает список расписаний с подсчитанным количеством людей"""
            try:
                cursor = await self.db.execute("""
                    SELECT 
                        s.id, 
                        s.date, 
                        d.name, 
                        s.shift_type, 
                        s.start_time, 
                        s.department_id,
                        (SELECT COUNT(*) FROM schedule_employees WHERE schedule_id = s.id) as emp_count
                    FROM schedule s
                    JOIN departments d ON s.department_id = d.id
                    ORDER BY s.date DESC, d.name ASC
                """)
                return await cursor.fetchall()
            except Exception as e:
                self.logger.error(f"Ошибка получения расписаний со статистикой: {e}")
                return []
            
    async def get_schedules_by_date(self, target_date: str):
        try:
            cursor = await self.db.execute("""
                SELECT s.id, s.date, d.name, s.shift_type, d.id as department_id, 
                    s.start_time -- <--- ДОБАВИЛИ ЭТО ПОЛЕ
                FROM schedule s
                JOIN departments d ON s.department_id = d.id
                WHERE s.date = ?
                ORDER BY s.shift_type ASC, d.name ASC
            """, (target_date,))
            return await cursor.fetchall()
        except Exception as e:
            self.logger.error(f"Ошибка получения расписаний по дате: {e}")
            return []

    async def update_schedule_info(self, schedule_id: int, new_shift: str, new_time: str, date: str, department_id: int):
        try:
            await self.db.execute("""
                UPDATE schedule 
                SET shift_type = ?, start_time = ?, date = ?, department_id = ?
                WHERE id = ?
            """, (new_shift, new_time, date, department_id, schedule_id))
            
            await self.db.commit()
            self.logger.info(f"Расписание {schedule_id} обновлено: {new_shift} в {new_time}")
            return True
        except Exception as error:
            self.logger.error(f"Ошибка обновления расписания: {error}")
            return False


    async def duplicate_schedule_header(self, old_schedule_id: int, new_date: str):
        old_data = await self.get_schedule_by_id(old_schedule_id)
        
        await self.add_department_schedule(
            date=new_date,
            department_id=old_data['department_id'],
            shift_type=old_data['shift_type'],
            start_time=old_data['start_time'],
            end_time=old_data['end_time']
        )
        
        new_id = await self.get_schedule_id(date=new_date, department_id=old_data['department_id'], shift_type=old_data['shift_type'])
        
        return new_id

    async def get_schedule_by_id(self, schedule_id: int) -> aiosqlite.Row:
        try:
            cursor = await self.db.execute("""
                SELECT id, date, department_id, shift_type, start_time, end_time 
                FROM schedule 
                WHERE id = ?
            """, (schedule_id,))
            
            schedule_data = await cursor.fetchone()
            
            if schedule_data:
                return schedule_data
            
            else:
                self.logger.warning(f"(!) База данных: Расписание с ID {schedule_id} не найдено.")
                return None
                
        except Exception as error:
            self.logger.error(f"Ошибка при получении расписания по ID: {error}", exc_info=True)
            return None


    async def delete_schedule(self, schedule_id: int):
        try:
            await self.db.execute(
                "DELETE FROM schedule_employees WHERE schedule_id = ?", 
                (schedule_id,)
            )
            print("(!) База данных: Все сотрудники были удалены с текушей расстановки.")        
            await self.db.execute(
                "DELETE FROM schedule WHERE id = ?", 
                (schedule_id,)
            )
            print("(!) База данных: Данная расстановка была удалена из Базы данных.") 
                               
            await self.db.commit()
            self.logger.info(f"Schedule ID {schedule_id} and its employees were deleted.")
            return True
            
        except Exception as error:
            self.logger.error(f"Error deleting schedule: {error}", exc_info=True)
            return False

    async def get_schedule_id(self, date: str, department_id: int, shift_type: str) -> int | None:
        try:
            cursor = await self.db.execute("""
                             SELECT id
                             FROM schedule
                             WHERE department_id = ? AND date = ? AND shift_type = ?
                             """, (department_id, date, shift_type))

            schedule_id = await cursor.fetchone()
            
            if not schedule_id:
                raise
            
        except Exception as error:
            print(f"(!) Данного участка еще не создано на дату: {date}")
            return None
        
        else:
            self.logger.info("schedule id was successfully fetched from DB.")
            return schedule_id[0]

    async def check_if_schedule_exists(self, date: str, department_id: int, shift_type: str) -> bool:
        try:
            cursor = await self.db.execute("""
                                SELECT 1 FROM schedule 
                                WHERE date = ? AND department_id = ? AND shift_type = ?
                                """, (date, department_id, shift_type))
            
            schedule_exist = await cursor.fetchone()
            if schedule_exist:
                print(f"(!) Попытка создать участок, который уже существует на дату: {date} | смену: {shift_type}")
                return False
        
        except Exception as error:
            await self.logger.error(error, exc_info=True)

        else:
            return True
    
    async def add_department_schedule(self, date: str, department_id: int, shift_type: str, start_time: str, end_time: str = None):
        try:
            if await self.check_if_schedule_exists(date=date, department_id=department_id, shift_type=shift_type):
                await self.db.execute("""
                                INSERT INTO schedule (date, department_id, shift_type, start_time, end_time)
                                VALUES (?, ?, ?, ?, ?)
                                """, (date, department_id, shift_type, start_time, end_time))
            
                await self.db.commit()
            else:
                return False
        except Exception as error:
            self.logger.error(error, exc_info=True)
            
        else:
            self.logger.info("department successfully added to schedule.")
            print(f"(v) База данных: Расстановка успешно создана, разрешение добавление сотруднков: {True}")
            return True
            
    async def get_all_departments_schedule(self) -> dict:
        try:
            cursor = await self.db.execute("""
                SELECT DISTINCT 
                    s.id, 
                    s.date, 
                    d.name, 
                    d.id as department_id, 
                    s.shift_type, 
                    s.start_time, 
                    s.end_time 
                FROM schedule s
                JOIN departments d ON s.department_id = d.id
                ORDER BY s.id DESC
            """)
            
            schedule_data = await cursor.fetchall()

            if not schedule_data:
                raise
        
        except Exception as error:
            print("(!) База данных: Невозможно выбрать данные с участков, (Возможно вы не добавили ни один участок.)")
            return {}
            
        else:
            self.logger.info("successfuly fetched data")
            return schedule_data

    async def init_db(self):
        try:
            db = await self.create_connection()

            cursor = await db.execute("""
        SELECT se.id, se.date, se.shift_type, s.schedule_id, se.department_id, s.employee_id, e.first_name, e.last_name, d.name
        FROM schedule se
        JOIN schedule_employees s ON se.id = s.schedule_id
        JOIN employees e ON s.employee_id = e.user_id
        JOIN departments d ON se.department_id = d.id
    """)
            print("Таблица успешно создана!")
            data = await cursor.fetchall()
            for i in data:
                for b in i.keys():
                    print(b,i[b])
        except Exception as error:
            print(error)

        finally:
            await self.close_connection(db=db)
