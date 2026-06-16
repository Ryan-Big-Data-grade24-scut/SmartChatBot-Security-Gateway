import psycopg2
import psycopg2.pool
from contextlib import contextmanager
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=2,
    maxconn=10,
    host=DB_HOST,
    port=DB_PORT,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
)

@contextmanager
def get_conn():
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)

@contextmanager
def get_cursor():
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            yield cur
        finally:
            cur.close()
