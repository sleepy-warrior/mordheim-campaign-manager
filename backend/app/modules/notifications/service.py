from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models import Notification


def create_notification(
    db: Session,
    *,
    recipient_id: UUID,
    notification_type: str,
    title: str,
    message: str,
    campaign_id: UUID | None = None,
    actor_id: UUID | None = None,
    metadata: dict[str, object] | None = None,
) -> Notification:
    notification = Notification(
        recipient_id=recipient_id,
        notification_type=notification_type,
        title=title,
        message=message,
        campaign_id=campaign_id,
        actor_id=actor_id,
        notification_metadata=metadata or {},
    )
    db.add(notification)
    return notification


def list_notifications(db: Session, user_id: UUID) -> list[Notification]:
    return list(db.scalars(select(Notification).where(Notification.recipient_id == user_id).order_by(Notification.created_at.desc())).all())


def mark_notification_read(db: Session, user_id: UUID, notification_id: UUID) -> Notification | None:
    notification = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.recipient_id == user_id))
    if notification is None:
        return None
    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc)
    db.commit()
    return notification


def mark_all_read(db: Session, user_id: UUID) -> None:
    db.execute(update(Notification).where(Notification.recipient_id == user_id, Notification.is_read.is_(False)).values(is_read=True, read_at=datetime.now(timezone.utc)))
    db.commit()


def clear_notifications(db: Session, user_id: UUID) -> None:
    db.execute(delete(Notification).where(Notification.recipient_id == user_id))
    db.commit()
