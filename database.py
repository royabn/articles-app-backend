from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import re
import base64
from pathlib import Path
import tempfile
import sqlalchemy.dialects.postgresql.base as pg_base

def patched_get_server_version_info(self, connection):
        v = connection.exec_driver_sql("select pg_catalog.version()").scalar()
        m = re.search(r'v(\d+\.\d+\.\d+)', v)
        if not m:
            raise AssertionError(
                "Could not determine version from string '%s'" % v
            )
        return tuple(map(int, m.group(1).split('.')))

pg_base.PGDialect._get_server_version_info = patched_get_server_version_info

temp_dir = Path(tempfile.gettempdir())
cert_path = temp_dir / "root.crt"
cert_data = base64.b64decode(os.environ["DB_ROOT_CERT"])
cert_path.write_bytes(cert_data)

# DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sql_app.db")
DATABASE_URL = os.environ["DATABASE_URL"] + f"&sslrootcert={cert_path}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()