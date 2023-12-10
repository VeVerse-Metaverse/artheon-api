import logging
import time
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app import config

# Get database configuration from settings.
database = config.settings.db.name
user = config.settings.db.user
password = config.settings.db.password
host = config.settings.db.host
port = config.settings.db.port

sqlalchemy_database_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"

engine = create_engine(sqlalchemy_database_url, encoding="utf8", echo=False, pool_size=200, max_overflow=50)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


@contextmanager
def session(auto_commit=True):
    sess = SessionLocal()
    try:
        yield sess
        if auto_commit:
            sess.commit()
    except SQLAlchemyError:
        sess.rollback()
        raise
    finally:
        sess.close()


logging.basicConfig()
logger = logging.getLogger("app.sqltime")
logger.setLevel(logging.DEBUG)


@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    if config.settings.env == 'development':
        conn.info.setdefault('query_start_time', []).append(time.time())
        logger.debug("\n=====\n%s\n-----\n-- %s\n-----", statement, parameters)


@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    if config.settings.env == 'development':
        total = time.time() - conn.info['query_start_time'].pop(-1)
        logger.debug("\nQuery completed in: %f\n=====\n", total)


# region Parser Helpers
def is_in_table(model, **kwargs):
    """Проверка наличия экземпляра в таблице.

    Parameters
    ----------
    # session : sqlalchemy.orm.session.Session
    #     Сессия.
    model : sqlalchemy.schema.Table, sqlalchemy.ext.declarative.api.DeclarativeMeta
        Таблица.
    **kwargs : dict
        Параметры фильтрации.

    Returns
    -------
    instance : bool
        True or False

    """
    with session() as db:
        instance = db.query(model).filter_by(**kwargs).first()
        if instance:
            return True

        return False


def get_or_create(model, **kwargs):
    """Получить или создать экземпляр модели.

    Parameters
    ----------
    # session : sqlalchemy.orm.session.Session
    #     Сессия.
    model : sqlalchemy.schema.Table, sqlalchemy.ext.declarative.api.DeclarativeMeta
        Таблица.
    **kwargs : dict
        Параметры фильтрации.

    Returns
    -------
    instance : Model
        Instacne of model.

    """
    with session() as db:
        instance = db.query(model).filter_by(**kwargs).first()
        if instance:
            return instance
        else:
            instance = model(**kwargs)
            db.add(instance)
            db.commit()
            return instance
# endregion
