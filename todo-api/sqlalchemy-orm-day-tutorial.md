# 1 天离线教程：把 todo-api 从 sqlite3/原生 SQL 迁移到 SQLAlchemy ORM

## 今天的目标

今天只做一件大事：

**把你现在已经能跑的 `todo-api`，从“原生 SQL + sqlite3”逐步迁移到“SQLAlchemy ORM”写法。**

不是推翻重写，而是按顺序替换。

你今天学完，至少应该能说清楚：

- `db.py` 在 ORM 里负责什么
- `models.py` 为什么要定义 `Todo` 类
- `SessionLocal()` 是什么
- `db.query(Todo).all()` 和 `SELECT * FROM todos` 的对应关系
- 为什么 ORM 更适合后面做真实后端项目

## 今日总安排

建议总时长：`4 ~ 6` 小时

分 6 段：

1. 第 1 段：梳理 SQLAlchemy 基础设施
2. 第 2 段：写对 `models.py`
3. 第 3 段：把读取逻辑迁移到 ORM
4. 第 4 段：把新增逻辑迁移到 ORM
5. 第 5 段：把更新和删除逻辑迁移到 ORM
6. 第 6 段：完整回归测试 + 复盘

## 第 1 段：梳理 SQLAlchemy 基础设施（40 分钟）

### 目标

先把下面 3 个文件的职责彻底理顺：

- `db.py`
- `models.py`
- `app.py`

### 一、`db.py` 应该长什么样

你现在的 ORM 版 [db.py](/Users/wangxu/Documents/RAG%20检索知识库/todo-api/db.py) 应该接近这样：

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./todo.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()
```

### 二、逐行理解 `db.py`

#### `DATABASE_URL`

```python
DATABASE_URL = "sqlite:///./todo.db"
```

作用：

- 指定数据库文件路径

意思是：

- 使用当前目录下的 `todo.db` 作为 SQLite 数据库文件

#### `engine`

```python
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)
```

作用：

- 创建数据库引擎

你可以把 `engine` 理解成：

**SQLAlchemy 连接数据库的总入口。**

后面：

- 建表
- 创建会话
- 真正访问数据库

都围绕它展开。

#### `SessionLocal`

```python
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)
```

作用：

- 创建数据库会话工厂

以后你在业务函数里会写：

```python
db = SessionLocal()
```

意思是：

- 创建一个这次请求使用的数据库会话

你可以把它理解成：

**一次数据库操作的工作上下文。**

#### `Base`

```python
Base = declarative_base()
```

作用：

- 所有 ORM 模型的父类

以后在 `models.py` 里会写：

```python
class Todo(Base):
    ...
```

所以 `Base` 不是表，也不是连接，它是：

**ORM 模型的共同基类。**

### 三、`app.py` 应该长什么样

当前最小版 [app.py](/Users/wangxu/Documents/RAG%20检索知识库/todo-api/app.py) 应该接近这样：

```python
from fastapi import FastAPI

from db import Base, engine
from routes import router
import models

app = FastAPI()
app.include_router(router)

Base.metadata.create_all(bind=engine)
```

### 四、逐行理解 `app.py`

#### `from db import Base, engine`
导入数据库基础设施。

#### `import models`
这一步很重要。

它的作用是：

**先让 `Todo` 这种 ORM 模型注册到 `Base` 上。**

如果不导入 `models`，有时候 `Base.metadata.create_all(...)` 不知道你有哪些表要建。

#### `Base.metadata.create_all(bind=engine)`
作用：

**根据 ORM 模型，自动创建数据库表。**

这一步本质上替代了你之前原生 SQL 版的：

```sql
CREATE TABLE IF NOT EXISTS todos (...)
```

### 这一段的结论

你现在先记住：

- `db.py`：数据库运行环境
- `models.py`：数据库表的 Python 映射
- `app.py`：项目启动时把表建起来

## 第 2 段：写对 `models.py`（40 分钟）

### 目标

把 [models.py](/Users/wangxu/Documents/RAG%20检索知识库/todo-api/models.py) 修成一个真正的 ORM 模型文件。

### 正确版 `models.py`

```python
from sqlalchemy import Column, Integer, String

from db import Base


class Todo(Base):
    __tablename__ = "todos"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
