from app.db.database import engine
from app.models import user, risk_history

def init_db():
    user.Base.metadata.create_all(bind=engine)