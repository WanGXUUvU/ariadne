import sqlite3

db_path = "agent_session.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # 物理为已存在的主表 session_records 添加 session_type 字段，默认值为 'coding'
    cursor.execute("ALTER TABLE session_records ADD COLUMN session_type TEXT NOT NULL DEFAULT 'coding';")
    conn.commit()
    print("🎉 物理数据库升级成功：已为表 session_records 追加 session_type 字段且默认值为 'coding'")
except sqlite3.OperationalError as e:
    # 如果已存在，则优雅吞掉异常
    if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
        print("💡 字段 session_type 已经存在，无需重复添加。")
    else:
        raise e
finally:
    conn.close()