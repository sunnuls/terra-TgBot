# migrate_add_tz.py
from datetime import datetime
import os
import shutil
import sqlite3
from dotenv import load_dotenv

DB_PATH = "reports.db"

def backup(db_path: str) -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = f"reports_backup_{ts}.db"
    shutil.copy2(db_path, dst)
    print(f"[i] Бэкап создан: {dst}")

def column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())

def main():
    if not os.path.exists(DB_PATH):
        print(f"[ERR] Не найден {DB_PATH} в текущей папке")
        return

    load_dotenv(".env")
    env_tz = os.getenv("TZ") or "Europe/Moscow"

    backup(DB_PATH)
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # users.username (на всякий случай, если в старой базе)
    if not column_exists(cur, "users", "username"):
        cur.execute("ALTER TABLE users ADD COLUMN username TEXT")
        print("[i] Добавлена колонка users.username")

    # users.tz — причина вашей ошибки
    if not column_exists(cur, "users", "tz"):
        cur.execute("ALTER TABLE users ADD COLUMN tz TEXT")
        print("[i] Добавлена колонка users.tz")
        con.commit()

    # Заполним пустые tz значением из .env
    cur.execute("UPDATE users SET tz = ? WHERE tz IS NULL OR tz = ''", (env_tz,))
    updated = cur.rowcount
    con.commit()
    print(f"[i] Обновлено записей users.tz: {updated}")

    # reports.reg_name (оставлено для совместимости с прошлыми миграциями)
    if not column_exists(cur, "reports", "reg_name"):
        cur.execute("ALTER TABLE reports ADD COLUMN reg_name TEXT")
        print("[i] Добавлена колонка reports.reg_name")
        con.commit()

    con.close()
    print("[i] Готово. Запускайте бота.")

if __name__ == "__main__":
    main()
