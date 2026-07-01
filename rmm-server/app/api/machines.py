"""Machine management routes: enroll, list, get, update, delete, regenerate token."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_event
from app.core.deps import get_current_active_user
from app.core.security import generate_agent_token
from app.database import get_db
from app.models.machine import Machine
from app.models.user import User
from app.schemas.machine import (
    MachineCreate,
    MachineEnrolled,
    MachineOut,
    MachineUpdate,
)

router = APIRouter(prefix="/api/machines", tags=["machines"])


@router.post("", response_model=MachineEnrolled, status_code=status.HTTP_201_CREATED)
async def enroll_machine(
    payload: MachineCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> MachineEnrolled:
    """Create a machine and generate its unique agent token (shown once)."""
    raw, token_hash, prefix = generate_agent_token()
    machine = Machine(
        name=payload.name,
        notes=payload.notes,
        token_hash=token_hash,
        token_prefix=prefix,
    )
    db.add(machine)
    await db.commit()
    await db.refresh(machine)
    await log_event(
        db, "machine.enrolled", actor=user.email, machine_id=machine.id, admin_id=user.id,
        detail={"name": machine.name},
    )
    base = MachineOut.model_validate(machine).model_dump()
    return MachineEnrolled(**base, agent_token=raw)  # plaintext returned once


@router.get("", response_model=list[MachineOut])
async def list_machines(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> list[Machine]:
    rows = await db.scalars(select(Machine).order_by(Machine.name))
    return list(rows)


@router.get("/{machine_id}", response_model=MachineOut)
async def get_machine(
    machine_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> Machine:
    machine = await db.get(Machine, machine_id)
    if not machine:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Machine not found")
    return machine


@router.patch("/{machine_id}", response_model=MachineOut)
async def update_machine(
    machine_id: uuid.UUID,
    payload: MachineUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> Machine:
    machine = await db.get(Machine, machine_id)
    if not machine:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Machine not found")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(machine, field, value)
    await db.commit()
    await db.refresh(machine)
    await log_event(db, "machine.updated", actor=user.email, machine_id=machine.id,
                    admin_id=user.id, detail=data)
    return machine


@router.post("/{machine_id}/regenerate-token", response_model=MachineEnrolled)
async def regenerate_token(
    machine_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> MachineEnrolled:
    machine = await db.get(Machine, machine_id)
    if not machine:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Machine not found")
    raw, token_hash, prefix = generate_agent_token()
    machine.token_hash = token_hash
    machine.token_prefix = prefix
    await db.commit()
    await db.refresh(machine)
    await log_event(db, "machine.token_regenerated", actor=user.email,
                    machine_id=machine.id, admin_id=user.id)
    base = MachineOut.model_validate(machine).model_dump()
    return MachineEnrolled(**base, agent_token=raw)


@router.delete("/{machine_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_machine(
    machine_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> None:
    machine = await db.get(Machine, machine_id)
    if not machine:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Machine not found")
    name = machine.name
    await db.delete(machine)
    await db.commit()
    await log_event(db, "machine.deleted", actor=user.email, machine_id=machine_id,
                    admin_id=user.id, detail={"name": name})