```

### 逐行解释

#### `from sqlalchemy import Column, Integer, String`
导入列定义和字段类型。

#### `from db import Base`
导入 ORM 模型基类。

#### `class Todo(Base):`
定义 ORM 模型类 `Todo`。

这里的 `Todo` 表示：

**数据库 `todos` 表中的一条记录，对应的 Python 类。**

#### `__tablename__ = "todos"`
指定这个模型类对应数据库里的 `todos` 表。

#### `id = Column(Integer, primary_key=True, index=True)`
定义 `id` 字段：

- 整数
- 主键
- 带索引

#### `title = Column(String, nullable=False)`
定义 `title` 字段：

- 字符串
- 不能为空

### 你在这一段必须能回答

1. `Todo` 类和 `todos` 表是什么关系
2. `id` 和 `title` 为什么写成 `Column(...)`
3. 为什么 `title` 建议 `nullable=False`

## 第 3 段：迁移读取逻辑到 ORM（1 小时）

### 目标

先迁移两条只读接口：

- `GET /todos`
- `GET /todos/{todo_id}`

只改 [services.py](/Users/wangxu/Documents/RAG%20检索知识库/todo-api/services.py)，路由层尽量少动。

### 一、ORM 版 `get_all_todos()`

```python
from db import SessionLocal
from models import Todo


def get_all_todos():
    db = SessionLocal()

    todos = db.query(Todo).all()

    db.close()

    return [
        {"id": todo.id, "title": todo.title}
        for todo in todos
    ]
```

### 逐行解释

#### `db = SessionLocal()`
创建数据库会话。

#### `db.query(Todo).all()`
这是 ORM 查询的核心写法。

它的意思是：

- 对 `Todo` 模型发起查询
- 拿到所有结果

从 SQL 角度理解，大致相当于：

```sql
SELECT * FROM todos
```

#### `db.close()`
关闭会话。

#### `todo.id` / `todo.title`
注意：现在不再是 `row["id"]`，而是对象属性访问：

```python
todo.id
todo.title
```

因为 ORM 返回的是 `Todo` 对象，不是 `sqlite3.Row`。

### 二、ORM 版 `get_todo_by_id()`

```python
def get_todo_by_id(todo_id: int):
    db = SessionLocal()

    todo = db.query(Todo).filter(Todo.id == todo_id).first()

    db.close()

    if todo is None:
        return None

    return {"id": todo.id, "title": todo.title}
```

### 逐行解释

#### `filter(Todo.id == todo_id)`
按 id 加筛选条件。

这大致对应 SQL：

```sql
WHERE id = ?
```

#### `.first()`
取第一条结果。

如果没查到，会得到 `None`。

### 三、你这一段要完成什么

把 `routes.py` 保持成这种调用方式：

```python
@router.get("/todos", response_model=list[TodoResponse])
def get_todos():
    return get_all_todos()
```

```python
@router.get("/todos/{todo_id}", response_model=TodoResponse)
def get_todo(todo_id: int):
    todo = get_todo_by_id(todo_id)
    if todo is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todo
```

### 这一段的关键结论

你要真正理解这句话：

**ORM 查询不是不用数据库，而是把“写 SQL”换成了“操作模型”。**

## 第 4 段：迁移新增逻辑到 ORM（1 小时）

### 目标

把 `POST /todos` 迁到 ORM。

### ORM 版 `create_todo()`

```python
def create_todo(title: str):
    db = SessionLocal()

    todo = Todo(title=title)
    db.add(todo)
    db.commit()
    db.refresh(todo)

    db.close()

    return {"id": todo.id, "title": todo.title}
```

### 逐行解释

#### `todo = Todo(title=title)`
创建一个 ORM 对象。

你可以把它理解成：

**先在 Python 里创建一条待插入的记录对象。**

#### `db.add(todo)`
把这个对象加入当前会话，表示“准备插入”。

#### `db.commit()`
真正提交到数据库。

#### `db.refresh(todo)`
提交后重新刷新这个对象。  
这样像 `id` 这种数据库自动生成的值，才能回填到 `todo.id`。

#### 返回值
最后把 ORM 对象转成字典返回。

### 这一段你要理解什么

这一步最重要的是：

**新增时，你不再写 `INSERT INTO`，而是创建 `Todo(...)` 对象，然后 `db.add()`。**

## 第 5 段：迁移更新和删除逻辑到 ORM（1.5 小时）

### 一、ORM 版 `update_todo()`

```python
def update_todo(todo_id: int, title: str):
    db = SessionLocal()

    todo = db.query(Todo).filter(Todo.id == todo_id).first()
    if todo is None:
        db.close()
        return None

    todo.title = title
    db.commit()
    db.refresh(todo)

    db.close()

    return {"id": todo.id, "title": todo.title}
