from datetime import datetime
from typing import Optional
from pydantic import BaseModel,ConfigDict,EmailStr,Field
class Token(BaseModel): access_token:str; token_type:str="bearer"
class RegisterIn(BaseModel): email:EmailStr; display_name:str=Field(min_length=2,max_length=80); password:str=Field(min_length=8,max_length=128)
class LoginIn(BaseModel): email:EmailStr; password:str
class UserOut(BaseModel):
 model_config=ConfigDict(from_attributes=True)
 id:int; email:EmailStr; display_name:str; role:str; is_active:bool
class WritingIn(BaseModel):
 title:str=Field(min_length=1,max_length=220); content:str=Field(min_length=1); excerpt:Optional[str]=None; cover_image_url:Optional[str]=None
 category_id:Optional[int]=None; tag_ids:list[int]=[]; status:str="DRAFT"; featured:bool=False
class WritingOut(WritingIn):
 model_config=ConfigDict(from_attributes=True)
 id:int; slug:str; view_count:int; author_id:int; created_at:datetime; updated_at:datetime; published_at:Optional[datetime]
class CommentIn(BaseModel): content:str=Field(min_length=1,max_length=5000); parent_id:Optional[int]=None
class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    status: str
    author_id: int
    author_name: str
    writing_id: int
    parent_id: Optional[int]
    created_at: datetime
    updated_at: datetime

class CategoryIn(BaseModel): name:str=Field(min_length=1,max_length=80); slug:str=Field(min_length=1,max_length=100)
class ReportIn(BaseModel): reason:str=Field(min_length=3,max_length=500)
class StatusIn(BaseModel): status:str
class NotificationOut(BaseModel):
 model_config=ConfigDict(from_attributes=True)
 id:int; type:str; message:str; is_read:bool; created_at:datetime; writing_id:Optional[int]; comment_id:Optional[int]
