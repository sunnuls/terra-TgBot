from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm.attributes import flag_modified
from app.core.database import get_db
from app.models.form import FormTemplate, FormAssignment
from app.models.user import UserRole
from app.schemas.form import FormTemplateCreate, FormTemplateUpdate, FormTemplateOut
from app.api.deps import get_current_user, require_admin
from app.models.user import User

router = APIRouter(prefix="/forms", tags=["forms"])


async def _form_to_out(form: FormTemplate, db: AsyncSession) -> FormTemplateOut:
    result = await db.execute(
        select(FormAssignment.role).where(
            FormAssignment.form_id == form.id,
            FormAssignment.role.isnot(None)
        )
    )
    roles = [r[0] for r in result.all()]
    return FormTemplateOut(
        id=form.id,
        name=form.name,
        title=form.title,
        schema=form.schema,
        is_active=form.is_active,
        created_by=form.created_by,
        created_at=form.created_at,
        roles=roles,
    )


@router.get("", response_model=list[FormTemplateOut])
async def list_forms(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    role_result = await db.execute(select(UserRole).where(UserRole.user_id == current_user.id))
    role_row = role_result.scalar_one_or_none()
    role = role_row.role if role_row else "user"

    # Support comma-separated multi-roles (e.g. "otd,brigadier")
    user_roles = [r.strip() for r in role.split(",")]

    if "admin" in user_roles:
        q = select(FormTemplate).order_by(FormTemplate.id)
    else:
        assigned = select(FormAssignment.form_id).where(FormAssignment.role.in_(user_roles))
        q = select(FormTemplate).where(
            FormTemplate.is_active == True,
            FormTemplate.id.in_(assigned)
        ).order_by(FormTemplate.id)

    result = await db.execute(q)
    forms = result.scalars().all()
    return [await _form_to_out(f, db) for f in forms]


@router.post("", response_model=FormTemplateOut, status_code=201)
async def create_form(
    body: FormTemplateCreate,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user, _ = admin
    existing = await db.execute(select(FormTemplate).where(FormTemplate.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Form name already exists")

    form = FormTemplate(
        name=body.name,
        title=body.title,
        schema=body.schema.model_dump(),
        created_by=user.id,
    )
    db.add(form)
    await db.flush()

    for role in body.roles:
        db.add(FormAssignment(form_id=form.id, role=role))
    for group_id in body.group_ids:
        db.add(FormAssignment(form_id=form.id, group_id=group_id))

    await db.commit()
    await db.refresh(form)
    return await _form_to_out(form, db)


@router.get("/{form_id}", response_model=FormTemplateOut)
async def get_form(form_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(FormTemplate).where(FormTemplate.id == form_id))
    form = result.scalar_one_or_none()
    if not form:
        raise HTTPException(404, "Not found")
    return await _form_to_out(form, db)


@router.patch("/{form_id}", response_model=FormTemplateOut)
async def update_form(
    form_id: int,
    body: FormTemplateUpdate,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(FormTemplate).where(FormTemplate.id == form_id))
    form = result.scalar_one_or_none()
    if not form:
        raise HTTPException(404, "Not found")

    if body.title is not None:
        form.title = body.title
    if body.schema is not None:
        form.schema = body.schema.model_dump()
        flag_modified(form, "schema")  # force SQLAlchemy to detect JSONB mutation
    if body.is_active is not None:
        form.is_active = body.is_active

    if body.roles is not None:
        await db.execute(delete(FormAssignment).where(
            FormAssignment.form_id == form_id,
            FormAssignment.role.isnot(None)
        ))
        for role in body.roles:
            db.add(FormAssignment(form_id=form_id, role=role))

    await db.commit()
    await db.refresh(form)
    return await _form_to_out(form, db)


@router.delete("/{form_id}", status_code=204)
async def delete_form(form_id: int, admin=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FormTemplate).where(FormTemplate.id == form_id))
    form = result.scalar_one_or_none()
    if not form:
        raise HTTPException(404, "Not found")
    await db.delete(form)
    await db.commit()
