import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    raise RuntimeError("DB_URL environment variable is not set")

# Schema migrations are managed via Alembic. Run `alembic upgrade head`
# to apply migrations instead of calling Base.metadata.create_all().

engine = create_engine(DB_URL, pool_pre_ping=True)


@event.listens_for(engine, "connect")
def set_search_path(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("SET search_path TO sq_schema, public")
    cursor.close()


SessionLocal = sessionmaker(bind=engine)


def get_session():
    return SessionLocal()
