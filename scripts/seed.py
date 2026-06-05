"""
Seed script — creates sample org, users, clients, and filings.
Safe to run multiple times: checks before inserting, never creates duplicates.

Usage:
    python scripts/seed.py
"""
import asyncio
import sys
import os

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from datetime import date, datetime, timezone
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from api.db.models import Organisation, User, Client, Filing

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_async_engine(DATABASE_URL, echo=False)
Session = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def get_or_create(session: AsyncSession, model, defaults: dict, **filters):
    """Fetch a row matching filters, or create it with filters + defaults."""
    result = await session.execute(select(model).filter_by(**filters))
    obj = result.scalar_one_or_none()
    if obj:
        return obj, False
    obj = model(**filters, **defaults)
    session.add(obj)
    await session.flush()
    return obj, True


async def seed():
    async with Session() as session:
        async with session.begin():

            # ── Organisation ──────────────────────────────────────────────────
            org, created = await get_or_create(
                session, Organisation,
                defaults={"is_active": True},
                name="Sharma & Associates",
            )
            if created:
                print(f"  ✓ Org created:   {org.name}")
            else:
                print(f"  · Org exists:    {org.name}")

            # ── Users ─────────────────────────────────────────────────────────
            users_data = [
                {
                    "email": "ca@sharma.com",
                    "name": "Rajesh Sharma",
                    "role": "owner",
                    "password": "test1234",
                },
                {
                    "email": "priya@sharma.com",
                    "name": "Priya Nair",
                    "role": "member",
                    "password": "test1234",
                },
                {
                    "email": "rahul@sharma.com",
                    "name": "Rahul Mehta",
                    "role": "member",
                    "password": "test1234",
                },
            ]

            user_objs = {}
            for u in users_data:
                user, created = await get_or_create(
                    session, User,
                    defaults={
                        "org_id": org.id,
                        "name": u["name"],
                        "role": u["role"],
                        "password_hash": pwd_context.hash(u["password"]),
                        "is_active": True,
                    },
                    email=u["email"],
                )
                user_objs[u["email"]] = user
                status = "✓ created" if created else "· exists "
                print(f"  {status}  User:    {u['name']} <{u['email']}> ({u['role']})")

            owner = user_objs["ca@sharma.com"]
            priya = user_objs["priya@sharma.com"]
            rahul = user_objs["rahul@sharma.com"]

            # ── Clients ───────────────────────────────────────────────────────
            clients_data = [
                {
                    "pan": "ABCPS1234F",
                    "name": "Suresh Patel",
                    "date_of_birth": date(1985, 3, 15),
                    "email": "suresh.patel@gmail.com",
                    "mobile": "9876543210",
                },
                {
                    "pan": "DEFKM5678G",
                    "name": "Kavya Menon",
                    "date_of_birth": date(1990, 7, 22),
                    "email": "kavya.menon@outlook.com",
                    "mobile": "9123456780",
                },
                {
                    "pan": "GHIAJ9012H",
                    "name": "Arjun Joshi",
                    "date_of_birth": date(1978, 11, 5),
                    "email": "arjun.joshi@yahoo.com",
                    "mobile": "9988776655",
                },
                {
                    "pan": "JKLRD3456J",
                    "name": "Deepa Rao",
                    "date_of_birth": date(1960, 6, 1),  # senior citizen
                    "email": "deepa.rao@gmail.com",
                    "mobile": "9112233445",
                },
                {
                    "pan": "MNOGT7890K",
                    "name": "Gautam Tiwari",
                    "date_of_birth": date(1995, 2, 28),
                    "email": "gautam.tiwari@gmail.com",
                    "mobile": "9001122334",
                },
            ]

            client_objs = []
            for c in clients_data:
                client, created = await get_or_create(
                    session, Client,
                    defaults={
                        "created_by": owner.id,
                        "date_of_birth": c["date_of_birth"],
                        "email": c["email"],
                        "mobile": c["mobile"],
                        "is_active": True,
                    },
                    org_id=org.id,
                    pan=c["pan"],
                    name=c["name"],
                )
                client_objs.append(client)
                status = "✓ created" if created else "· exists "
                print(f"  {status}  Client:  {c['name']} ({c['pan']})")

            # ── Filings — one per client, different statuses ───────────────────
            filings_data = [
                # (client, assigned_to, status)
                (client_objs[0], priya,  "draft"),
                (client_objs[1], rahul,  "reviewed"),
                (client_objs[2], priya,  "generated"),
                (client_objs[3], owner,  "filed"),
                (client_objs[4], rahul,  "draft"),
            ]

            for client, assigned, status in filings_data:
                filing, created = await get_or_create(
                    session, Filing,
                    defaults={
                        "org_id": org.id,
                        "assigned_to": assigned.id,
                        "last_modified_by": assigned.id,
                        "status": status,
                        "acknowledgement_number": "ITD-2025-SAMPLE-001" if status == "filed" else None,
                        "filed_at": datetime.now(tz=timezone.utc) if status == "filed" else None,
                        "filed_by": owner.id if status == "filed" else None,
                    },
                    client_id=client.id,
                    assessment_year="AY 2025-26",
                )
                status_str = "✓ created" if created else "· exists "
                print(f"  {status_str}  Filing:  {client.name} — AY 2025-26 [{filing.status}] → {assigned.name}")

    await engine.dispose()


if __name__ == "__main__":
    print("\nSeeding database...\n")
    asyncio.run(seed())
    print("\nDone. Login credentials:\n")
    print("  ca@sharma.com    / test1234  (owner)")
    print("  priya@sharma.com / test1234  (member)")
    print("  rahul@sharma.com / test1234  (member)\n")
