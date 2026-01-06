from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_news():
    return {"message": "News endpoint placeholder"}
