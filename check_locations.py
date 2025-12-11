import sqlite3

def check_locations():
    con = sqlite3.connect("reports.db")
    c = con.cursor()
    
    print("=== Структура таблицы locations ===")
    c.execute("PRAGMA table_info(locations)")
    columns = c.fetchall()
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    print("\n=== Все записи в locations ===")
    c.execute("SELECT * FROM locations")
    rows = c.fetchall()
    for row in rows:
        print(f"  {row}")
    
    print(f"\nВсего записей: {len(rows)}")
    
    con.close()

if __name__ == "__main__":
    check_locations()

