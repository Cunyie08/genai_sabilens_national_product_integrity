"""Seed script for Nigerian states table."""

import asyncio

from sqlalchemy import select

from backend.database import AsyncSessionLocal
from backend.models.analytics import NigerianState

NIGERIAN_STATES = [
    {"name": "Abia", "capital": "Umuahia", "region": "South East"},
    {"name": "Adamawa", "capital": "Yola", "region": "North East"},
    {"name": "Akwa Ibom", "capital": "Uyo", "region": "South South"},
    {"name": "Anambra", "capital": "Awka", "region": "South East"},
    {"name": "Bauchi", "capital": "Bauchi", "region": "North East"},
    {"name": "Bayelsa", "capital": "Yenagoa", "region": "South South"},
    {"name": "Benue", "capital": "Makurdi", "region": "North Central"},
    {"name": "Borno", "capital": "Maiduguri", "region": "North East"},
    {"name": "Cross River", "capital": "Calabar", "region": "South South"},
    {"name": "Delta", "capital": "Asaba", "region": "South South"},
    {"name": "Ebonyi", "capital": "Abakaliki", "region": "South East"},
    {"name": "Edo", "capital": "Benin City", "region": "South South"},
    {"name": "Ekiti", "capital": "Ado-Ekiti", "region": "South West"},
    {"name": "Enugu", "capital": "Enugu", "region": "South East"},
    {"name": "FCT", "capital": "Abuja", "region": "North Central"},
    {"name": "Gombe", "capital": "Gombe", "region": "North East"},
    {"name": "Imo", "capital": "Owerri", "region": "South East"},
    {"name": "Jigawa", "capital": "Dutse", "region": "North West"},
    {"name": "Kaduna", "capital": "Kaduna", "region": "North West"},
    {"name": "Kano", "capital": "Kano", "region": "North West"},
    {"name": "Katsina", "capital": "Katsina", "region": "North West"},
    {"name": "Kebbi", "capital": "Birnin Kebbi", "region": "North West"},
    {"name": "Kogi", "capital": "Lokoja", "region": "North Central"},
    {"name": "Kwara", "capital": "Ilorin", "region": "North Central"},
    {"name": "Lagos", "capital": "Ikeja", "region": "South West"},
    {"name": "Nasarawa", "capital": "Lafia", "region": "North Central"},
    {"name": "Niger", "capital": "Minna", "region": "North Central"},
    {"name": "Ogun", "capital": "Abeokuta", "region": "South West"},
    {"name": "Ondo", "capital": "Akure", "region": "South West"},
    {"name": "Osun", "capital": "Osogbo", "region": "South West"},
    {"name": "Oyo", "capital": "Ibadan", "region": "South West"},
    {"name": "Plateau", "capital": "Jos", "region": "North Central"},
    {"name": "Rivers", "capital": "Port Harcourt", "region": "South South"},
    {"name": "Sokoto", "capital": "Sokoto", "region": "North West"},
    {"name": "Taraba", "capital": "Jalingo", "region": "North East"},
    {"name": "Yobe", "capital": "Damaturu", "region": "North East"},
    {"name": "Zamfara", "capital": "Gusau", "region": "North West"},
]


async def seed_nigerian_states() -> None:
    async with AsyncSessionLocal() as session:
        existing_names = set((await session.execute(select(NigerianState.name))).scalars().all())
        to_insert = [
            NigerianState(name=item["name"], capital=item["capital"], region=item["region"])
            for item in NIGERIAN_STATES
            if item["name"] not in existing_names
        ]

        if to_insert:
            session.add_all(to_insert)
            await session.commit()
            print(f"Inserted {len(to_insert)} states.")
        else:
            print("No new states to insert.")


if __name__ == "__main__":
    asyncio.run(seed_nigerian_states())
