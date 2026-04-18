"""
Migration script: copy data from the existing SQLite (reports.db) into the new PostgreSQL.
Run once after setting up the new backend:
    python migrate_from_sqlite.py --sqlite-path ../reports.db
"""
import asyncio
import sqlite3
import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User, AuthCredential, UserRole
from app.models.report import Report, BrigadierReport
from app.models.dictionary import Activity, Location, MachineKind, MachineItem, Crop


async def migrate(sqlite_path: str, default_password: str):
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row

    async with AsyncSessionLocal() as db:
        # ── Users ──────────────────────────────────────────────────────────────
        users_rows = conn.execute("SELECT * FROM users").fetchall()
        print(f"Migrating {len(users_rows)} users...")
        for row in users_rows:
            existing = await db.get(User, row["user_id"])
            if existing:
                continue
            user = User(
                id=row["user_id"],
                full_name=row.get("full_name"),
                username=row.get("username"),
                phone=row.get("phone"),
                tz=row.get("tz", "UTC"),
            )
            db.add(user)

            login = row.get("username") or row.get("phone") or str(row["user_id"])
            cred = AuthCredential(user_id=row["user_id"], login=login, password_hash=hash_password(default_password))
            db.add(cred)

        await db.flush()

        # ── Roles ──────────────────────────────────────────────────────────────
        try:
            role_rows = conn.execute("SELECT * FROM user_roles").fetchall()
            print(f"Migrating {len(role_rows)} roles...")
            for row in role_rows:
                existing = await db.get(UserRole, row["user_id"])
                if not existing:
                    db.add(UserRole(user_id=row["user_id"], role=row["role"]))
            await db.flush()
        except Exception as e:
            print(f"Roles migration skipped: {e}")

        # ── Dictionaries ───────────────────────────────────────────────────────
        try:
            acts = conn.execute("SELECT * FROM activities").fetchall()
            print(f"Migrating {len(acts)} activities...")
            for row in acts:
                db.add(Activity(id=row["id"], name=row["name"], grp=row["grp"], pos=row.get("pos", 0)))
            await db.flush()
        except Exception as e:
            print(f"Activities migration skipped: {e}")

        try:
            locs = conn.execute("SELECT * FROM locations").fetchall()
            print(f"Migrating {len(locs)} locations...")
            for row in locs:
                db.add(Location(id=row["id"], name=row["name"], grp=row["grp"], pos=row.get("pos", 0)))
            await db.flush()
        except Exception as e:
            print(f"Locations migration skipped: {e}")

        try:
            crops = conn.execute("SELECT * FROM crops").fetchall()
            print(f"Migrating {len(crops)} crops...")
            for row in crops:
                db.add(Crop(name=row["name"], pos=row.get("pos", 0)))
            await db.flush()
        except Exception as e:
            print(f"Crops migration skipped: {e}")

        try:
            kinds = conn.execute("SELECT * FROM machine_kinds").fetchall()
            for row in kinds:
                db.add(MachineKind(id=row["id"], title=row["title"], mode=row.get("mode", "list"), pos=row.get("pos", 0)))
            await db.flush()
            items = conn.execute("SELECT * FROM machine_items").fetchall()
            for row in items:
                db.add(MachineItem(id=row["id"], kind_id=row["kind_id"], name=row["name"], pos=row.get("pos", 0)))
            await db.flush()
        except Exception as e:
            print(f"Machines migration skipped: {e}")

        # ── Reports ────────────────────────────────────────────────────────────
        reports_rows = conn.execute("SELECT * FROM reports").fetchall()
        print(f"Migrating {len(reports_rows)} OTD reports...")
        for row in reports_rows:
            db.add(Report(
                id=row["id"],
                user_id=row.get("user_id"),
                reg_name=row.get("reg_name"),
                username=row.get("username"),
                location=row.get("location"),
                location_grp=row.get("location_grp"),
                activity=row.get("activity"),
                activity_grp=row.get("activity_grp"),
                work_date=row.get("work_date"),
                hours=row.get("hours"),
                machine_type=row.get("machine_type"),
                machine_name=row.get("machine_name"),
                crop=row.get("crop"),
                trips=row.get("trips"),
            ))
        await db.flush()

        # ── Brigadier Reports ──────────────────────────────────────────────────
        try:
            brig_rows = conn.execute("SELECT * FROM brigadier_reports").fetchall()
            print(f"Migrating {len(brig_rows)} brigadier reports...")
            for row in brig_rows:
                db.add(BrigadierReport(
                    id=row["id"],
                    user_id=row.get("user_id"),
                    username=row.get("username"),
                    work_type=row.get("work_type"),
                    field=row.get("field"),
                    shift=row.get("shift"),
                    rows=row.get("rows"),
                    bags=row.get("bags"),
                    workers=row.get("workers"),
                    work_date=row.get("work_date"),
                ))
            await db.flush()
        except Exception as e:
            print(f"Brigadier reports migration skipped: {e}")

        await db.commit()

    conn.close()
    print("Migration complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite-path", default="../reports.db")
    parser.add_argument("--default-password", default="Change123!")
    args = parser.parse_args()

    asyncio.run(migrate(args.sqlite_path, args.default_password))