```

### 它在做什么

1. 先按 id 查对象
2. 如果没找到，返回 `None`
3. 找到了就改对象属性：
   ```python
   todo.title = title
   ```
4. 提交到数据库
5. 返回更新后的结果

### 二、ORM 版 `delete_todo()`

```python
def delete_todo(todo_id: int):
    db = SessionLocal()

    todo = db.query(Todo).filter(Todo.id == todo_id).first()
    if todo is None:
        db.close()
        return None

    result = {"id": todo.id, "title": todo.title}

    db.delete(todo)
    db.commit()
    db.close()

    return result
```

### 它在做什么

1. 先查要删的那条记录
2. 如果没有，就返回 `None`
3. 如果有，先把数据保存到 `result`
4. 然后执行：
   ```python
   db.delete(todo)
   ```
5. 再 `commit()`
6. 返回被删掉的数据

### 这一段最关键的理解

你现在已经可以开始对比：

#### 原生 SQL 版
- `SELECT`
- `INSERT`
- `UPDATE`
- `DELETE`

#### ORM 版
- `db.query(...)`
- `db.add(...)`
- `todo.title = ...`
- `db.delete(...)`

这两套是在做同一件事，只是写法不同。

## 第 6 段：完整回归测试（40 分钟）

### 要测的接口

#### 1. 查全部
```bash
curl "http://127.0.0.1:8000/todos"
```

#### 2. 新增
```bash
curl -X POST "http://127.0.0.1:8000/todos" \
  -H "Content-Type: application/json" \
  -d '{"title":"学习 SQLAlchemy"}'
```

#### 3. 查单条
```bash
curl "http://127.0.0.1:8000/todos/1"
```

#### 4. 修改
```bash
curl -X PUT "http://127.0.0.1:8000/todos/1" \
  -H "Content-Type: application/json" \
  -d '{"title":"学习 ORM 更新"}'
```

#### 5. 删除
```bash
curl -X DELETE "http://127.0.0.1:8000/todos/1"
```

#### 6. 查不存在的记录
```bash
curl "http://127.0.0.1:8000/todos/999"
```

预期：

- 返回 `404`
- 内容类似：
```json
{"detail":"Todo not found"}
```

## 今日收尾复盘（30 分钟）

### 你要自己写 8 句总结

1. `db.py` 负责什么
2. `models.py` 负责什么
3. `SessionLocal()` 是什么
4. `Todo` 类和 `todos` 表是什么关系
5. `db.query(Todo).all()` 大致对应什么 SQL
6. `db.add(todo)` 在做什么
7. `db.refresh(todo)` 为什么要用
8. 为什么 ORM 更适合后续真实后端项目

## 今日最低完成标准

如果今天飞机上时间有限，至少保证完成这 4 个：

1. 把 `db.py` 和 `models.py` 理顺
2. ORM 版 `get_all_todos()`
3. ORM 版 `get_todo_by_id()`
4. ORM 版 `create_todo()`

这 4 个完成，你今天就算达标。

## 今日完成后的判断标准

如果你能做到下面这些，就说明今天学成了：

- 能解释 `db.py` / `models.py` / `services.py` 的分工
- 能写 ORM 版读取接口
- 能写 ORM 版新增接口
- 知道 ORM 查询返回的是对象，不是 `sqlite3.Row`
- 知道 `Todo` 模型为什么可以映射到 `todos` 表

## 今日最终结论

今天这一整天，不是让你背 SQLAlchemy API，而是让你真正理解这件事：

**在 Python 后端里，数据库表可以被映射成 Python 类，数据库记录可以被当成对象处理。**

这就是你从“会写 CRUD”走向“更像真实后端工程”的关键一步。
