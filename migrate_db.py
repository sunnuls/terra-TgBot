import sqlite3, os, shutil, datetime as dt

DB = "reports.db"
assert os.path.exists(DB), f"Файл {DB} не найден рядом со скриптом."

# 1) Бэкап на всякий случай
ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = f"reports_backup_{ts}.db"
shutil.copy2(DB, backup)
print(f"[i] Бэкап создан: {backup}")

conn = sqlite3.connect(DB)
c = conn.cursor()

def has_column(table, col):
    c.execute(f"PRAGMA table_info({table})")
    return any(row[1] == col for row in c.fetchall())

# 2) users.username
if not has_column("users", "username"):
    c.execute("ALTER TABLE users ADD COLUMN username TEXT")
    print("[i] Добавлена колонка users.username")
else:
    print("[i] Колонка users.username уже существует")

# 3) reports.reg_name (на случай старой схемы)
if not has_column("reports", "reg_name"):
    c.execute("ALTER TABLE reports ADD COLUMN reg_name TEXT")
    print("[i] Добавлена колонка reports.reg_name")
else:
    print("[i] Колонка reports.reg_name уже существует")

conn.commit()
conn.close()
print("[i] Готово. Запускайте бота.")
