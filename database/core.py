# core.py Основной класс базы данных
import sqlite3
from contextlib import contextmanager

class Database:
    def __init__(self, db_name):
        self.db_name = db_name

    @contextmanager
    def get_cursor(self):
        conn = sqlite3.connect(self.db_name)
        try:
            cursor = conn.cursor()
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()