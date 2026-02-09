from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.batch import Batch, BatchMember, BatchMemberRole, BatchMemberStatus
from app.schemas.batch import BatchCreate, BatchUpdate, BatchMemberCreate, BatchMemberUpdate
from app.crud.crud_chat import chat as crud_chat
from app.schemas.chat import ChatMemberCreate
from app.models.chat import ChatMemberRoleEnum

class CRUDBatch:
    async def get(self, db: AsyncSession, id: int) -> Optional[Batch]:
        result = await db.execute(select(Batch).filter(Batch.id == id))
        return result.scalars().first()

    async def get_with_members(self, db: AsyncSession, id: int) -> Optional[Batch]:
        result = await db.execute(
            select(Batch)
            .options(
                selectinload(Batch.members).selectinload(BatchMember.user),
                selectinload(Batch.teacher),
                selectinload(Batch.course)
            )
            .filter(Batch.id == id)
        )
        return result.scalars().first()

    async def get_multi(self, db: AsyncSession, *, skip: int = 0, limit: int = 100) -> List[Batch]:
        result = await db.execute(select(Batch).offset(skip).limit(limit))
        return result.scalars().all()

    async def create(self, db: AsyncSession, *, obj_in: BatchCreate) -> Batch:
        db_obj = Batch(
            course_id=obj_in.course_id,
            batch_name=obj_in.batch_name,
            teacher_id=obj_in.teacher_id,
            start_date=obj_in.start_date,
            end_date=obj_in.end_date,
            total_hours=obj_in.total_hours,
            consumed_hours=obj_in.consumed_hours,
            remaining_hours=obj_in.remaining_hours,
            schedule_time=obj_in.schedule_time,
            status=obj_in.status
        )
        db.add(db_obj)
        await db.flush()  # Generate ID for db_obj

        if obj_in.members:
            for member_in in obj_in.members:
                member_obj = BatchMember(
                    batch_id=db_obj.id,
                    user_id=member_in.user_id,
                    role_id=member_in.role_id,
                    role=BatchMemberRole.student, # Establish as student enum (or map from role_id if possible, but role_id is key)
                    status=BatchMemberStatus.active
                )
                db.add(member_obj)

        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(self, db: AsyncSession, *, db_obj: Batch, obj_in: BatchUpdate) -> Batch:
        update_data = obj_in.model_dump(exclude_unset=True)
        
        # Handle members separately
        members_in = update_data.pop("members", None)
        
        # Update scalar fields
        for field, value in update_data.items():
            setattr(db_obj, field, value)
            
        db.add(db_obj)
        
        if members_in is not None:
            # 1. Fetch existing members
            # We assume db_obj might not have members loaded, or we want fresh state.
            # But relationships might be loaded if we used get_with_members. 
            # Safest is to query existing association objects.
            stmt = select(BatchMember).filter(BatchMember.batch_id == db_obj.id)
            result = await db.execute(stmt)
            existing_members = result.scalars().all()
            existing_map = {m.user_id: m for m in existing_members}
            
            # 2. Process input members
            incoming_user_ids = set()
            
            # Find associated chat for this batch
            chat_obj = await crud_chat.get_by_batch(db, batch_id=db_obj.id)

            for m_in in members_in:
                user_id = m_in['user_id'] if isinstance(m_in, dict) else m_in.user_id
                role_id = m_in['role_id'] if isinstance(m_in, dict) else m_in.role_id
                incoming_user_ids.add(user_id)
                
                if user_id in existing_map:
                    # Update existing member (e.g. role)
                    existing_member = existing_map[user_id]
                    if existing_member.status != BatchMemberStatus.active:
                         existing_member.status = BatchMemberStatus.active
                    if role_id is not None:
                        existing_member.role_id = role_id
                    db.add(existing_member)
                else:
                    # Add new member
                    new_member = BatchMember(
                        batch_id=db_obj.id,
                        user_id=user_id,
                        role_id=role_id,
                        role=BatchMemberRole.student,
                        status=BatchMemberStatus.active
                    )
                    db.add(new_member)
                
                # Sync with Chat
                if chat_obj:
                    await crud_chat.add_member(
                        db, 
                        chat_id=chat_obj.id, 
                        member_in=ChatMemberCreate(
                            user_id=user_id,
                            role=ChatMemberRoleEnum.student
                        )
                    )
            
            # 3. Handle removals (or deactivations)
            for m in existing_members:
                if m.user_id not in incoming_user_ids and m.status == BatchMemberStatus.active:
                     # Option A: Hard delete
                     # await db.delete(m)
                     # Option B: Soft delete (set status inactive) - User prefer removal or inactive? 
                     # usually "remove" from list implies removal. Let's hard delete for cleanup or check requirements.
                     # The frontend calls it "removeMember". Codebase uses "remove" method which deletes.
                     # Let's delete to keep it clean, or update status.
                     # Given 'BatchMember' has status, maybe soft delete is better?
                     # But if I add again, I reactivate (above).
                     # Let's hard delete for now to match typical "Edit list" behavior unless "inactive" is tracked history.
                     await db.delete(m)

        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def remove(self, db: AsyncSession, *, id: int) -> Batch:
        result = await db.execute(select(Batch).filter(Batch.id == id))
        obj = result.scalars().first()
        await db.delete(obj)
        await db.commit()
        return obj

    async def get_by_course(self, db: AsyncSession, *, course_id: int, skip: int = 0, limit: int = 100) -> List[Batch]:
        result = await db.execute(select(Batch).filter(Batch.course_id == course_id).offset(skip).limit(limit))
        return result.scalars().all()
    
    async def get_active_batch_by_course(self, db: AsyncSession, *, course_id: int) -> Optional[Batch]:
        """Find an active batch for a course"""
        result = await db.execute(
            select(Batch)
            .filter(Batch.course_id == course_id, Batch.status == True)
            .order_by(Batch.created_at.desc())
        )
        return result.scalars().first()

    async def get_by_teacher(self, db: AsyncSession, *, teacher_id: UUID, skip: int = 0, limit: int = 100) -> List[Batch]:
        """
        Get batches assigned to a teacher.
        """
        result = await db.execute(
            select(Batch)
            .filter(Batch.teacher_id == teacher_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_student(self, db: AsyncSession, *, user_id: UUID, skip: int = 0, limit: int = 100) -> List[Batch]:
        """
        Get batches a student is enrolled in.
        """
        result = await db.execute(
            select(Batch)
            .join(BatchMember)
            .filter(
                BatchMember.user_id == user_id,
                BatchMember.status == BatchMemberStatus.active
            )
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

class CRUDBatchMember:
    async def get(self, db: AsyncSession, id: int) -> Optional[BatchMember]:
        result = await db.execute(select(BatchMember).filter(BatchMember.id == id))
        return result.scalars().first()

    async def create(self, db: AsyncSession, *, obj_in: BatchMemberCreate) -> BatchMember:
        db_obj = BatchMember(
            batch_id=obj_in.batch_id,
            user_id=obj_in.user_id,
            role_id=obj_in.role_id,
            role=obj_in.role,
            status=obj_in.status
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def get_by_batch(self, db: AsyncSession, *, batch_id: int, skip: int = 0, limit: int = 100) -> List[BatchMember]:
        result = await db.execute(select(BatchMember).filter(BatchMember.batch_id == batch_id).offset(skip).limit(limit))
        return result.scalars().all()
    
    async def get_by_user_and_course(self, db: AsyncSession, *, user_id, course_id: int) -> Optional[BatchMember]:
        """Check if user is enrolled in a course"""
        from app.models.batch import Batch
        result = await db.execute(
            select(BatchMember)
            .join(Batch)
            .filter(
                BatchMember.user_id == user_id,
                Batch.course_id == course_id,
                BatchMember.status == BatchMemberStatus.active
            )
        )
        return result.scalars().first()

batch = CRUDBatch()
batch_member = CRUDBatchMember()
