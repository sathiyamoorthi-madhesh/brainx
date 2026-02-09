from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.crud.crud_batch import batch as crud_batch, batch_member as crud_batch_member
from app.crud.crud_course import course as crud_course # To check course existence
from app.crud.crud_user import user as crud_user
from app.models.user import User, UserRole
from app.schemas.batch import Batch, BatchCreate, BatchUpdate, BatchMember, BatchMemberCreate, BatchDetail, BatchMemberDetail
from app.schemas.chat import ChatCreate, ChatMemberCreate, MessageCreate
from app.models.chat import ChatTypeEnum, ChatMemberRoleEnum
from app.crud.crud_chat import chat as crud_chat, message as crud_message
from app.services.bunny_service import bunny_service

router = APIRouter()

# --- Batch Endpoints ---

@router.get("/", response_model=List[Batch])
async def read_batches(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve batches based on user role.
    """
    print(f"DEBUG: current_user: {current_user.email}, role: {current_user.role}, type: {type(current_user.role)}")
    if current_user.role == UserRole.admin:
        print("DEBUG: Role is admin")
        batches = await crud_batch.get_multi(db, skip=skip, limit=limit)
    elif current_user.role == UserRole.teacher:
        print("DEBUG: Role is teacher")
        batches = await crud_batch.get_by_teacher(db, teacher_id=current_user.id, skip=skip, limit=limit)
    elif current_user.role == UserRole.student:
        print("DEBUG: Role is student")
        batches = await crud_batch.get_by_student(db, user_id=current_user.id, skip=skip, limit=limit)
    else:
        print("DEBUG: Role is other")
        batches = []
        
    return batches

@router.post("/", response_model=Batch)
async def create_batch(
    *,
    db: AsyncSession = Depends(deps.get_db),
    batch_in: BatchCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Create new batch.
    """
    # Check if course exists
    course = await crud_course.get(db, id=batch_in.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
        
    batch = await crud_batch.create(db=db, obj_in=batch_in)

    # Automatic Chat Creation
    try:
        # Map batch members to chat members
        # Map batch members to chat members
        initial_chat_members = []
        
        # Add Teacher if assigned
        if batch_in.teacher_id:
            teacher = await crud_user.get(db, id=batch_in.teacher_id)
            if teacher:
                initial_chat_members.append(
                    ChatMemberCreate(
                        user_id=teacher.id,
                        role=ChatMemberRoleEnum.teacher,
                        role_id=None
                    )
                )

        if batch_in.members:
            for bm in batch_in.members:
                # Default role to student if not specified, or map appropriately
                # For now assuming 'student' role for batch members in chat
                initial_chat_members.append(
                    ChatMemberCreate(
                        user_id=bm.user_id,
                        role=ChatMemberRoleEnum.student,
                        role_id=bm.role_id
                    )
                )

        chat_in = ChatCreate(
            chat_type=ChatTypeEnum.group,
            batch_id=batch.id,
            is_official=True,
            initial_members=initial_chat_members
        )
        chat = await crud_chat.create(db=db, obj_in=chat_in, created_by=current_user.id)

        # Welcome Message
        msg_in = MessageCreate(
            chat_id=chat.id,
            batch_id=batch.id,
            message="HI this is chat our group",
            is_system_message=True
        )
        await crud_message.create(db=db, obj_in=msg_in, sender_id=current_user.id)
    except Exception as e:
        print(f"Failed to create auto-chat for batch {batch.id}: {e}")
        raise e # Debugging: Raise to see error in response

    return batch

@router.get("/{batch_id}", response_model=BatchDetail)
async def read_batch(
    *,
    db: AsyncSession = Depends(deps.get_db),
    batch_id: int,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get batch by ID.
    """
    batch = await crud_batch.get_with_members(db=db, id=batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
        
    # Manual mapping to schema
    members_details = [
        BatchMemberDetail(
            user_id=m.user_id,
            user_name=m.user.full_name if m.user else "Unknown",
            user_email=m.user.email if m.user else "Unknown",
            role_id=m.role_id
        )
        for m in batch.members
    ]
    
    batch_detail = BatchDetail(
        id=batch.id,
        course_id=batch.course_id,
        batch_name=batch.batch_name,
        teacher_id=batch.teacher_id,
        start_date=batch.start_date,
        end_date=batch.end_date,
        total_hours=batch.total_hours,
        consumed_hours=batch.consumed_hours,
        remaining_hours=batch.remaining_hours,
        schedule_time=batch.schedule_time,
        status=batch.status,
        created_at=batch.created_at,
        teacher_name=batch.teacher.full_name if batch.teacher else None,
        course_name=batch.course.title if batch.course else None,
        members=members_details
    )
    return batch_detail

@router.put("/{batch_id}", response_model=Batch)
async def update_batch(
    *,
    db: AsyncSession = Depends(deps.get_db),
    batch_id: int,
    batch_in: BatchUpdate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Update a batch.
    """
    batch = await crud_batch.get(db=db, id=batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    batch = await crud_batch.update(db, db_obj=batch, obj_in=batch_in)
    return batch

@router.delete("/{batch_id}", response_model=Batch)
async def delete_batch(
    *,
    db: AsyncSession = Depends(deps.get_db),
    batch_id: int,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Delete a batch.
    """
    batch = await crud_batch.get(db=db, id=batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    batch = await crud_batch.remove(db, id=batch_id)
    return batch


# --- Batch Member Endpoints ---

@router.post("/{batch_id}/members/", response_model=BatchMember)
async def add_batch_member(
    *,
    db: AsyncSession = Depends(deps.get_db),
    batch_id: int,
    member_in: BatchMemberCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Add a member to a batch.
    """
    batch = await crud_batch.get(db=db, id=batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
        
    # Ensure member_in.batch_id matches URL batch_id (or just override it)
    member_in.batch_id = batch_id
    
    # Check if already exists? (Omitted for brevity, but should be here)
    
    member = await crud_batch_member.create(db=db, obj_in=member_in)
    return member

@router.get("/{batch_id}/members/", response_model=List[BatchMember])
async def read_batch_members(
    *,
    db: AsyncSession = Depends(deps.get_db),
    batch_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get members of a batch.
    """
    batch = await crud_batch.get(db=db, id=batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
        
    members = await crud_batch_member.get_by_batch(db, batch_id=batch_id, skip=skip, limit=limit)
    return members

@router.get("/{batch_id}/resources", response_model=List[Any])
async def read_batch_resources(
    *,
    db: AsyncSession = Depends(deps.get_db),
    batch_id: int,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get resources for a batch (from its group chat).
    """
    batch = await crud_batch.get(db=db, id=batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    # Resolve Chat Group ID from Batch ID
    chat = await crud_chat.get_by_batch(db, batch_id=batch_id)
    
    if not chat:
        # If no chat exists yet (e.g. auto-creation failed), returns empty list instead of 404 for resources
        return []
        
    # Fetch resources from Bunny.net
    # Path: resources/groups/{chat_id}/
    path = f"resources/groups/{chat.id}"
    files = await bunny_service.list_files(path)
    
    return files
