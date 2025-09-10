import os
from sqlalchemy import create_engine, text

url = os.environ.get("DATABASE_URL")
print("URL =", url)

try:
    eng = create_engine(url, future=True)
    with eng.connect() as c:
        print("SELECT 1 ->", c.execute(text("SELECT 1")).scalar())
    print("Conexión OK")
except Exception as e:
    print("FALLO:", type(e).__name__, e)
