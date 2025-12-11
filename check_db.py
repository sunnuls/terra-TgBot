import sqlite3
import os

def check_db():
    if not os.path.exists("reports.db"):
        print("Файл reports.db не найден!")
        return
    
    print(f"Размер файла: {os.path.getsize('reports.db')} байт")
    
    con = sqlite3.connect("reports.db")
    c = con.cursor()
    
    # Список всех таблиц
    print("\n=== Все таблицы в базе ===")
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = c.fetchall()
    for table in tables:
        print(f"  {table[0]}")
    
    if not tables:
        print("  Таблиц не найдено!")
        con.close()
        return
    
    # Проверяем каждую таблицу
    for table_name in [t[0] for t in tables]:
        print(f"\n=== Таблица: {table_name} ===")
        
        # Структура
        c.execute(f"PRAGMA table_info({table_name})")
        columns = c.fetchall()
        if columns:
            print("  Структура:")
            for col in columns:
                print(f"    {col[1]} ({col[2]})")
        else:
            print("  Структура не найдена")
        
        # Количество записей
        try:
            c.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = c.fetchone()[0]
            print(f"  Записей: {count}")
            
            if count > 0:
                # Первые записи
                c.execute(f"SELECT * FROM {table_name} LIMIT 3")
                rows = c.fetchall()
                print("  Первые записи:")
                for row in rows:
                    print(f"    {row}")
        except Exception as e:
            print(f"  Ошибка при чтении: {e}")
    
    con.close()

if __name__ == "__main__":
    check_db()
