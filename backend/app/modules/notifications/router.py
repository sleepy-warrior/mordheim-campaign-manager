from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User
from app.modules.auth.dependencies import get_current_user

from .schemas import NotificationResponse
from .service import clear_notifications, list_notifications, mark_all_read, mark_notification_read

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
def get_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return list_notifications(db, user.id)


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def read_notification(notification_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    notification = mark_notification_read(db, user.id, notification_id)
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return notification


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def read_all_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    mark_all_read(db, user.id)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    clear_notifications(db, user.id)
