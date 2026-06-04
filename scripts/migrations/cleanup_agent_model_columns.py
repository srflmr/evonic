#!/usr/bin/env python3
"""Migration script: drop legacy `model` column, rename `default_model_id` → `model_id`."""

import os
import sys
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, 'shared', 'db', 'evonic.db')


def main():
    print("=== Agent Model Column Cleanup Migration ===")
    print(f"Database: {DB_PATH}")
    print()

    if not os.path.isfile(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Step 1: Add model_id column if not present
    print("Step 1: Ensuring model_id column exists...")
    try:
        cursor.execute("ALTER TABLE agents ADD COLUMN model_id TEXT")
        print("  [OK] Added model_id column")
    except sqlite3.OperationalError:
        print("  [OK] model_id column already exists")

    # Step 2: Copy default_model_id → model_id
    print("Step 2: Copying default_model_id → model_id...")
    try:
        cursor.execute(
            "UPDATE agents SET model_id = default_model_id "
            "WHERE model_id IS NULL AND default_model_id IS NOT NULL"
        )
        print(f"  [OK] Updated {cursor.rowcount} row(s)")
    except sqlite3.OperationalError as e:
        print(f"  [WARN] Could not copy data: {e}")

    # Step 3: Drop default_model_id column
    print("Step 3: Dropping default_model_id column...")
    try:
        cursor.execute("ALTER TABLE agents DROP COLUMN default_model_id")
        print("  [OK] Dropped default_model_id column")
    except sqlite3.OperationalError:
        print("  [WARN] DROP COLUMN not supported (SQLite < 3.35.0) — column left unused")

    # Step 4: Drop legacy model column
    print("Step 4: Dropping legacy model column...")
    try:
        cursor.execute("ALTER TABLE agents DROP COLUMN model")
        print("  [OK] Dropped model column")
    except sqlite3.OperationalError:
        print("  [WARN] DROP COLUMN not supported (SQLite < 3.35.0) — column left unused")

    conn.commit()
    conn.close()

    print()
    print("=== Summary ===")
    print("Migration complete.")
    print("  - model_id: added/copied from default_model_id")
    print("  - default_model_id: dropped (or left unused on old SQLite)")
    print("  - model: dropped (or left unused on old SQLite)")
    print("Done.")


if __name__ == '__main__':
    main()
