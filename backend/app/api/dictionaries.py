from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from app.core.database import get_db
from app.models.dictionary import Activity, Location, MachineKind, MachineItem, Crop, CustomDict, CustomDictItem
from app.schemas.dictionary import (
    ActivityOut, ActivityCreate, ActivityUpdate,
    LocationOut, LocationCreate, LocationUpdate,
    MachineKindOut, MachineKindCreate, MachineKindUpdate,
    MachineItemOut, MachineItemCreate,
    CropOut, CropCreate, CropUpdate,
    CustomDictOut, CustomDictCreate, CustomDictUpdate,
    CustomDictItemOut, CustomDictItemCreate, CustomDictItemUpdate,
    DictionariesOut, ReorderRequest
)
from app.api.deps import get_current_user, require_admin

router = APIRouter(prefix="/dictionaries", tags=["dictionaries"])


@router.get("", response_model=DictionariesOut)
async def get_all(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    acts  = (await db.execute(select(Activity).order_by(Activity.grp, Activity.pos))).scalars().all()
    locs  = (await db.execute(select(Location).order_by(Location.grp, Location.pos))).scalars().all()
    kinds = (await db.execute(select(MachineKind).order_by(MachineKind.pos))).scalars().all()
    items = (await db.execute(select(MachineItem).order_by(MachineItem.kind_id, MachineItem.pos))).scalars().all()
    crops = (await db.execute(select(Crop).order_by(Crop.pos))).scalars().all()
    cdicts = (await db.execute(select(CustomDict).order_by(CustomDict.pos))).scalars().all()
    cditems = (await db.execute(select(CustomDictItem).order_by(CustomDictItem.dict_id, CustomDictItem.pos))).scalars().all()
    # attach items to each custom dict
    cditems_map: dict[int, list] = {}
    for ci in cditems:
        cditems_map.setdefault(ci.dict_id, []).append(ci)
    custom_dicts_out = [
        CustomDictOut(id=d.id, name=d.name, pos=d.pos, items=cditems_map.get(d.id, []))
        for d in cdicts
    ]
    return DictionariesOut(activities=acts, locations=locs, machine_kinds=kinds, machine_items=items, crops=crops, custom_dicts=custom_dicts_out)


# ── Activities ──
@router.get("/activities", response_model=list[ActivityOut])
async def list_activities(grp: str | None = None, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    q = select(Activity).order_by(Activity.grp, Activity.pos)
    if grp:
        q = q.where(Activity.grp == grp)
    return (await db.execute(q)).scalars().all()


@router.post("/activities", response_model=ActivityOut, status_code=201)
async def create_activity(body: ActivityCreate, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    obj = Activity(**body.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


@router.patch("/activities/{activity_id}", response_model=ActivityOut)
async def update_activity(activity_id: int, body: ActivityUpdate, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    result = await db.execute(select(Activity).where(Activity.id == activity_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    await db.commit()
    await db.refresh(obj)
    return obj


@router.delete("/activities/{activity_id}", status_code=204)
async def delete_activity(activity_id: int, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    result = await db.execute(select(Activity).where(Activity.id == activity_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Not found")
    await db.delete(obj)
    await db.commit()


# ── Locations ──
@router.get("/locations", response_model=list[LocationOut])
async def list_locations(grp: str | None = None, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    q = select(Location).order_by(Location.grp, Location.pos)
    if grp:
        q = q.where(Location.grp == grp)
    return (await db.execute(q)).scalars().all()


@router.post("/locations", response_model=LocationOut, status_code=201)
async def create_location(body: LocationCreate, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    obj = Location(**body.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


@router.patch("/locations/{loc_id}", response_model=LocationOut)
async def update_location(loc_id: int, body: LocationUpdate, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    result = await db.execute(select(Location).where(Location.id == loc_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    await db.commit()
    await db.refresh(obj)
    return obj


@router.delete("/locations/{loc_id}", status_code=204)
async def delete_location(loc_id: int, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    result = await db.execute(select(Location).where(Location.id == loc_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Not found")
    await db.delete(obj)
    await db.commit()


# ── Crops ──
@router.get("/crops", response_model=list[CropOut])
async def list_crops(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    return (await db.execute(select(Crop).order_by(Crop.pos))).scalars().all()


@router.post("/crops", response_model=CropOut, status_code=201)
async def create_crop(body: CropCreate, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    obj = Crop(**body.model_dump())
    db.add(obj)
    await db.commit()
    return obj


@router.patch("/crops/{name}", response_model=CropOut)
async def update_crop(name: str, body: CropUpdate, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    result = await db.execute(select(Crop).where(Crop.name == name))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Not found")
    data = body.model_dump(exclude_unset=True)
    new_name = data.pop("name", None)
    if new_name is not None and new_name.strip() and new_name.strip() != name:
        new_name = new_name.strip()
        conflict = await db.execute(select(Crop).where(Crop.name == new_name))
        if conflict.scalar_one_or_none():
            raise HTTPException(400, "Культура с таким названием уже есть")
        pos, mode, options, message = obj.pos, obj.mode, obj.options, obj.message
        await db.delete(obj)
        await db.flush()
        obj = Crop(name=new_name, pos=pos, mode=mode, options=options, message=message)
        db.add(obj)
        await db.flush()
        for k, v in data.items():
            setattr(obj, k, v)
        await db.commit()
        await db.refresh(obj)
        return obj
    for k, v in data.items():
        setattr(obj, k, v)
    await db.commit()
    await db.refresh(obj)
    return obj


@router.delete("/crops/{name}", status_code=204)
async def delete_crop(name: str, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    result = await db.execute(select(Crop).where(Crop.name == name))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Not found")
    await db.delete(obj)
    await db.commit()


# ── Machine Kinds ──
@router.get("/machine-kinds", response_model=list[MachineKindOut])
async def list_machine_kinds(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    return (await db.execute(select(MachineKind).order_by(MachineKind.pos))).scalars().all()


@router.post("/machine-kinds", response_model=MachineKindOut, status_code=201)
async def create_machine_kind(body: MachineKindCreate, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    obj = MachineKind(**body.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


@router.patch("/machine-kinds/{kind_id}", response_model=MachineKindOut)
async def update_machine_kind(kind_id: int, body: MachineKindUpdate, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    result = await db.execute(select(MachineKind).where(MachineKind.id == kind_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    await db.commit()
    await db.refresh(obj)
    return obj


@router.delete("/machine-kinds/{kind_id}", status_code=204)
async def delete_machine_kind(kind_id: int, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    result = await db.execute(select(MachineKind).where(MachineKind.id == kind_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Not found")
    await db.delete(obj)
    await db.commit()


# ── Machine Items ──
@router.get("/machine-items", response_model=list[MachineItemOut])
async def list_machine_items(kind_id: int | None = None, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    q = select(MachineItem).order_by(MachineItem.pos)
    if kind_id:
        q = q.where(MachineItem.kind_id == kind_id)
    return (await db.execute(q)).scalars().all()


@router.post("/machine-items", response_model=MachineItemOut, status_code=201)
async def create_machine_item(body: MachineItemCreate, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    obj = MachineItem(**body.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


@router.delete("/machine-items/{item_id}", status_code=204)
async def delete_machine_item(item_id: int, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    result = await db.execute(select(MachineItem).where(MachineItem.id == item_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Not found")
    await db.delete(obj)
    await db.commit()


# ── Custom Dicts ──
@router.get("/custom", response_model=list[CustomDictOut])
async def list_custom_dicts(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    dicts = (await db.execute(select(CustomDict).order_by(CustomDict.pos))).scalars().all()
    ditems = (await db.execute(select(CustomDictItem).order_by(CustomDictItem.dict_id, CustomDictItem.pos))).scalars().all()
    imap: dict[int, list] = {}
    for ci in ditems:
        imap.setdefault(ci.dict_id, []).append(ci)
    return [CustomDictOut(id=d.id, name=d.name, pos=d.pos, items=imap.get(d.id, [])) for d in dicts]


@router.post("/custom", response_model=CustomDictOut, status_code=201)
async def create_custom_dict(body: CustomDictCreate, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    obj = CustomDict(**body.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return CustomDictOut(id=obj.id, name=obj.name, pos=obj.pos, items=[])


@router.patch("/custom/{dict_id}", response_model=CustomDictOut)
async def update_custom_dict(dict_id: int, body: CustomDictUpdate, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    result = await db.execute(select(CustomDict).where(CustomDict.id == dict_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    await db.commit()
    await db.refresh(obj)
    items = (await db.execute(select(CustomDictItem).where(CustomDictItem.dict_id == dict_id).order_by(CustomDictItem.pos))).scalars().all()
    return CustomDictOut(id=obj.id, name=obj.name, pos=obj.pos, items=list(items))


@router.delete("/custom/{dict_id}", status_code=204)
async def delete_custom_dict(dict_id: int, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    result = await db.execute(select(CustomDict).where(CustomDict.id == dict_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Not found")
    await db.delete(obj)
    await db.commit()


@router.post("/custom/{dict_id}/items", response_model=CustomDictItemOut, status_code=201)
async def create_custom_dict_item(dict_id: int, body: CustomDictItemCreate, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    obj = CustomDictItem(dict_id=dict_id, value=body.value, pos=body.pos)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


@router.patch("/custom/items/{item_id}", response_model=CustomDictItemOut)
async def update_custom_dict_item(item_id: int, body: CustomDictItemUpdate, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    result = await db.execute(select(CustomDictItem).where(CustomDictItem.id == item_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    await db.commit()
    await db.refresh(obj)
    return obj


@router.delete("/custom/items/{item_id}", status_code=204)
async def delete_custom_dict_item(item_id: int, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    result = await db.execute(select(CustomDictItem).where(CustomDictItem.id == item_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Not found")
    await db.delete(obj)
    await db.commit()
