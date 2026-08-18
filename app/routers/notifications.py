from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import get_db
from app.models import Notification
from app.schemas import NotificationOut
from app.security import current_user
router=APIRouter()
@router.get("",response_model=list[NotificationOut])
def list_notifications(db:Session=Depends(get_db),u=Depends(current_user)):
 return list(db.scalars(select(Notification).where(Notification.user_id==u.id).order_by(Notification.created_at.desc()).limit(100)).all())
@router.post("/{notification_id}/read")
def mark_read(notification_id:int,db:Session=Depends(get_db),u=Depends(current_user)):
 n=db.get(Notification,notification_id)
 if not n or n.user_id!=u.id:raise HTTPException(404,"Notification not found")
 n.is_read=True;db.commit();return {"message":"Marked as read"}
@router.post("/read-all")
def read_all(db:Session=Depends(get_db),u=Depends(current_user)):
 for n in db.scalars(select(Notification).where(Notification.user_id==u.id,n.is_read==False)):n.is_read=True
 db.commit();return {"message":"All notifications marked as read"}
