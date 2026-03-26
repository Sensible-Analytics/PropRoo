#!/usr/bin/env python3
import os

print("DATABASE_URL:", os.environ.get("DATABASE_URL", "NOT SET"))
print("DATA_DIR:", os.environ.get("DATA_DIR", "NOT SET"))
