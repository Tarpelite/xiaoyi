from fastapi import APIRouter

router = APIRouter()

@router.post("/")
async def upload_file():
    return {"message": "Upload endpoint placeholder"}
