from app.database import SessionLocal
from app.models import User
from app.config import settings
from app.security import hash_password
db=SessionLocal()
try:
 u=db.query(User).filter(User.email==settings.ADMIN_EMAIL).first()
 if not u:
  db.add(User(email=settings.ADMIN_EMAIL,display_name="Admin",password_hash=hash_password(settings.ADMIN_PASSWORD),role="ADMIN"));db.commit();print("Admin created.")
 else: print("Admin already exists.")
finally: db.close()
