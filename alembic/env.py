from logging.config import fileConfig  # 读取 alembic.ini 里的日志配置

from sqlalchemy import engine_from_config, pool  # 用配置创建数据库引擎，并指定连接池策略
from alembic import context  # Alembic 的运行上下文对象，迁移时靠它工作

from agent_prototype.db import Base  # 导入你项目里的 Base，这里挂着所有模型元数据
from agent_prototype import models  # 必须导入模型模块，这样 SessionRecord 才会注册到 Base.metadata 上

config = context.config  # 取得 Alembic 当前加载的配置对象

if config.config_file_name is not None:  # 如果当前确实有配置文件
    fileConfig(config.config_file_name)  # 就把日志配置加载进来

target_metadata = Base.metadata  # 把项目里的元数据交给 Alembic，后面 autogenerate 就靠它比对


def run_migrations_offline() -> None:  # 离线模式：只生成 SQL，不真正连接数据库
    url = config.get_main_option("sqlalchemy.url")  # 从 alembic.ini 里读取数据库地址
    context.configure(  # 配置 Alembic 上下文
        url=url,  # 告诉它目标数据库地址
        target_metadata=target_metadata,  # 告诉它要对比哪份 ORM 元数据
        literal_binds=True,  # 把参数直接展开到 SQL 文本里
        compare_type=True,  # 以后字段类型变化时也能被检测出来
    )

    with context.begin_transaction():  # 开启迁移事务
        context.run_migrations()  # 执行迁移逻辑


def run_migrations_online() -> None:  # 在线模式：真实连接数据库并执行迁移
    connectable = engine_from_config(  # 根据配置创建数据库连接引擎
        config.get_section(config.config_ini_section, {}),  # 读取当前配置段
        prefix="sqlalchemy.",  # 只取 sqlalchemy. 开头的配置项
        poolclass=pool.NullPool,  # 迁移时不需要常驻连接池
    )

    with connectable.connect() as connection:  # 打开一个真实数据库连接
        context.configure(  # 配置迁移上下文
            connection=connection,  # 把真实连接交给 Alembic
            target_metadata=target_metadata,  # 继续告诉它 ORM 元数据来源
            compare_type=True,  # 保持类型比较开启
        )

        with context.begin_transaction():  # 开启迁移事务
            context.run_migrations()  # 执行迁移


if context.is_offline_mode():  # 如果当前是离线模式
    run_migrations_offline()  # 走离线分支
else:  # 否则
    run_migrations_online()  # 走在线分支
