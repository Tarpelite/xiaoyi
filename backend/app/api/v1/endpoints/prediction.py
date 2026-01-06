from fastapi import APIRouter

router = APIRouter()

@router.post("/")
async def predict():
    return {"message": "Prediction endpoint placeholder"}
