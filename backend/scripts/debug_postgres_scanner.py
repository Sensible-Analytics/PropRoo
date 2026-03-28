#!/usr/bin/env python3
"""Debug postgres_scanner schema discovery."""

import os
import sys

sys.path.insert(0, "/app")

from app.config import settings

db_url = os.environ.get("DATABASE_URL")
print(f"DB URL: {db_url[:50]}...")

import duckdb

conn = duckdb.connect(database=":memory:")
conn.execute("INSTALL postgres_scanner; LOAD postgres_scanner;")
conn.execute(f"CALL postgres_attach('{db_url}')")

schemas = conn.execute("SELECT schema_name FROM information_schema.schemata").fetchall()
print("Schemas:", schemas)

tables = conn.execute(
    "SELECT table_schema, table_name FROM information_schema.tables ORDER BY table_schema"
).fetchall()
print("Tables found:")
for t in tables:
    print(f"  {t[0]}.{t[1]}")
