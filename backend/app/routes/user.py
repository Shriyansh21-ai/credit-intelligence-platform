from fastapi import APIRouter
from backend.app.models.schemas import UserData

router = APIRouter()

fake_db = {}

@router.post("/create")
async def create_user(user: UserData):
    user_id = str(len(fake_db) + 1)
    fake_db[user_id] = user.dict()

    return {"user_id": user_id, "message": "User created"}

# ADD THIS
def get_user(user_id: str):
    return fake_db.get(user_id)