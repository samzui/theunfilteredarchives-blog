from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy.orm import Session
from sqlalchemy import select,or_,func
from app.database import get_db
from app.models import Writing,Tag,WritingLike
from app.schemas import WritingIn,WritingOut
from app.security import current_user,admin_user
from app.services.utils import slugify
router=APIRouter()
def unique_slug(title,db,exclude=None):
 base=slugify(title) or "writing"; slug=base; n=2
 while db.scalar(select(Writing).where(Writing.slug==slug,Writing.id!=exclude if exclude else True)): slug=f"{base}-{n}"; n+=1
 return slug
@router.get("",response_model=list[WritingOut])
def list_public(db:Session=Depends(get_db),q:str|None=None,category_id:int|None=None,featured:bool|None=None,page:int=Query(1,ge=1),limit:int=Query(12,ge=1,le=50)):
 s=select(Writing).where(Writing.status=="PUBLISHED")
 if q: s=s.where(or_(Writing.title.ilike(f"%{q}%"),Writing.content.ilike(f"%{q}%"),Writing.excerpt.ilike(f"%{q}%")))
 if category_id is not None:s=s.where(Writing.category_id==category_id)
 if featured is not None:s=s.where(Writing.featured==featured)
 return list(db.scalars(s.order_by(Writing.published_at.desc().nullslast()).offset((page-1)*limit).limit(limit)).all())
@router.get("/admin/all",response_model=list[WritingOut])
def admin_all(db:Session=Depends(get_db),u=Depends(admin_user)): return list(db.scalars(select(Writing).order_by(Writing.updated_at.desc())).all())
@router.get("/{writing_id}",response_model=WritingOut)
def get_one(writing_id:int,db:Session=Depends(get_db)):
 w=db.get(Writing,writing_id)
 if not w or w.status!="PUBLISHED": raise HTTPException(404,"Writing not found")
 w.view_count+=1; db.commit(); db.refresh(w); return w
@router.post("",response_model=WritingOut)
def create(d:WritingIn,db:Session=Depends(get_db),u=Depends(admin_user)):
 w=Writing(**{k:v for k,v in d.model_dump().items() if k!="tag_ids"},slug=unique_slug(d.title,db),author_id=u.id)
 if d.tag_ids: w.tags=list(db.scalars(select(Tag).where(Tag.id.in_(d.tag_ids))).all())
 if d.status=="PUBLISHED": w.published_at=datetime.now(timezone.utc)
 db.add(w); db.commit(); db.refresh(w); return w
@router.put("/{writing_id}",response_model=WritingOut)
def update(writing_id:int,d:WritingIn,db:Session=Depends(get_db),u=Depends(admin_user)):
 w=db.get(Writing,writing_id)
 if not w: raise HTTPException(404,"Writing not found")
 for k,v in d.model_dump().items():
  if k!="tag_ids": setattr(w,k,v)
 w.tags=list(db.scalars(select(Tag).where(Tag.id.in_(d.tag_ids))).all()) if d.tag_ids else []
 if d.status=="PUBLISHED" and not w.published_at:w.published_at=datetime.now(timezone.utc)
 db.commit(); db.refresh(w); return w
@router.delete("/{writing_id}")
def delete(writing_id:int,db:Session=Depends(get_db),u=Depends(admin_user)):
 w=db.get(Writing,writing_id)
 if not w: raise HTTPException(404,"Writing not found")
 db.delete(w); db.commit(); return {"message":"Writing deleted"}
@router.get("/{writing_id}/like-count")
def like_count(writing_id:int,db:Session=Depends(get_db)):
 return {"likes":db.scalar(select(func.count()).select_from(WritingLike).where(WritingLike.writing_id==writing_id))}
