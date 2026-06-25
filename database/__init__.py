import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:vidhi@localhost:5432/authclaw")

engine = create_engine(DATABASE_URL)
