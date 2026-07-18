from fastapi import APIRouter

from backend.app.routes.user import get_user
from backend.app.services.credit_analyst_report import build_credit_analyst_report

router = APIRouter()

@router.get("/report/{user_id}")

async def get_report(user_id: str):

    # Get user
    user = get_user(user_id)

    if not user:

        return {
            "success": False,
            "error": "User not found"
        }

    # ----------------------------------------
    # Convert User Data To ML Input Format
    # ----------------------------------------

    prediction_data = {

        "Age": user.get("age", 35),

        "Sex": user.get("sex", "male"),

        "Job": user.get("job", 2),

        "Housing": user.get("housing", "own"),

        "Saving accounts": user.get(
            "saving_accounts",
            "moderate"
        ),

        "Checking account": user.get(
            "checking_account",
            "little"
        ),

        "Credit amount": user.get(
            "credit_amount",
            4000
        ),

        "Duration": user.get(
            "duration",
            24
        ),

        "Purpose": user.get(
            "purpose",
            "car"
        )
    }

    report = build_credit_analyst_report(prediction_data, report_type="personal")

    return {
        "success": True,
        "user_id": user_id,
        "user_profile": user,
        "analysis": report
    }