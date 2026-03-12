from pydantic import BaseModel, ConfigDict, ValidationError, Field
import logging
import aiosqlite
from typing import Optional, Literal

class ValidateUser(BaseModel):
    name: str | None
    telegram_id: str | None = Field(min_length=9, max_length=10, pattern=r'^\d+$')
    password: str | None

class ValidateUserScheme(BaseModel):
    user_name: str 
    telegram_id: int
    password_hash: str
    
    model_config = ConfigDict(from_attributes=True)
    
class ValidateJobScheme(BaseModel):
    user_id: int
    company_name: str
    job_category: str
    salary_rate: int
    salary_type: str = Literal["hourly", "daily", "weekly", "biweekly", "monthly", "year"]
    flat_rent: int | None
    
    
class Validator:
    logger = logging.getLogger(__name__)
    
    @classmethod
    def validate_user_data(cls, username: str | None = None, telegram_id: int | None = None, raw_password: str | None = None) -> ValidateUser | None:
        try:
            if username == None and telegram_id == None and raw_password == None:
                raise Exception("Data didn't pass the access.")
            
            user = ValidateUser(name=username, telegram_id=telegram_id, password=raw_password)
        
        except ValidationError:
            cls.logger.error("Data was not validated. Error occured during data validation")
            return None
        
        else:
            cls.logger.info("Data successfully validated.")
            return user
        
    @classmethod
    def validate_user_sql(cls, sql_row: aiosqlite.Row) -> Optional[ValidateUserScheme] | None:
        try:
            user = ValidateUserScheme.model_validate(dict(sql_row))
        
        except ValidationError as error:
            cls.logger.error("Data was not validated. Error occured during data validation.", exc_info=True)
            return None
        
        else:
            return user
        
    @classmethod
    def validate_job_data(cls, user_id: int, company_name: str, job_category: str, salary_rate: int, salary_type: str, flat_rent: int | None) -> Optional[ValidateJobScheme] | None:
        try:
            job_data = ValidateJobScheme(user_id=user_id, company_name=company_name, job_category=job_category, salary_rate=salary_rate, salary_type=salary_type, flat_rent=flat_rent)
        
        except ValidationError as error:
            cls.logger.error("Job data was not validated.", exc_info=True)
            return None
        
        else:
            return job_data
        