from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import get_db
from app.models import Category,Tag
from app.schemas import CategoryIn
from app.security import admin_user
router=APIRouter()
@router.get("/categories")
def categories(db:Session=Depends(get_db)): return list(db.scalars(select(Category).order_by(Category.name)).all())
@router.get("/tags")
def tags(db:Session=Depends(get_db)): return list(db.scalars(select(Tag).order_by(Tag.name)).all())
@router.post("/categories")
def add_category(d:CategoryIn,db:Session=Depends(get_db),u=Depends(admin_user)):
 c=Category(**d.model_dump()); db.add(c); db.commit(); db.refresh(c); return c
@router.post("/tags")
def add_tag(d:CategoryIn,db:Session=Depends(get_db),u=Depends(admin_user)):
 t=Tag(**d.model_dump()); db.add(t); db.commit(); db.refresh(t); return t
