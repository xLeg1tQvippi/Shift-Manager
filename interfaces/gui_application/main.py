import sys, os
import asyncio

os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QListWidget, QTableWidget, 
                             QTableWidgetItem, QPushButton, QLabel, QHeaderView, QListWidgetItem,
                             QDialog, QFormLayout, QLineEdit, QComboBox, QTimeEdit, QDialogButtonBox, QGridLayout, QFrame, QMenu,
                             QDateEdit, QMessageBox, QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QScrollArea, QCheckBox, QAbstractItemView)

from PyQt6.QtCore import Qt, QTime, QDate, QTimer
from PyQt6.QtGui import QAction, QCursor, QFont, QPixmap, QPainter, QColor, QPen
from qasync import QEventLoop, asyncSlot
import aiosqlite
import arrow

from helping_tools import HelpingTools
import logging
from db_operations.operations import EmployeeDatabase, DepartmentBase, JobBase, DataBaseOperations, ScheduleBase, ScheduleEmployeesBase, DayOffSetterBase
from core.employees_arrangement import EmployeeOperations, DepartmentOperations, JobPlaceOperations, CompleterInputController, DateOperations, ScheduleOperations, ScheduleEmployeesOperations
from interfaces.console.main import ArrangementCreator


class MainWindow(QMainWindow):
    def __init__(self, db: aiosqlite.Connection):
        super().__init__()
        self.db = db
        self.setWindowTitle("Shift Manager GUI")
        self.resize(1100, 700)

        # --- ИНИЦИАЛИЗАЦИЯ ОПЕРАЦИЙ ---
        self.logger: logging = logging.getLogger(__name__)    
        self.employee_ops = EmployeeOperations(db=db)
        self.department_ops = DepartmentOperations(db=db)
        self.job_ops = JobPlaceOperations(db=db)
        self.schedule_employees_base = ScheduleEmployeesBase(db=db)
        self.schedule_base = ScheduleBase(db=db)
        self.helping_tools = HelpingTools()
        self.employee_base = EmployeeDatabase(db=db)
        self.schedule_ops = ScheduleOperations(db=db)
        self.schedule_employees_ops = ScheduleEmployeesOperations(db=db)
        self.day_off_setter_base = DayOffSetterBase(db=db)
        self.arrangement_creator = ArrangementCreator(
            employee_ops=self.employee_ops, job_ops=self.job_ops, 
            department_ops=self.department_ops, schedule_employees_base=self.schedule_employees_base, 
            schedule_base=self.schedule_base, schedule_ops=self.schedule_ops, 
            schedule_employees_ops=self.schedule_employees_ops, day_off_setter_base=self.day_off_setter_base
        )

        # --- ИНТЕРФЕЙС ---
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)

        # --- ЛЕВАЯ КОЛОНКА: Расписания ---
        self.left_layout = QVBoxLayout()
        self.label_schedules = QLabel("<b>📅 Доступные расписания</b>")
        
        self.list_schedules = QListWidget()
        self.list_schedules.itemClicked.connect(self.on_schedule_selected)
        self.list_schedules.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_schedules.customContextMenuRequested.connect(self.show_schedule_context_menu)
        
        self.btn_refresh = QPushButton("Обновить список")
        self.btn_refresh.clicked.connect(self.refresh_schedules)
        
        self.btn_employees = QPushButton("База сотрудников")
        self.btn_employees.clicked.connect(lambda: asyncio.create_task(self.open_employee_manager()))
        
        self.left_layout.addWidget(self.label_schedules)
        self.left_layout.addWidget(self.list_schedules)
        self.left_layout.addWidget(self.btn_refresh)
        self.left_layout.addWidget(self.btn_employees)

        # --- ПРАВАЯ КОЛОНКА: Состав участка ---
        self.right_layout = QVBoxLayout()
        self.label_title = QLabel("<b>👥 Состав участка</b>")

        # 1. Поле поиска (фильтр таблицы)
        self.name_filter = QLineEdit()
        self.name_filter.setPlaceholderText("🔍 Поиск по списку участка...")
        self.name_filter.setClearButtonEnabled(True)
        self.name_filter.textChanged.connect(self.filter_employees_in_table)

        # 2. Таблица сотрудников
        self.table_employees = QTableWidget()
        self.table_employees.setColumnCount(5)
        self.table_employees.setHorizontalHeaderLabels(["Сотрудник", "Позиция", "Время", "Смена", "ID"])
        self.table_employees.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_employees.setColumnHidden(3, True) 
        self.table_employees.setColumnHidden(4, True)
        
        self.table_employees.setDragEnabled(True)
        self.table_employees.setAcceptDrops(True)
        self.table_employees.setDragDropOverwriteMode(False)
        self.table_employees.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_employees.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_employees.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.table_employees.setDefaultDropAction(Qt.DropAction.MoveAction)
        
        self.table_employees.model().rowsMoved.connect(
            lambda: asyncio.create_task(self.save_new_order())
        )
        self.table_employees.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_employees.customContextMenuRequested.connect(self.show_context_menu)

        # --- СБОРКА ПРАВОЙ КОЛОНКИ ---
        self.right_layout.addWidget(self.label_title)
        self.right_layout.addWidget(self.name_filter)
        self.right_layout.addWidget(self.table_employees)

        # Установка растяжения, чтобы таблица была большой, а поиск узким
        self.right_layout.setStretch(0, 0) # Заголовок
        self.right_layout.setStretch(1, 0) # Поиск
        self.right_layout.setStretch(2, 1) # Таблица (забирает всё место)

        # 3. Кнопки действий (Добавить, Изменить, Удалить)
        self.actions_layout = QHBoxLayout()
        self.btn_add = QPushButton("(+) Добавить")
        self.btn_edit = QPushButton("(>) Изменить")
        self.btn_del = QPushButton("(x) Удалить участок")
        
        self.btn_edit.clicked.connect(lambda: asyncio.create_task(self.edit_selected_employee()))
        self.btn_add.clicked.connect(lambda: self.add_employee_to_current_schedule())
        self.btn_del.clicked.connect(lambda: asyncio.create_task(self.delete_current_schedule()))
        
        self.actions_layout.addWidget(self.btn_add)
        self.actions_layout.addWidget(self.btn_edit)
        self.actions_layout.addWidget(self.btn_del)
        self.right_layout.addLayout(self.actions_layout)

        # 4. Кнопки отчетов (Копировать)
        self.report_layout = QHBoxLayout()
        self.btn_copy_text = QPushButton("Копировать текстом")
        self.btn_copy_img = QPushButton("Копировать фото")
        self.btn_copy_text.clicked.connect(lambda: self.open_smart_report())
        self.btn_copy_img.clicked.connect(self.copy_as_excel_style_image)
        self.report_layout.addWidget(self.btn_copy_text)
        self.report_layout.addWidget(self.btn_copy_img)
        self.right_layout.addLayout(self.report_layout)

        # --- ОБЪЕДИНЕНИЕ КОЛОНОК ---
        self.main_layout.addLayout(self.left_layout, 1)
        self.main_layout.addLayout(self.right_layout, 3) # Правая колонка в 3 раза шире левой

    # Не забудь добавить этот метод в класс, чтобы поиск работал:

    def filter_employees_in_table(self, text):
        search_text = text.lower().strip()
        
        # Отключаем Drag&Drop при поиске, чтобы случайно не перемешать скрытые строки
        self.table_employees.setDragEnabled(not bool(search_text))

        for row in range(self.table_employees.rowCount()):
            # Индекс 0 — это колонка "Сотрудник"
            item = self.table_employees.item(row, 0)
            if item:
                # Если текст поиска есть в имени — показываем строку, иначе скрываем
                is_match = search_text in item.text().lower()
                self.table_employees.setRowHidden(row, not is_match)


    async def save_new_order(self):
        current = self.list_schedules.currentItem()
        if not current: return
        schedule_id = current.data(Qt.ItemDataRole.UserRole)['id']
        
        try:
            # Проходим по всем строкам таблицы в их новом порядке
            for row in range(self.table_employees.rowCount()):
                # Берем ID из нашей скрытой 4-й колонки
                emp_id_item = self.table_employees.item(row, 4)
                if emp_id_item:
                    emp_id = int(emp_id_item.text())
                    # Обновляем порядковый номер в базе
                    self.db.execute("""
                        UPDATE schedule_employees 
                        SET sort_order = ? 
                        WHERE schedule_id = ? AND user_id = ?
                    """, (row, schedule_id, emp_id))
            
            await self.db.commit()
            print(">>> Порядок сотрудников сохранен")
            
        except Exception as e:
            print(f"Ошибка сохранения порядка: {e}")


    def show_copy_options_menu(self):
        menu = QMenu(self)
        
        act_single = QAction("📄 Только текущий участок", self)
        act_single.triggered.connect(lambda: asyncio.create_task(self.copy_schedule_to_clipboard()))
        
        act_multi = QAction("📊 Сводный отчет (несколько)", self)
        act_multi.triggered.connect(lambda: asyncio.create_task(self.create_multi_report_gui()))
        
        menu.addAction(act_single)
        menu.addAction(act_multi)
        
        menu.exec(QCursor.pos())


    def copy_as_excel_style_image(self):
        # 1. Данные
        rows = self.table_employees.rowCount()
        cols = 3 
        
        if rows == 0: return

        # 2. Создаем "Призрачную" таблицу
        temp_table = QTableWidget(rows, cols)
        temp_table.setHorizontalHeaderLabels(["Сотрудник", "Рабочее место", "Время"])
        
        # --- УБИРАЕМ ПОЛЗУНКИ ---
        temp_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        temp_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        temp_table.verticalHeader().setVisible(False)
        temp_table.setFrameStyle(0) # Убираем рамку самого виджета, рисуем свою

        # --- СТИЛЬ "ЗЕЛЕНЫЙ EXCEL" ---
        temp_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #D4D4D4;
                background-color: white;
                selection-background-color: white;
                color: black;
                border: 1px solid #D4D4D4;
            }
            QHeaderView::section {
                background-color: #217346; /* Тот самый зеленый Excel */
                color: white;              /* Белый текст */
                padding: 6px;
                border: 1px solid #107C41;
                font-weight: bold;
            }
        """)
        
        font = QFont("Segoe UI", 10) # Или Calibri
        temp_table.setFont(font)
        temp_table.horizontalHeader().setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))

        # 3. Заполняем данные
        for r in range(rows):
            for c in range(cols):
                cell = self.table_employees.item(r, c)
                text = cell.text() if cell else ""
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                temp_table.setItem(r, c, item)
        
        # Настройка размеров колонок
        temp_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        temp_table.resizeColumnsToContents()
        temp_table.resizeRowsToContents()
        
        # Расчет геометрии (с небольшим запасом, чтобы не было ползунков)
        width = temp_table.horizontalHeader().length() + 2
        height = temp_table.verticalHeader().length() + temp_table.horizontalHeader().height() + 2
        temp_table.setFixedSize(width + 10, height + 10) 

        # Проявляем в памяти
        temp_table.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        temp_table.show()

        # 4. Рисование финальной картинки
        current_data = self.list_schedules.currentItem().data(Qt.ItemDataRole.UserRole)
        header_text = f"{current_data['name']} | {current_data['date']} | {'Дневная' if current_data['shift_type'] == "Day" else "Ночная"}"
        
        final_img = QPixmap(width + 60, height + 100)
        final_img.fill(QColor("white"))
        
        painter = QPainter(final_img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Рисуем красивый заголовок
        painter.setPen(QPen(QColor("#217346"))) # Зеленый текст заголовка
        painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        painter.drawText(30, 45, header_text)
        
        # Рисуем таблицу
        painter.translate(30, 70)
        temp_table.render(painter)
        painter.end()

        # 5. Копируем в буфер
        QApplication.clipboard().setPixmap(final_img)
        
        temp_table.close()
        print("✅ Зеленая Excel-расстановка в буфере!")

    def get_data_from_table(self):
        """Собирает данные прямо из виджета таблицы в том порядке, который видит пользователь"""
        report_data = []
        for row in range(self.table_employees.rowCount()):
            # Пропускаем скрытые строки (если включен фильтр)
            if self.table_employees.isRowHidden(row):
                continue
                
            name = self.table_employees.item(row, 0).text()
            job = self.table_employees.item(row, 1).text()
            time = self.table_employees.item(row, 2).text()
            shift = self.table_employees.item(row, 3).text()
            
            # Сохраняем в виде словаря или кортежа, как тебе удобно для отчета
            report_data.append({
                'name': name,
                'job_place': job,
                'start_time': time,
                'shift_type': shift
            })
        return report_data


    @asyncSlot()
    async def copy_schedule_to_clipboard(self):
        # 1. Проверяем, выбрано ли расписание
        current_item = self.list_schedules.currentItem()
        if not current_item: 
            print("(!) Сначала выберите расписание")
            return
            
        schedule_info = current_item.data(Qt.ItemDataRole.UserRole)
        
        # 2. Собираем данные ПРЯМО ИЗ ТАБЛИЦЫ (как они стоят на экране)
        report_lines = []
        report_lines.append(f"📋 Расстановка: {schedule_info['name']} ({schedule_info['date']})")
        report_lines.append("-" * 30)

        for row in range(self.table_employees.rowCount()):
            # Если хочешь копировать даже скрытые поиском строки — убирай проверку isRowHidden
            # if self.table_employees.isRowHidden(row): continue 

            name = self.table_employees.item(row, 0).text()
            job = self.table_employees.item(row, 1).text()
            time = self.table_employees.item(row, 2).text()
            
            # Формируем строку (например: 1. Аминева К. (Вакуум) - 08:00)
            line = f"{row + 1}. {name} ({job}) - {time}"
            report_lines.append(line)

        # 3. Соединяем всё в один текст
        final_text = "\n".join(report_lines)

        # 4. Копируем в буфер обмена
        clipboard = QApplication.clipboard()
        clipboard.setText(final_text)
        
        print("✅ Данные скопированы в буфер обмена в текущем порядке!")


    def get_short_name(self, emp):
        
        emp = dict(emp) if not isinstance(emp, dict) else emp
        
        last = emp.get('last_name') or ""
        first = emp.get('first_name') or ""
        middle = emp.get('middle_name') or ""

        name_parts = [last]
        
        # Если есть имя — берем первую букву и точку
        if len(last + first + middle) <= 12:
            return " ".join([last, first, middle])
        
        if first:
            name_parts.append(f"{first[0]}.")
            
        # Если есть отчество — берем первую букву и точку
        if middle:
            name_parts.append(f"{middle[0]}.")
            
        return " ".join(name_parts).strip()



    async def open_employee_manager(self):
        dialog = EmployeeManagerDialog(self.employee_ops, self.employee_base, self)
        await dialog.init_list()
        dialog.show()

    # @asyncSlot()
    async def replace_employee_gui(self):
        selected = self.table_employees.selectedItems()
        if not selected: return
        
        row = selected[0].row()
        old_emp_id = int(self.table_employees.item(row, 4).text()) 
        old_emp_name = self.table_employees.item(row, 0).text()
        old_job = self.table_employees.item(row, 1).text()
        old_time = self.table_employees.item(row, 2).text()
        
        current_item = self.list_schedules.currentItem()
        schedule_data = current_item.data(Qt.ItemDataRole.UserRole)

        all_employees_dict = await self.employee_base.get_employees_with_status()
        current_employees = await self.schedule_employees_base.get_all_employees_by_schedule(schedule_data['id'])
        current_ids = [emp['user_id'] for emp in current_employees]

        select_dialog = AddEmployeeDialog(all_employees_dict, current_ids, self)
        if select_dialog.exec():
            new_name, new_id = select_dialog.get_selected()
            if not new_id: return

            # 2. Шаг: Спрашиваем, что сделать с ТЕМ, КОГО ЗАМЕНИЛИ
            from PyQt6.QtWidgets import QMessageBox
            msg = QMessageBox(self)
            msg.setWindowTitle(f"Куда переставить {old_emp_name}")
            msg.setText(f"<center>Меню сотрудника</center>\n<center>{old_emp_name}</center>")
            
            btn_day_off = msg.addButton("На выходной", QMessageBox.ButtonRole.ActionRole)
            btn_remove = msg.addButton("Временно убрать", QMessageBox.ButtonRole.ActionRole)
            btn_cancel = msg.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
            
            msg.exec()

            if msg.clickedButton() == btn_cancel:
                return

            # 3. Шаг: Выполняем действия в БД
            # А) Убираем старого
            if msg.clickedButton() == btn_day_off:
                await self.day_off_setter_base.put_employee_to_day_off(old_emp_id)
                await self.schedule_employees_base.delete_employee_from_schedule(schedule_data['id'], old_emp_id, schedule_date=schedule_data['date'])
            else:
                await self.schedule_employees_base.delete_employee_from_schedule(schedule_data['id'], old_emp_id, schedule_date=schedule_data['date'])

            await self.schedule_employees_base.add_employee_to_schedule(
                schedule_id=schedule_data['id'],
                user_id=new_id,
                job_place=old_job if old_job != "—" else None,
                start_time=old_time,
                date=schedule_data['date'],
                dept_name=schedule_data['name'],
                shift_type=schedule_data['shift_type']
            )

            
            # В) Обновляем стрик новому
            await self.day_off_setter_base.increment_work_streak(new_id, schedule_data['date'])

            # 4. Обновляем интерфейс
            await self.on_schedule_selected(current_item)
            print(f"(✓) Замена произведена: {old_emp_name} -> {new_name}")


    async def edit_schedule_params(self, current_data: dict):
        try:
            all_depts = await self.department_ops.get_all_departments()
            dialog = ScheduleDialog(all_depts, current_data=current_data, parent=self)
            
            if dialog.exec():
                res = dialog.get_data()
                
                # 1. Обновляем основную таблицу расписания
                await self.schedule_base.update_schedule_info(
                    schedule_id=current_data['id'],
                    date=res['date'],
                    department_id=res['dept_id'],
                    new_shift=res['shift'],
                    new_time=res['time'] 
                )
                
                # 2. ПРОВЕРКА: Изменился ли участок?
                if int(current_data['department_id']) != int(res['dept_id']):
                    reply_dept = QMessageBox.question(
                        self, 'Смена участка', 
                        "Вы изменили участок. Сбросить рабочие позиции у всех сотрудников?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply_dept == QMessageBox.StandardButton.Yes:
                        await self.schedule_employees_base.reset_all_job_places_to_all_employees(current_data['id'])
                        print("(✓) Позиции сотрудников сброшены из-за смены участка.")

                # 3. ПРОВЕРКА: Изменилось ли время?
                if current_data['start_time'] != res['time']:
                    reply_time = QMessageBox.question(
                        self, 'Синхронизация', 
                        "Обновить время выхода всем сотрудникам на этом участке?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply_time == QMessageBox.StandardButton.Yes:
                        await self.schedule_employees_base.update_all_employees_start_time(
                            current_data['id'], res['time']
                        )

                print(f"(✓) Параметры расстановки #{current_data['id']} обновлены.")
                await self.refresh_schedules()
                
        except Exception as e:
            self.logger.error(f"Ошибка при изменении параметров расстановки: {e}", exc_info=True)


    async def delete_current_schedule(self):
        # 1. Получаем выбранный элемент из списка слева
        current_item = self.list_schedules.currentItem()
        if not current_item:
            print("(!) Ничего не выбрано для удаления")
            return

        schedule_data = current_item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self, 'Удаление', 
            f"Вы уверены, что хотите полностью удалить расстановку участка\n'{schedule_data['name']}' на {schedule_data['date']}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Используем твой готовый метод из базы
            await self.schedule_base.delete_schedule(schedule_data['id'])
            print(f"(✓) Участок {schedule_data['name']} удален.")
            
            # Обновляем интерфейс
            await self.refresh_schedules()
            self.table_employees.setRowCount(0)
            self.label_title.setText("<b>👥 Состав участка</b>")

    async def copy_schedule_gui(self, source_schedule_data: dict):
            try:
                # 1. Спрашиваем дату через маленькое окошко с календарем
                from PyQt6.QtWidgets import QDialog, QVBoxLayout, QDateEdit, QDialogButtonBox
                from PyQt6.QtCore import QDate

                dialog = QDialog(self)
                dialog.setWindowTitle("Копировать на дату")
                l = QVBoxLayout(dialog)
                
                date_inp = QDateEdit()
                date_inp.setCalendarPopup(True)
                date_inp.setDate(QDate.currentDate())
                l.addWidget(date_inp)
                
                btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
                btns.accepted.connect(dialog.accept)
                btns.rejected.connect(dialog.reject)
                l.addWidget(btns)

                if dialog.exec():
                    target_date = date_inp.date().toString("yyyy-MM-dd")
                    
                    # 2. Вызываем твою логику копирования (шапка + люди)
                    new_id = await self.schedule_base.duplicate_schedule_header(
                        old_schedule_id=source_schedule_data['id'], 
                        new_date=target_date
                    )

                    await self.schedule_employees_base.copy_employees_between_schedules(
                        from_id=source_schedule_data['id'], 
                        to_id=new_id,
                        target_date=target_date
                    )
                    
                    print(f"(✓) Скопировано на {target_date}")
                    await self.refresh_schedules()

            except Exception as e:
                self.logger.error(f"Ошибка копирования в GUI: {e}", exc_info=True)

    async def create_new_schedule_gui(self):
        all_depts = await self.department_ops.get_all_departments() 

        dialog = ScheduleDialog(all_depts, parent=self)
        if dialog.exec():
            res = dialog.get_data()
            
            def_time = "08:00" if res['shift'] == "Day" else "20:00"
            
            await self.schedule_base.add_department_schedule(
                date=res['date'],
                department_id=res['dept_id'],
                shift_type=res['shift'],
                start_time=def_time
            )
            
            await self.refresh_schedules()
            print(f"Создано расписание на {res['date']}")

    async def open_job_editor(self, schedule_data):
        self.job_editor = JobPositionsEditorDialog(
            department_name=schedule_data['name'],
            department_id=schedule_data['department_id'],
            job_ops=self.job_ops,
            parent=self
        )
        await self.job_editor.load_jobs()
        self.job_editor.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.job_editor.show()



    def show_schedule_context_menu(self, position):
        menu = QMenu(self)
        item = self.list_schedules.itemAt(position)

        if item:
            data = item.data(Qt.ItemDataRole.UserRole)
            
            act_edit = QAction("(>) Изменить параметры (Дата/Смена)", self)
            act_copy = QAction("(<) Копировать на другую дату", self)
            act_manage_jobs = QAction("(>) Управление позициями участка", self)
            act_del = QAction("(x) Удалить расстановку", self)
            
            act_manage_jobs.triggered.connect(lambda: asyncio.create_task(self.open_job_editor(data)))
            act_edit.triggered.connect(lambda: asyncio.create_task(self.edit_schedule_params(data)))
            act_copy.triggered.connect(lambda: asyncio.create_task(self.copy_schedule_gui(data)))
            act_del.triggered.connect(lambda: asyncio.create_task(self.delete_current_schedule()))

            menu.addAction(act_edit)
            menu.addAction(act_copy)
            menu.addAction(act_manage_jobs)
            menu.addSeparator()
            menu.addAction(act_del)
        else:
            act_add = QAction("(+) Создать новую расстановку", self)
            act_add.triggered.connect(lambda: asyncio.create_task(self.create_new_schedule_gui()))
            menu.addAction(act_add)

        menu.exec(QCursor.pos())


    def show_context_menu(self, position):
        index = self.table_employees.indexAt(position)
        if not index.isValid():
            return

        menu = QMenu(self)

        # Создаем действия
        action_edit = QAction("(>) Открыть карточку (Изменить)", self)
        action_day_off = QAction("(*) Отправить на выходной", self)
        action_replace = QAction("(*) Заменить сотрудника", self)
        action_remove = QAction("(x) Убрать из списка", self)

        # Подключаем их (здесь это нормально, так как menu локальное и удалится)
        action_edit.triggered.connect(lambda: asyncio.create_task(self.edit_selected_employee()))
        action_day_off.triggered.connect(lambda: asyncio.create_task(self.quick_day_off()))
        action_remove.triggered.connect(lambda: asyncio.create_task(self.quick_remove()))
        action_replace.triggered.connect(lambda: asyncio.create_task(self.replace_employee_gui()))

        # Добавляем в меню
        menu.addAction(action_edit)
        menu.addSeparator()
        menu.addAction(action_day_off)
        menu.addAction(action_replace)
        menu.addAction(action_remove)

        # Показываем
        menu.exec(self.table_employees.viewport().mapToGlobal(position))

    async def quick_remove(self):
        selected = self.table_employees.selectedItems()
        
        if not selected: 
            return
        
        row = selected[0].row() 
        
        emp_name = self.table_employees.item(row, 0).text()
        emp_id = int(self.table_employees.item(row, 4).text()) 
        
        current_schedule = self.list_schedules.currentItem().data(Qt.ItemDataRole.UserRole)

        await self.schedule_employees_base.delete_employee_from_schedule(current_schedule['id'], emp_id, schedule_date=current_schedule['date'])
        
        await self.on_schedule_selected(self.list_schedules.currentItem())
        print(f"Сотрудник {emp_name} удален")

    async def quick_day_off(self):
        selected = self.table_employees.selectedItems()
        if not selected: return
        
        row = selected[0].row()
        emp_id = int(self.table_employees.item(row, 4).text()) 
        emp_name = self.table_employees.item(row, 0).text()
        current_schedule = self.list_schedules.currentItem().data(Qt.ItemDataRole.UserRole)

        await self.day_off_setter_base.put_employee_to_day_off(emp_id)
        await self.schedule_employees_base.delete_employee_from_schedule(current_schedule['id'], emp_id, current_schedule['date'])
        
        await self.on_schedule_selected(self.list_schedules.currentItem())
        print(f"Сотрудник {emp_name} отправлен на выходной через ПКМ")




    # @asyncSlot()
    @asyncSlot()
    async def add_employee_to_current_schedule(self):
        # 1. Замок от повторных нажатий
        if not self.btn_add.isEnabled(): 
            return 
        
        current_item = self.list_schedules.currentItem()
        if not current_item:
            print("(!) Ошибка: Сначала выберите расписание!")
            return

        self.btn_add.setEnabled(False) 
        print('>>> Начало процесса добавления')

        try:
            # Цикл нужен, чтобы при создании нового сотрудника (777) диалог выбора открывался снова
            while True:
                schedule_data = current_item.data(Qt.ItemDataRole.UserRole)
                
                # Загружаем данные
                all_employees_data = await self.employee_base.get_employees_with_location(schedule_data['date'])
                current_employees = await self.schedule_employees_base.get_all_employees_by_schedule(schedule_data['id'])
                current_ids = [emp['user_id'] for emp in current_employees]

                # Открываем диалог выбора
                dialog = AddEmployeeDialog(all_employees_data, current_ids, self)
                result = dialog.exec()

                # --- СЦЕНАРИЙ А: СОЗДАНИЕ НОВОГО (777) ---
                if result == 777:
                    new_emp_data = dialog.new_emp_data
                    new_id = await self.employee_base.add_user(
                        new_emp_data['fn'], new_emp_data['ln'], new_emp_data['mn']
                    )
                    if new_id:
                        await self.day_off_setter_base.init_employee_stats(new_id)
                        print(f"✅ Сотрудник {new_emp_data['ln']} создан. Возврат к выбору...")
                        continue # Возвращаемся в начало цикла while, чтобы снова открыть выбор уже с новым сотрудником
                    break # Если не удалось создать, выходим

                # --- СЦЕНАРИЙ Б: ОТМЕНА ---
                if result != QDialog.DialogCode.Accepted:
                    break

                # --- СЦЕНАРИЙ В: ОБЫЧНЫЙ ВЫБОР ---
                name, eid = dialog.get_selected()
                if not (name and eid):
                    break

                # Проверка на занятость на другом участке
                if "📍 Занят:" in name:
                    from PyQt6.QtWidgets import QMessageBox
                    clean_name = name.split('|')[0].strip()
                    reply = QMessageBox.question(
                        self, "Перенос сотрудника",
                        f"Сотрудник {clean_name} уже стоит на другом участке.\nПеренести сюда?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        await self.schedule_employees_base.remove_from_all_schedules_on_date(eid, schedule_data['date'])
                    else:
                        break # Пользователь отказался

                # Подготовка данных для карточки
                emp_data = {
                    "id": eid, 
                    "name": name.split('|')[0].strip(),
                    "job": "—", 
                    "time": schedule_data['start_time'],
                    "shift_type": schedule_data['shift_type'] if schedule_data['shift_type'] != "Mixed" else "Day"
                }
                
                stats = await self.day_off_setter_base.get_employee_stats(eid)
                available_jobs = await self.job_ops.create_job_position_dict(schedule_data['department_id'])
                
                # Финальная настройка в карточке
                card = EmployeeCardDialog(emp_data, stats, available_jobs, self)
                if card.exec():
                    final_data = card.get_data()
                    
                    await self.schedule_employees_base.add_employee_to_schedule(
                        schedule_id=schedule_data['id'],
                        user_id=eid,
                        job_place=final_data['job'],
                        start_time=final_data['time'],
                        date=schedule_data['date'],
                        dept_name=schedule_data['name'],
                        shift_type=final_data['shift']
                    )

                    await self.day_off_setter_base.increment_work_streak(eid, schedule_data['date'])
                    
                    # ОБНОВЛЕНИЕ GUI
                    # Важно: вызываем последовательно, чтобы избежать конфликтов индексов
                    await self.on_schedule_selected(current_item)
                    await self.refresh_schedules()
                
                break # Выходим из while после успешного завершения

        except Exception as error:
            print(f"Критическая ошибка: {error}")
            import traceback
            traceback.print_exc()
        finally:
            self.btn_add.setEnabled(True)
            print('>>> Кнопка "Добавить" снова активна')


    @asyncSlot()
    async def refresh_schedules(self):
        # 1. ЗАПОМИНАЕМ ТЕКУЩИЙ ВЫБОР (перед очисткой)
        selected_id = None
        current_item = self.list_schedules.currentItem()
        if current_item:
            current_data = current_item.data(Qt.ItemDataRole.UserRole)
            if current_data:
                # Используем id расписания как уникальный маркер
                selected_id = current_data.get('id') 

        # 2. ОЧИЩАЕМ СПИСОК
        self.list_schedules.clear()
        
        # 3. ПОЛУЧАЕМ ДАННЫЕ
        schedules = await self.schedule_base.get_all_schedules_with_stats()
        
        import arrow
        now = arrow.now()
        today = now.format('YYYY-MM-DD')
        yesterday = now.shift(days=-1).format('YYYY-MM-DD')
        tomorrow = now.shift(days=+1).format('YYYY-MM-DD')

        groups = {"Завтра": [], "Сегодня": [], "Вчера": [], "Ранее": []}
        
        for s in schedules:
            if s['date'] == tomorrow: groups["Завтра"].append(s)
            elif s['date'] == today: groups["Сегодня"].append(s)
            elif s['date'] == yesterday: groups["Вчера"].append(s)
            else: groups["Ранее"].append(s)

        # 4. ЗАПОЛНЯЕМ СПИСОК ЗАНОВО
        for label, items in groups.items():
            if not items: 
                continue
            
            # Добавляем разделитель группы
            header = QListWidgetItem(f"--- {label} ---")
            header.setFlags(Qt.ItemFlag.NoItemFlags) # Не кликабельно
            header.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            header.setForeground(Qt.GlobalColor.darkGray)
            self.list_schedules.addItem(header)

            for row in items:
                
                s = dict(row)
                # Формируем иконку смены
                shift_type = s.get('shift_type')
                if shift_type == "Day": 
                    shift_icon = "(День)"
                elif shift_type == "Night": 
                    shift_icon = "(Ночь)"
                else: 
                    shift_icon = "(Смешанная)"
                
                # Текст элемента
                date_str = f"{s['date'][8:]}.{s['date'][5:7]}"
                text = f"{date_str} | {s['name']} {shift_icon} [{s['emp_count']}]"
                
                item = QListWidgetItem(text)
                # Сохраняем все данные расписания в UserRole
                item.setData(Qt.ItemDataRole.UserRole, dict(s))
                self.list_schedules.addItem(item)

                # 5. ВОССТАНАВЛИВАЕМ ВЫДЕЛЕНИЕ
                # Если ID совпадает с тем, что был выбран до обновления
                if selected_id and s.get('id') == selected_id:
                    # Блокируем сигналы, если не хотим, чтобы on_schedule_selected вызвался дважды
                    # self.list_schedules.blockSignals(True) 
                    self.list_schedules.setCurrentItem(item)
                    # self.list_schedules.blockSignals(False)


    # @asyncSlot()
    # async def refresh_schedules(self):
    #     """Обновляет список расписаний слева с учетом смены и кол-ва людей"""
    #     self.list_schedules.clear()
        
    #     # Вызываем наш новый метод с подсчетом людей
    #     schedules = await self.schedule_base.get_all_schedules_with_stats()
        
    #     for s in schedules:
    #         date_short = s['date']
            
    #         shift_icon = ""
    #         if s['shift_type'] == "Day": shift_icon = "(День)"
    #         elif s['shift_type'] == "Night": shift_icon = "(Ночь)"
    #         else: shift_icon = "(Смешанная)" # Для Mixed/Смешанной
            
    #         # 3. Формируем итоговую строку
    #         # Пример: 11.03 | Гексагон ☀️ [12 чел.]
    #         text = f"{date_short} | {s['name']} {shift_icon} [{s['emp_count']}]"
            
    #         item = QListWidgetItem(text)
    #         # Сохраняем полные данные в UserRole
    #         item.setData(Qt.ItemDataRole.UserRole, dict(s))
            
    #         # Если людей 0, можно чуть приглушить цвет текста
    #         if s['emp_count'] == 0:
    #             item.setForeground(Qt.GlobalColor.gray)
                
    #         self.list_schedules.addItem(item)
            
    #     # Авто-выбор первого элемента, если список не пуст
    #     if self.list_schedules.count() > 0:
    #         self.list_schedules.setCurrentRow(0)
    #         await self.on_schedule_selected(self.list_schedules.item(0))
    #     else:
    #         self.table_employees.setRowCount(0)



    async def edit_selected_employee(self):
        if not self.btn_edit.isEnabled(): return
        self.btn_edit.setEnabled(False) 
        try:
            selected = self.table_employees.selectedItems()
            if not selected: return
            
            row = selected[0].row()
            emp_data = {
                "id": int(self.table_employees.item(row, 4).text()), 
                "name": self.table_employees.item(row, 0).text(),
                "job": self.table_employees.item(row, 1).text(),
                "time": self.table_employees.item(row, 2).text(),
                "shift_type": self.table_employees.item(row, 3).text()
            }
            
            stats = await self.day_off_setter_base.get_employee_stats(emp_data['id'])
            current_schedule = self.list_schedules.currentItem().data(Qt.ItemDataRole.UserRole)
            available_jobs = await self.job_ops.create_job_position_dict(current_schedule['department_id'])

            dialog = EmployeeCardDialog(emp_data, stats, available_jobs, self)
            if dialog.exec():
                action = dialog.result_action
                new_data = dialog.get_data()

                if action == "save":
                    await self.schedule_employees_base.update_employee_in_schedule(
                        new_data['job'], new_data['time'], current_schedule['id'], emp_data['id']
                    )
                
                elif action == "day_off":
                    await self.day_off_setter_base.put_employee_to_day_off(emp_data['id'])
                    await self.schedule_employees_base.delete_employee_from_schedule(current_schedule['id'], emp_data['id'], current_schedule['date'])
                    print(f"{emp_data['name']} отправлен на отдых")

                elif action == "remove":
                    await self.schedule_employees_base.delete_employee_from_schedule(current_schedule['id'], emp_data['id'], current_schedule['date'])

                elif action == "replace":
                    all_employees_dict = await self.employee_ops.create_employee_dict()
                    current_employees = await self.schedule_employees_base.get_all_employees_by_schedule(current_schedule['id'])
                    current_ids = [emp['user_id'] for emp in current_employees]

                    select_dialog = AddEmployeeDialog(all_employees_dict, current_ids, self)
                    
                    if select_dialog.exec():
                        new_name, new_id = select_dialog.get_selected()
                        
                        if new_id:
                            await self.schedule_employees_base.delete_employee_from_schedule(current_schedule['id'], emp_data['id'], current_schedule['date'])
                            await self.schedule_employees_base.add_employee_to_schedule(
                                current_schedule['id'], 
                                new_id, 
                                new_data['job'], 
                                new_data['time']
                            )
                            
                            await self.day_off_setter_base.increment_work_streak(new_id, current_schedule['date'])
                            print(f"(✓) Успешная замена: {emp_data['name']} -> {new_name}")


                await self.on_schedule_selected(self.list_schedules.currentItem())
        finally:
            self.btn_edit.setEnabled(True)

    async def build_and_copy_report(self, selected_schedules: list, report_date: str):
        """Собирает текст из выбранных расстановок и кладет в буфер с умным выводом времени"""
        if not selected_schedules:
            return
        
        total_people = 0
        full_report = [f"📅 Дата: {report_date}"]

        # 2. Цикл по каждому выбранному участку
        for s in selected_schedules:
            employees = await self.employee_base.get_full_data_for_report(s['id'])
            
            # --- ПРОВЕРКА ОДИНАКОВОГО ВРЕМЕНИ ---
            all_times = {emp['start_time'] for emp in employees} if employees else set()
            is_single_time = len(all_times) == 1
            common_time = list(all_times)[0] if is_single_time else None
            
            shift_ru = "День" if s['shift_type'] == "Day" else "Ночь"
            if s['shift_type'] == "Mixed": shift_ru = ""
            
            # Если время одно на всех - добавляем его в заголовок участка
            time_in_header = f"🕒 Выход с: {common_time}" if is_single_time else ""
            time_header = time_in_header + f"{f'| Смена: {shift_ru}' if shift_ru else ''}"
            full_report.append(f"🏢 Участок: {s['name']}")
            full_report.append(time_header)
            
            if not employees:
                full_report.append("  (список пуст)")
            else:
                for i, emp in enumerate(employees):
                    short_name = self.get_short_name(emp)
                    job = emp['job_place'] or "—"
                    job_text = f" ({job})" if job != "—" else ""
                    
                    if is_single_time:
                        # Время уже в шапке, выводим просто нумерованный список
                        full_report.append(f"  {i+1}. {short_name}{job_text}")
                    else:
                        # Время разное, выводим с твоим форматированием пробелов
                        t_val = emp['start_time']
                        time_str = f"{t_val if len(t_val) == 5 else '  ' + t_val}"
                        full_report.append(f"{time_str} | {i+1}. {short_name}{job_text}")
                    
                    total_people += 1
            
            full_report.append("")

        final_text = "\n".join(full_report)
        
        import pyperclip
        pyperclip.copy(final_text)
        
        if len(final_text) > 3900:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Внимание", "Отчет очень большой! Telegram может скрыть часть текста под 'Читать далее'.")
            
        print(f"✅ Отчет собран ({total_people} чел.) и скопирован в буфер! 📋✨")


    @asyncSlot()
    async def open_smart_report(self):
        current = self.list_schedules.currentItem()
        init_date = current.data(Qt.ItemDataRole.UserRole)['date'] if current else QDate.currentDate().toString("yyyy-MM-dd")
        init_id = current.data(Qt.ItemDataRole.UserRole)['id'] if current else -1

        dialog = SmartReportDialog(init_date, init_id, self)
        
        # Цикл "Живого окна"
        while True:
            # 1. Сначала грузим данные для текущей даты в диалоге
            target_date = dialog.date_edit.date().toString("yyyy-MM-dd")
            schedules = await self.schedule_base.get_schedules_by_date(target_date)
            dialog.set_schedules(schedules)

            # 2. Показываем окно
            result = dialog.exec()

            if result == 888: # Код смены даты
                continue # Просто крутим цикл дальше с новой датой
            
            if result == QDialog.DialogCode.Accepted:
                selected = dialog.get_selected_schedules()
                if selected:
                    await self.build_and_copy_report(selected, target_date)
                break # Выход
            
            break # Если нажали Отмена



    @asyncSlot(QListWidgetItem)
    async def on_schedule_selected(self, item):
        """Срабатывает при клике на расписание в списке"""
        schedule_data = item.data(Qt.ItemDataRole.UserRole)
        schedule_id = schedule_data['id']
        
        self.label_title.setText(f"<b>👥 {schedule_data['name']} ({schedule_data['date']})</b>")
        
        employees = await self.schedule_employees_base.get_all_employees_by_schedule(schedule_id)
            
        self.table_employees.setRowCount(0)
        if not employees: return

        for row_idx, emp in enumerate(employees):
            self.table_employees.insertRow(row_idx)
            
            
            
            full_name = self.get_short_name(emp)

            shift = emp['shift_type'] if 'shift_type' in emp.keys() else "Day"

            self.table_employees.setItem(row_idx, 0, QTableWidgetItem(full_name))
            self.table_employees.setItem(row_idx, 1, QTableWidgetItem(emp['job_place'] or "—"))
            self.table_employees.setItem(row_idx, 2, QTableWidgetItem(emp['start_time'] or "—"))
            self.table_employees.setItem(row_idx, 3, QTableWidgetItem(shift or "Day"))
            self.table_employees.setItem(row_idx, 4, QTableWidgetItem(str(emp['user_id'])))

class SmartReportDialog(QDialog):
    def __init__(self, initial_date, initial_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Генератор отчетов")
        self.resize(450, 550)
        self.initial_id = initial_id

        layout = QVBoxLayout(self)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.fromString(initial_date, "yyyy-MM-dd"))
        
        # ВАЖНО: При смене даты мы просто закрываем окно с кодом "Нужно обновить"
        self.date_edit.dateChanged.connect(lambda: self.done(888)) 
        
        layout.addWidget(QLabel("<b>Выбор даты:</b>"))
        layout.addWidget(self.date_edit)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.scroll_layout = QVBoxLayout(self.container)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

        self.checkboxes = []
        self.btn_copy = QPushButton("📋 Скопировать выбранное")
        self.btn_copy.clicked.connect(self.accept)
        layout.addWidget(self.btn_copy)

    def set_schedules(self, schedules):
        # 1. Полностью удаляем старый контейнер со всеми потрохами
        if hasattr(self, 'container'):
            self.container.deleteLater()
        
        # 2. Создаем НОВЫЙ чистый контейнер и слой
        self.container = QWidget()
        self.scroll_layout = QVBoxLayout(self.container)
        self.checkboxes.clear()

        # 3. Наполняем данными
        for s in schedules:
            s_dict = dict(s)
            cb = QCheckBox(f"{s_dict['name']} ({s_dict['shift_type']})")
            cb.schedule_data = s_dict
            
            # Отмечаем только при первом входе
            if self.initial_id != -1 and s_dict['id'] == self.initial_id:
                cb.setChecked(True)
            
            self.scroll_layout.addWidget(cb)
            self.checkboxes.append(cb)
            
        # Пружина в конце
        self.scroll_layout.addStretch()
        
        # 4. Устанавливаем новый контейнер в скролл-зону
        self.scroll.setWidget(self.container)
        
        # 5. Сбрасываем ID, чтобы на другой дате не было авто-галочек
        self.initial_id = -1 



    def get_selected_schedules(self):
        return [cb.schedule_data for cb in self.checkboxes if cb.isChecked()]



class EmployeeNameDialog(QDialog):
    def __init__(self, current_data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Данные сотрудника")
        layout = QFormLayout(self)

        self.ln_input = QLineEdit()
        self.fn_input = QLineEdit()
        self.mn_input = QLineEdit()

        if current_data:
            self.ln_input.setText(current_data.get('last_name', ''))
            self.fn_input.setText(current_data.get('first_name', ''))
            self.mn_input.setText(current_data.get('middle_name', ''))

        layout.addRow("Фамилия:", self.ln_input)
        layout.addRow("Имя:", self.fn_input)
        layout.addRow("Отчество:", self.mn_input)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def get_data(self):
        return {
            "ln": self.ln_input.text().strip(),
            "fn": self.fn_input.text().strip(),
            "mn": self.mn_input.text().strip()
        }



class EmployeeManagerDialog(QDialog):
    def __init__(self, employee_ops: EmployeeOperations, employee_base: EmployeeDatabase, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Управление базой сотрудников")
        self.resize(800, 500)
        self.employee_ops = employee_ops
        self.employee_base = employee_base

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Введите фамилию...")
        self.list_all_emps = QListWidget()
        self.btn_add_new = QPushButton("(+) Новый сотрудник")
        
        self.info_label = QLabel("Выберите сотрудника для просмотра")
        self.info_label.setWordWrap(True)
        self.history_list = QListWidget()
        self.btn_edit_profile = QPushButton("(>) Изменить ФИО")
        self.btn_del_from_db = QPushButton("(Х) Удалить сотрудника из Базы Данных")

        left_side = QVBoxLayout()
        left_side.addWidget(QLabel("<b>Поиск сотрудника:</b>"))
        left_side.addWidget(self.search_input)
        left_side.addWidget(self.list_all_emps)
        left_side.addWidget(self.btn_add_new)

        self.right_side = QVBoxLayout()
        self.right_side.addWidget(QLabel("<b>Информация и история:</b>"))
        self.right_side.addWidget(self.info_label)
        self.right_side.addWidget(self.btn_edit_profile)
        self.right_side.addWidget(self.history_list)
        self.right_side.addWidget(self.btn_del_from_db)

        main_layout = QHBoxLayout(self)
        main_layout.addLayout(left_side, 1)
        main_layout.addLayout(self.right_side, 2)

        self.search_input.textChanged.connect(self.filter_employees)
        self.btn_add_new.clicked.connect(self.add_new_employee)
        self.btn_del_from_db.clicked.connect(self.delete_employee_from_db)
        self.btn_edit_profile.clicked.connect(self.edit_employee)
        
        self.list_all_emps.itemClicked.connect(
            lambda item: asyncio.create_task(self.load_selected_emp_info(item))
        )


    async def init_list(self):
        """Первичная загрузка всех имен"""
        self.all_emps_dict = await self.employee_base.get_employees_with_status()
        self.filter_employees()
        
    @asyncSlot()
    async def add_new_employee(self):
        dialog = EmployeeNameDialog(parent=self)
        if dialog.exec():
            data = dialog.get_data()
            if not data['ln']: return
            
            await self.employee_base.add_user(data['fn'], data['ln'], data['mn'])
            await self.init_list()

    @asyncSlot()
    async def edit_employee(self):
        item = self.list_all_emps.currentItem()
        if not item: return
        
        user_id = item.data(Qt.ItemDataRole.UserRole)
        full_info_row = await self.employee_base.get_employee_full_info(user_id) 
        
        if full_info_row:
            full_info = dict(full_info_row)
            
            dialog = EmployeeNameDialog(current_data=full_info, parent=self)
            if dialog.exec():
                data = dialog.get_data()
                await self.employee_base.update_employee_name(user_id, data['fn'], data['ln'], data['mn'])
                await self.init_list() 

            
    @asyncSlot()
    async def delete_employee_from_db(self):
        item = self.list_all_emps.currentItem()
        if not item: return
        
        user_id = item.data(Qt.ItemDataRole.UserRole)
        name = item.text()
        
        reply = QMessageBox.question(self, 'Удаление', 
                                     f"ВНИМАНИЕ!\nУдаление {name} сотрет всю его историю и статистику.\nПродолжить?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            await self.employee_base.delete_employee_completely(user_id)
            await self.init_list()
            self.info_label.setText("Сотрудник удален")
            self.history_list.clear()
            
    def get_short_name(self, emp):
        
        emp = dict(emp) if not isinstance(emp, dict) else emp
        
        last = emp.get('last_name') or ""
        first = emp.get('first_name') or ""
        middle = emp.get('middle_name') or ""

        name_parts = [last]
        
        if len(last + first + middle) <= 12:
            return " ".join([last, first, middle])
        
        if first:
            name_parts.append(f"{first[0]}.")
            
        if middle:
            name_parts.append(f"{middle[0]}.")
            
        return " ".join(name_parts).strip()

    def filter_employees(self):
        search = self.search_input.text().lower()
        self.list_all_emps.clear()
        
        for emp_row in self.all_emps_dict:
            emp = dict(emp_row) 
            
            full_name = self.get_short_name(emp)
            
            if search in full_name.lower():
                item = QListWidgetItem(full_name)
                item.setData(Qt.ItemDataRole.UserRole, emp['user_id'])
                self.list_all_emps.addItem(item)

    # @asyncSlot()
    async def load_selected_emp_info(self, item):
        user_id = item.data(Qt.ItemDataRole.UserRole)
        name = item.text()
        

        stats = await self.parent().day_off_setter_base.get_employee_stats(user_id)
            
        status_text = f"Статус: {stats['status'] if stats else 'Нет данных'}\n"
        streak_text = f"Стрик: {stats['work_streak'] if stats else 0} дн.\n"
        
        self.info_label.setText(f"<b>{name}</b> (ID: {user_id})\n{status_text}{streak_text}")

        self.history_list.clear()
        history = await self.employee_base.get_employee_history(user_id)
        if history:
            for h in history:
                print(dict(h).items())
                self.history_list.addItem(f"📅 {h['work_date']} | {h['department_name']} | {h['job_place']} | {h['shift_type']}")
        else:
            self.history_list.addItem("История пуста")


class AddEmployeeDialog(QDialog):
    def __init__(self, all_employees_data, current_emp_ids, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить сотрудника на участок")
        self.resize(500, 600)
        
        self.all_emps = all_employees_data
        self.current_ids = current_emp_ids
        self.new_emp_data = None 

        layout = QVBoxLayout(self)

        # 1. ПОИСК (Оставляем, раз он нужен)
        layout.addWidget(QLabel("<b>🔍 Поиск по фамилии:</b>"))
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Начните вводить...")
        self.search_field.textChanged.connect(self.filter_list) # Привязываем поиск
        layout.addWidget(self.search_field)

        # 2. СПИСОК (Создаем только ОДИН раз)
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.accept)
        self.list_widget.setFont(QFont("Courier New", 10))
        layout.addWidget(self.list_widget)

        # 3. КНОПКА БЫСТРОГО ДОБАВЛЕНИЯ
        self.btn_quick_add = QPushButton("(+) Создать нового сотрудника в базе")
        self.btn_quick_add.clicked.connect(self.quick_add_employee)
        layout.addWidget(self.btn_quick_add)

        # 4. КНОПКИ ОК/ОТМЕНА
        btns = QHBoxLayout()
        self.btn_ok = QPushButton("Добавить")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.clicked.connect(self.reject)
        btns.addWidget(self.btn_ok)
        btns.addWidget(self.btn_cancel)
        layout.addLayout(btns)

        # Запускаем первичную отрисовку списка
        self.filter_list()

    def get_short_name(self, emp):
        e = dict(emp) if not isinstance(emp, dict) else emp
        last = e.get('last_name') or e.get('ln') or ""
        first = e.get('first_name') or e.get('fn') or ""
        middle = e.get('middle_name') or e.get('mn') or ""
        
        if len(last + first + middle) <= 12:
            return f"{last} {first} {middle}".strip()
        
        res = last
        if first: res += f" {first[0]}."
        if middle: res += f" {middle[0]}."
        return res

    def filter_list(self):
        """Метод поиска и отрисовки списка"""
        search_text = self.search_field.text().lower()
        self.list_widget.clear()

        for emp in self.all_emps:
            e = dict(emp)
            user_id = e.get('user_id') or e.get('id')
            short_name = self.get_short_name(e)
            
            # Если ввели текст, проверяем совпадение
            if search_text and search_text not in short_name.lower():
                continue

            # Логика определения статуса и цвета
            if user_id in self.current_ids:
                status_text = "Уже на участке"
                color = Qt.GlobalColor.cyan
            elif e.get('current_dept'):
                status_text = f"Занят: {e['current_dept']}"
                color = Qt.GlobalColor.red
            else:
                status = e.get('status')
                streak = e.get('work_streak') or 0
                if status == 'Working':
                    status_text = f"Работает: {streak} дн"
                    color = Qt.GlobalColor.green
                elif status == 'Day Off' and e.get('last_activity'):
                    try:
                        days = (arrow.now() - arrow.get(e['last_activity'])).days
                        status_text = f"Выходной: {days} дн"
                        color = Qt.GlobalColor.yellow
                    except:
                        status_text = "Выходной"
                        color = Qt.GlobalColor.white
                else:
                    status_text = "Свободен"
                    color = Qt.GlobalColor.white

            display_text = f"{short_name:<20} | {status_text}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, user_id)
            item.setForeground(color) 
            
            # Делаем некликабельным, если уже на участке
            if user_id in self.current_ids:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            
            self.list_widget.addItem(item)

    def get_selected(self):
        item = self.list_widget.currentItem()
        if item:
            user_id = item.data(Qt.ItemDataRole.UserRole)
            for emp in self.all_emps:
                emp = dict(emp)
                e_id = emp.get('user_id') or emp.get('id')
                if e_id == user_id:
                    return self.get_short_name(emp), user_id
        return None, None

    def quick_add_employee(self):
        # Здесь вызывай свой EmployeeNameDialog
        dialog = EmployeeNameDialog(parent=self)
        if dialog.exec():
            self.new_emp_data = dialog.get_data()
            if self.new_emp_data.get('ln'):
                self.done(777)
                
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, 
                             QLineEdit, QPushButton, QLabel, QMessageBox)

class JobPositionsEditorDialog(QDialog):
    def __init__(self, department_name, department_id, job_ops: JobPlaceOperations, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Позиции участка: {department_name}")
        self.resize(350, 450)
        
        self.dept_id = department_id
        self.job_ops = job_ops 
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("<b>Текущие позиции:</b>"))
        self.list_jobs = QListWidget()
        layout.addWidget(self.list_jobs)

        btn_del_layout = QHBoxLayout()
        self.btn_delete = QPushButton("(X) Удалить выбранную")
        self.btn_delete.clicked.connect(lambda: asyncio.create_task(self.delete_job()))
        btn_del_layout.addStretch()
        btn_del_layout.addWidget(self.btn_delete)
        layout.addLayout(btn_del_layout)

        layout.addSpacing(20)

        layout.addWidget(QLabel("<b>Добавить новую позицию:</b>"))
        self.new_job_input = QLineEdit()
        self.new_job_input.setPlaceholderText("Название позиции...")
        layout.addWidget(self.new_job_input)

        self.btn_add = QPushButton("(>) Добавить в базу")
        self.btn_add.clicked.connect(lambda: asyncio.create_task(self.add_job()))
        layout.addWidget(self.btn_add)

        self.btn_close = QPushButton("Закрыть")
        self.btn_close.clicked.connect(self.accept)
        layout.addWidget(self.btn_close)

    async def load_jobs(self):
        """Загрузка позиций из БД"""
        self.list_jobs.clear()
        jobs = await self.job_ops.create_job_position_dict(self.dept_id)
        if jobs:
            print(jobs)
            self.list_jobs.addItems(jobs)

    async def add_job(self):
        name = self.new_job_input.text().strip()
        if not name: return
        
        await self.job_ops.add_new_job_position(department_id=self.dept_id, job_name=name)
        self.new_job_input.clear()
        await self.load_jobs()
        print(f"Добавлена позиция: {name}")

    async def delete_job(self):
        item = self.list_jobs.currentItem()
        if not item: return
        
        job_name = item.text()
        reply = QMessageBox.question(self, 'Удаление', f"Удалить позицию '{job_name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            await self.job_ops.delete_job_position(department_id=self.dept_id, job_name=job_name)
            await self.load_jobs()



class ScheduleDialog(QDialog):
    def __init__(self, departments, current_data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Параметры расстановки")
        layout = QFormLayout(self)

        self.combo_dept = QComboBox()
        for row in departments:
            self.combo_dept.addItem(row['name'], row['id'])
        
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())

        self.combo_shift = QComboBox()
        self.combo_shift.addItems(["Day", "Night", "Mixed"]) 

        self.time_edit = QTimeEdit()

        if current_data:
            self.combo_dept.setCurrentText(current_data['name'])
            self.combo_shift.setCurrentText(current_data['shift_type'] or "Mixed")
            q_date = QDate.fromString(current_data['date'], "yyyy-MM-dd")
            self.date_edit.setDate(q_date)
            
            h, m = map(int, (current_data.get('start_time') or "08:00").split(':'))
            self.time_edit.setTime(QTime(h, m))
        else:
            self.time_edit.setTime(QTime(8, 0))

        layout.addRow("Участок:", self.combo_dept)
        layout.addRow("Дата:", self.date_edit)
        layout.addRow("Смена (основная):", self.combo_shift)
        layout.addRow("Время (дефолт):", self.time_edit)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def get_data(self):
        return {
            "dept_id": self.combo_dept.currentData(),
            "date": self.date_edit.date().toString("yyyy-MM-dd"),
            "shift": self.combo_shift.currentText(),
            "time": self.time_edit.time().toString("H:mm")
        }


class EmployeeCardDialog(QDialog):
    def __init__(self, emp_data, stats, available_jobs, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Карточка: {emp_data['name']}")
        self.result_action = None

        # 1. Главная сетка окна
        self.main_layout = QGridLayout(self)

        # --- ЛЕВАЯ ЧАСТЬ: СТАТИСТИКА ---
        self.stats_frame = QFrame()
        self.stats_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.stats_layout = QVBoxLayout(self.stats_frame)
        
        if stats is None:
            stats = {'status': 'Unknown', 'work_streak': 0, 'last_activity': 'Нет данных'}
        else:
            stats = dict(stats)

        activity_placeholder = "Активность:"
        if stats['status'] == 'Working': activity_placeholder = 'Работает с:'
        elif stats['status'] == "Day off": activity_placeholder = "Выходной c:"
        
        status_color = "green" if stats.get('status') == 'Working' else "red"
        self.stats_layout.addWidget(QLabel(f"<b>Статус:</b> <span style='color:{status_color}'>{stats['status']}</span>"))
        self.stats_layout.addWidget(QLabel(f"<b>Работает:</b> {stats['work_streak']} дн."))
        self.stats_layout.addWidget(QLabel(f"<b>{activity_placeholder}</b> {stats['last_activity']}"))

        self.main_layout.addWidget(QLabel("<b>Статистика:</b>"), 0, 0)
        self.main_layout.addWidget(self.stats_frame, 1, 0)

        # --- ПРАВАЯ ЧАСТЬ: РЕДАКТИРОВАНИЕ (СМЕНА, МЕСТО, ВРЕМЯ) ---
        self.edit_layout = QVBoxLayout()
        
        # Поле "Смена"
        self.combo_shift = QComboBox()
        self.combo_shift.addItems(["Day", "Night"])
        if emp_data.get('shift_type'):
            self.combo_shift.setCurrentText(emp_data['shift_type'])
        
        # Поле "Рабочее место"
        self.combo_job = QComboBox()
        # Добавляем прочерк ПЕРВЫМ в список
        jobs_with_null = ["—"] + (available_jobs if available_jobs else [])
        self.combo_job.addItems(jobs_with_null)
        
        # Установка текущей позиции (если в базе пусто или прочерк - ставим "—")
        current_job = emp_data.get('job')
        if current_job and current_job in jobs_with_null:
            self.combo_job.setCurrentText(current_job)
        else:
            self.combo_job.setCurrentText("—")
        
        # Поле "Время"
        self.time_edit = QTimeEdit()
        # Защита на случай, если время пришло в кривом формате
        try:
            h, m = map(int, emp_data['time'].split(':'))
            self.time_edit.setTime(QTime(h, m))
        except:
            self.time_edit.setTime(QTime(8, 0))

        # Добавляем виджеты в правый слой
        self.edit_layout.addWidget(QLabel("Смена:"))
        self.edit_layout.addWidget(self.combo_shift)
        self.edit_layout.addWidget(QLabel("Рабочее место:"))
        self.edit_layout.addWidget(self.combo_job)
        self.edit_layout.addWidget(QLabel("Время выхода:"))
        self.edit_layout.addWidget(self.time_edit)
        
        self.main_layout.addLayout(self.edit_layout, 1, 1)

        # --- НИЖНЯЯ ПАНЕЛЬ КНОПОК ---
        self.btn_panel = QHBoxLayout()
        
        self.btn_save = QPushButton("(>) Сохранить")
        self.btn_save.clicked.connect(self.action_save)
        
        self.btn_day_off = QPushButton("(~) На выходной")
        self.btn_day_off.clicked.connect(self.action_day_off)
        
        self.btn_replace = QPushButton("(*) Заменить")
        self.btn_replace.clicked.connect(self.action_replace)
        
        self.btn_remove = QPushButton("(x) Убрать")
        self.btn_remove.clicked.connect(self.action_remove)

        self.btn_panel.addWidget(self.btn_save)
        self.btn_panel.addWidget(self.btn_day_off)
        self.btn_panel.addWidget(self.btn_replace)
        self.btn_panel.addWidget(self.btn_remove)

        self.main_layout.addLayout(self.btn_panel, 2, 0, 1, 2)

    def action_save(self): self.result_action = "save"; self.accept()
    def action_day_off(self): self.result_action = "day_off"; self.accept()
    def action_replace(self): self.result_action = "replace"; self.accept()
    def action_remove(self): self.result_action = "remove"; self.accept()

    def get_data(self):
        """Возвращает данные для БД. Если выбран '—', возвращает None"""
        selected_job = self.combo_job.currentText()
        return {
            "job": None if selected_job == "—" else selected_job,
            "time": self.time_edit.time().toString("H:mm"),
            "shift": self.combo_shift.currentText()
        }

class EmployeeEditDialog(QDialog):
    def __init__(self, name, position, time_str, available_jobs, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Правка: {name}")
        self.layout = QFormLayout(self)

        self.combo_job = QComboBox()
        self.combo_job.addItems(available_jobs)
        if position in available_jobs:
            self.combo_job.setCurrentText(position)
        else:
            self.combo_job.setEditText(position)
        
        self.time_edit = QTimeEdit()
        h, m = map(int, time_str.split(':'))
        self.time_edit.setTime(QTime(h, m))

        self.layout.addRow("Позиция:", self.combo_job)
        self.layout.addRow("Время выхода:", self.time_edit)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def get_data(self):
        """Возвращает введенные данные"""
        return {
            "job": self.combo_job.currentText(),
            "time": self.time_edit.time().toString("H:mm")
        }

async def main_gui(db: aiosqlite.Connection):

    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    window = MainWindow(db)
    window.show()
    await window.refresh_schedules()

    with loop:
        await loop.run_forever()

if __name__ == "__main__":
    asyncio.run(main_gui())
