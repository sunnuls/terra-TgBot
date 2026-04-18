from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.models.group import Group, GroupMember
from app.models.user import User
from app.schemas.group import GroupCreate, GroupUpdate, GroupOut, GroupMemberAdd, GroupMemberOut
from app.api.deps import get_current_user, require_admin

router = APIRouter(prefix="/groups", tags=["groups"])


async def _build_group_out(group: Group, db: AsyncSession, depth: int = 2) -> GroupOut:
    count_result = await db.execute(
        select(func.count()).where(GroupMember.group_id == group.id)
    )
    member_count = count_result.scalar() or 0

    children = []
    if depth > 0:
        child_result = await db.execute(select(Group).where(Group.parent_id == group.id).order_by(Group.name))
        for child in child_result.scalars().all():
            children.append(await _build_group_out(child, db, depth - 1))

    return GroupOut(
        id=group.id,
        name=group.name,
        parent_id=group.parent_id,
        created_by=group.created_by,
        created_at=group.created_at,
        children=children,
        member_count=member_count,
    )


@router.get("", response_model=list[GroupOut])
async def list_groups(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(Group).where(Group.parent_id.is_(None)).order_by(Group.name))
    return [await _build_group_out(g, db) for g in result.scalars().all()]


@router.post("", response_model=GroupOut, status_code=201)
async def create_group(
    body: GroupCreate,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user, _ = admin
    if body.parent_id:
        parent = await db.execute(select(Group).where(Group.id == body.parent_id))
        if not parent.scalar_one_or_none():
            raise HTTPException(404, "Parent group not found")

    group = Group(name=body.name, parent_id=body.parent_id, created_by=user.id)
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return await _build_group_out(group, db)


@router.patch("/{group_id}", response_model=GroupOut)
async def update_group(
    group_id: int,
    body: GroupUpdate,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(404, "Group not found")
    if body.name is not None:
        group.name = body.name
    if body.parent_id is not None:
        group.parent_id = body.parent_id
    await db.commit()
    await db.refresh(group)
    return await _build_group_out(group, db)


@router.delete("/{group_id}", status_code=204)
async def delete_group(group_id: int, admin=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(404, "Group not found")
    await db.delete(group)
    await db.commit()


@router.get("/{group_id}/members", response_model=list[GroupMemberOut])
async def list_members(group_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(
        select(GroupMember, User).join(User, GroupMember.user_id == User.id).where(GroupMember.group_id == group_id)
    )
    items = []
    for gm, user in result.all():
        items.append(GroupMemberOut(
            user_id=gm.user_id,
            group_id=gm.group_id,
            role=gm.role,
            full_name=user.full_name,
            username=user.username,
        ))
    return items


@router.post("/{group_id}/members", status_code=201)
async def add_member(
    group_id: int,
    body: GroupMemberAdd,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == body.user_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Already a member")
    db.add(GroupMember(group_id=group_id, user_id=body.user_id, role=body.role))
    await db.commit()
    return {"ok": True}


@router.delete("/{group_id}/members/{user_id}", status_code=204)
async def remove_member(group_id: int, user_id: int, admin=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)
    )
    gm = result.scalar_one_or_none()
    if not gm:
        raise HTTPException(404, "Member not found")
    await db.delete(gm)
    await db.commit()
