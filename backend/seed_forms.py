"""Recreate default forms (OTD + Brig) if they don't exist."""
import asyncio
import json
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.form import FormTemplate

OTD_FLOW = {
    "startId": "start",
    "nodes": [
        {"id": "start",         "type": "start",   "label": "Начало",            "position": {"x": 300, "y": 50},  "defaultNextId": "date"},
        {"id": "date",          "type": "date",    "label": "Дата работы",        "position": {"x": 300, "y": 170}, "defaultNextId": "hours"},
        {"id": "hours",         "type": "number",  "label": "Количество часов",   "position": {"x": 300, "y": 290}, "defaultNextId": "machine_type"},
        {"id": "machine_type",  "type": "choice",  "label": "Тип техники",        "position": {"x": 300, "y": 410},
         "source": "machine_kinds", "defaultNextId": "activity_tech"},
        {"id": "activity_tech", "type": "choice",  "label": "Вид деятельности",   "position": {"x": 100, "y": 530},
         "source": "activities_tech", "defaultNextId": "location"},
        {"id": "location",      "type": "choice",  "label": "Поле / Склад",       "position": {"x": 100, "y": 650},
         "source": "locations", "defaultNextId": "confirm"},
        {"id": "work_type",     "type": "choice",  "label": "Тип работ",          "position": {"x": 500, "y": 410},
         "options": ["Техника", "Ручная"],
         "conditionalNext": [
             {"option": "Техника", "nextId": "machine_type"},
             {"option": "Ручная",  "nextId": "activity_hand"}
         ]},
        {"id": "activity_hand", "type": "choice",  "label": "Вид ручной работы",  "position": {"x": 700, "y": 530},
         "source": "activities_hand", "defaultNextId": "confirm"},
        {"id": "confirm",       "type": "confirm", "label": "Подтверждение",      "position": {"x": 300, "y": 780}},
    ]
}

BRIG_FLOW = {
    "startId": "start",
    "nodes": [
        {"id": "start",    "type": "start",   "label": "Начало",          "position": {"x": 300, "y": 50},  "defaultNextId": "date"},
        {"id": "date",     "type": "date",    "label": "Дата",            "position": {"x": 300, "y": 170}, "defaultNextId": "workers"},
        {"id": "workers",  "type": "number",  "label": "Количество рабочих", "position": {"x": 300, "y": 290}, "defaultNextId": "note"},
        {"id": "note",     "type": "text",    "label": "Примечание",      "position": {"x": 300, "y": 410}, "defaultNextId": "confirm"},
        {"id": "confirm",  "type": "confirm", "label": "Подтверждение",   "position": {"x": 300, "y": 530}},
    ]
}

FORMS = [
    {
        "name": "otd",
        "title": "ОТД Отчёт",
        "schema": {"fields": [], "flow": OTD_FLOW},
        "roles": ["user", "brigadier"],
        "is_active": True,
    },
    {
        "name": "brig",
        "title": "Отчёт бригадира",
        "schema": {"fields": [], "flow": BRIG_FLOW},
        "roles": ["brigadier", "tim"],
        "is_active": True,
    },
]

async def main():
    async with AsyncSessionLocal() as db:
        for f in FORMS:
            res = await db.execute(select(FormTemplate).where(FormTemplate.name == f["name"]))
            existing = res.scalar_one_or_none()
            if existing:
                print(f"  EXISTS: {f['name']} ({existing.title})")
            else:
                obj = FormTemplate(**f)
                db.add(obj)
                await db.commit()
                print(f"  CREATED: {f['name']} ({f['title']})")

if __name__ == "__main__":
    asyncio.run(main())
