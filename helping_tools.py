import logging

class HelpingTools:
    def __init__(self):
        self.logger: logging = logging.getLogger(__file__)
    
    @staticmethod
    async def clear_console():
    # clears console with help of ANSI escape codes
        print('\033[H\033[J', end='')
        
    async def menu_int_handler(self, text: str, max_value: int = None, min_value: int = None) -> int | bool:
        self.logger.info(f"menu int handler recieved: max_value: {max_value}, min_value: {min_value}")
        while True:
            try:
                choice = int(input(text))

                if max_value != None and min_value != None:
                    if choice < min_value or choice > max_value:
                        print(f"Диапазон выбора должен быть в рамках: {min_value} - {max_value}.")
                        continue
                    else:
                        break
                
                if max_value != None:
                    if choice > max_value or choice <= 0:
                        print(f'Максимально допустимое значение = {max_value}.')
                        continue
                    else:
                        break
                    
                if min_value != None:
                    if choice < min_value:
                        print(f"Минимально допустимое значение = {min_value}.")
                        continue
                    else:
                        break
                    
            except Exception:
                print("Неправильное значение для меню. Пожалуйста повторите попытку.")
                continue
            
            else:
                break
            
        return choice