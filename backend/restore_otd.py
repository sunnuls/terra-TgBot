"""Restore OTD and BRIG default flows in DB."""
import asyncio
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from app.core.database import AsyncSessionLocal
from app.models.form import FormTemplate

OTD_FLOW = {
    "startId": "start",
    "nodes": [
        {"id":"start","type":"start","label":"Начало","position":{"x":300,"y":50},"defaultNextId":"date"},
        {"id":"date","type":"date","label":"Дата работы","position":{"x":300,"y":170},"defaultNextId":"hours"},
        {"id":"hours","type":"number","label":"Количество часов","position":{"x":300,"y":290},"defaultNextId":"work_type"},
        {"id":"work_type","type":"choice","label":"Тип работ","position":{"x":300,"y":410},
         "options":["Техника","Ручная"],
         "conditionalNext":[{"option":"Техника","nextId":"machine_type"},{"option":"Ручная","nextId":"activity_hand"}]},
        {"id":"machine_type","type":"choice","label":"Тип техники","position":{"x":100,"y":530},
         "source":"machine_kinds","defaultNextId":"activity_tech"},
        {"id":"activity_tech","type":"choice","label":"Вид деятельности","position":{"x":100,"y":660},
         "source":"activities_tech","defaultNextId":"location"},
        {"id":"location","type":"choice","label":"Поле / Склад","position":{"x":100,"y":790},
         "source":"locations","defaultNextId":"confirm"},
        {"id":"activity_hand","type":"choice","label":"Вид ручной работы","position":{"x":500,"y":530},
         "source":"activities_hand","defaultNextId":"confirm"},
        {"id":"confirm","type":"confirm","label":"Подтверждение","position":{"x":300,"y":920}},
    ]
}

BRIG_FLOW = {
    "startId": "start",
    "nodes": [
        {"id":"start","type":"start","label":"Начало","position":{"x":300,"y":50},"defaultNextId":"date"},
        {"id":"date","type":"date","label":"Дата","position":{"x":300,"y":170},"defaultNextId":"workers"},
        {"id":"workers","type":"number","label":"Количество рабочих","position":{"x":300,"y":290},"defaultNextId":"note"},
        {"id":"note","type":"text","label":"Примечание","position":{"x":300,"y":410},"defaultNextId":"confirm"},
        {"id":"confirm","type":"confirm","label":"Подтверждение","position":{"x":300,"y":530}},
    ]
}

async def main():
    async with AsyncSessionLocal() as db:
        for name, flow in [("otd", OTD_FLOW), ("brig", BRIG_FLOW)]:
            res = await db.execute(select(FormTemplate).where(FormTemplate.name == name))
            f = res.scalar_one_or_none()
            if f:
                f.schema = {"fields": [], "flow": flow}
                flag_modified(f, "schema")
                await db.commit()
                print(f"  {name}: restored {len(flow['nodes'])} nodes")

if __name__ == "__main__":
    asyncio.run(main())
