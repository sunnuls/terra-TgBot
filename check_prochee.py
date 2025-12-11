import sqlite3

def check_prochee():
    con = sqlite3.connect("reports.db")
    c = con.cursor()
    
    print("=== Все записи 'прочее' в таблице activities ===")
    c.execute("SELECT * FROM activities WHERE name LIKE '%прочее%'")
    rows = c.fetchall()
    for i, row in enumerate(rows):
        print(f"  {i+1}. {row}")
    
    print(f"\nВсего записей 'прочее': {len(rows)}")
    
    # Проверим, есть ли дубликаты
    c.execute("SELECT name, COUNT(*) FROM activities WHERE name LIKE '%прочее%' GROUP BY name")
    duplicates = c.fetchall()
    print("\n=== Группировка по имени ===")
    for name, count in duplicates:
        print(f"  '{name}': {count} записей")
    
    con.close()

if __name__ == "__main__":
    check_prochee()
