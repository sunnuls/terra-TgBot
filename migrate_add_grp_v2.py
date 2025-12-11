# migrate_add_grp_v2.py
import os, shutil, sqlite3
from datetime import datetime

DB = "reports.db"

GROUP_FIELDS = "поля"
GROUP_WARE   = "склад"
GROUP_TECH   = "техника"
GROUP_HAND   = "ручная"

DEFAULT_TECH = [
    "пахота","чизелевание","дискование","культивация сплошная",
    "культивация междурядная","опрыскивание","комбайн уборка","сев","барнование",
]

def cols(c, table):
    return {r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}

def ensure_col(c, table, col, ddl_type="TEXT"):
    if col not in cols(c, table):
        c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl_type}")

def main():
    if not os.path.exists(DB):
        print(f"[!] Файл {DB} не найден.")
        return

    # backup
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"reports_backup_{ts}.db"
    shutil.copyfile(DB, backup)
    print(f"[i] Бэкап создан: {backup}")

    con = sqlite3.connect(DB)
    c = con.cursor()

    # Добавим недостающие колонки
    ensure_col(c, "locations", "grp", "TEXT")
    ensure_col(c, "activities", "grp", "TEXT")

    # Заполним grp в locations
    c.execute(
        "UPDATE locations SET grp=? WHERE (grp IS NULL OR grp='') AND name='Склад'",
        (GROUP_WARE,)
    )
    c.execute(
        "UPDATE locations SET grp=? WHERE (grp IS NULL OR grp='') AND name<>'Склад'",
        (GROUP_FIELDS,)
    )

    # Заполним grp в activities
    placeholders = ",".join("?" * len(DEFAULT_TECH))
    if placeholders:
        c.execute(
            f"UPDATE activities SET grp=? WHERE (grp IS NULL OR grp='') AND name IN ({placeholders})",
            (GROUP_TECH, *DEFAULT_TECH)
        )
    c.execute(
        "UPDATE activities SET grp=? WHERE (grp IS NULL OR grp='') AND (grp IS NULL OR grp='')",
        (GROUP_HAND,)
    )

    con.commit()
    con.close()
    print("[i] Миграция завершена. Запускайте бота.")

if __name__ == "__main__":
    main()

