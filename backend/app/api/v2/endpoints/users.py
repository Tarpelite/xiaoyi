"""
用户管理端点 - Authing SDK v3版本
================================

使用Authing Python SDK v3实现用户资料和密码更新
基于实际SDK源码：/backend/.venv/lib/python3.12/site-packages/authing/AuthenticationClient.py
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from authing import AuthenticationClient

from app.core.auth import verify_token, User
from app.core.config import settings

router = APIRouter()


class UpdateProfileRequest(BaseModel):
    """更新用户资料请求"""

    nickname: Optional[str] = Field(None, max_length=50, description="昵称")
    bio: Optional[str] = Field(None, max_length=200, description="个人简介")


class UpdatePasswordRequest(BaseModel):
    """更新密码请求"""

    old_password: str = Field(..., min_length=1, description="旧密码")
    new_password: str = Field(..., min_length=8, description="新密码")


class UserProfileResponse(BaseModel):
    """用户资料响应"""

    id: str
    email: Optional[str] = None
    nickname: Optional[str] = None
    name: Optional[str] = None
    bio: Optional[str] = None
    picture: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class APIResponse(BaseModel):
    """API统一响应格式"""

    success: bool
    data: Optional[dict] = None
    message: Optional[str] = None
    error: Optional[str] = None


def extract_access_token_from_header(authorization: str) -> str:
    """从Authorization header提取access token"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )
    return authorization.replace("Bearer ", "")


def create_authing_client_for_user(access_token: str) -> AuthenticationClient:
    """
    为特定用户创建AuthenticationClient实例

    Args:
        access_token: 用户的access_token

    Returns:
        AuthenticationClient实例，已设置用户token
    """
    # 获取Authing域名（移除/oidc后缀）
    app_host = settings.AUTHING_ISSUER.replace("/oidc", "")

    client = AuthenticationClient(
        app_id=settings.AUTHING_APP_ID,
        app_host=app_host,
        access_token=access_token,  # v3 SDK通过access_token参数传递用户token
    )
    return client


@router.get("/users/me")
async def get_current_user(
    current_user: User = Depends(verify_token), authorization: str = Header(...)
) -> APIResponse:
    """
    获取当前登录用户的完整信息

    使用SDK v3方法：get_profile()
    """
    try:
        access_token = extract_access_token_from_header(authorization)
        client = create_authing_client_for_user(access_token)

        # v3 SDK方法：get_profile(with_custom_data=True)
        response = client.get_profile(with_custom_data=True)

        # 检查响应格式
        if isinstance(response, dict):
            user_data = response.get("data", response)
        else:
            user_data = response

        # 提取自定义数据中的bio
        custom_data = (
            user_data.get("customData", {}) if user_data.get("customData") else {}
        )
        bio = custom_data.get("bio") if isinstance(custom_data, dict) else None

        # 构建响应
        profile = UserProfileResponse(
            id=user_data.get("userId") or user_data.get("id") or current_user.sub,
            email=user_data.get("email"),
            nickname=user_data.get("nickname"),
            name=user_data.get("name") or user_data.get("nickname"),
            bio=bio,
            picture=user_data.get("photo") or user_data.get("picture"),
            created_at=user_data.get("createdAt"),
            updated_at=user_data.get("updatedAt", datetime.now().isoformat()),
        )

        print(f"[INFO] 成功获取用户信息: {profile.nickname} ({profile.id})")

        return APIResponse(success=True, data=profile.dict())
    except Exception as e:
        print(f"[ERROR] 获取用户信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取用户信息失败: {str(e)}",
        )


@router.patch("/users/me")
async def update_current_user(
    request: UpdateProfileRequest,
    current_user: User = Depends(verify_token),
    authorization: str = Header(...),
) -> APIResponse:
    """
    更新当前登录用户的资料

    使用SDK v3方法：update_profile(nickname=..., custom_data={...})
    """
    try:
        access_token = extract_access_token_from_header(authorization)
        client = create_authing_client_for_user(access_token)

        # 准备更新参数
        update_params = {}
        if request.nickname is not None:
            update_params["nickname"] = request.nickname

        # bio作为自定义数据
        custom_data = {}
        if request.bio is not None:
            custom_data["bio"] = request.bio

        if not update_params and not custom_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="没有提供要更新的字段"
            )

        print(
            f"[INFO] 用户 {current_user.sub} 更新资料: nickname={request.nickname}, bio={request.bio}"
        )

        # v3 SDK方法：update_profile(**params)
        if custom_data:
            update_params["custom_data"] = custom_data

        response = client.update_profile(**update_params)

        # 重新获取完整的用户信息以确认更新
        refreshed_response = client.get_profile(with_custom_data=True)

        # 解析响应
        if isinstance(refreshed_response, dict):
            user_data = refreshed_response.get("data", refreshed_response)
        else:
            user_data = refreshed_response

        # 提取自定义数据
        custom_data_result = (
            user_data.get("customData", {}) if user_data.get("customData") else {}
        )
        bio_result = (
            custom_data_result.get("bio")
            if isinstance(custom_data_result, dict)
            else None
        )

        # 使用提交的值作为最终值（以防SDK返回延迟）
        final_nickname = request.nickname or user_data.get("nickname")
        final_bio = request.bio if request.bio is not None else bio_result

        # 构建响应
        profile = UserProfileResponse(
            id=user_data.get("userId") or user_data.get("id") or current_user.sub,
            email=user_data.get("email") or current_user.email,
            nickname=final_nickname,
            name=final_nickname,
            bio=final_bio,
            picture=user_data.get("photo") or user_data.get("picture"),
            created_at=user_data.get("createdAt"),
            updated_at=datetime.now().isoformat(),
        )

        print(f"[INFO] 用户资料更新成功，昵称: {profile.nickname}")

        return APIResponse(success=True, data=profile.dict(), message="资料更新成功")

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] 更新用户资料失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新失败: {str(e)}",
        )


@router.put("/users/password")
async def update_password(
    request: UpdatePasswordRequest,
    current_user: User = Depends(verify_token),
    authorization: str = Header(...),
) -> APIResponse:
    """
    更新当前登录用户的密码

    使用SDK v3方法：update_password(new_password, old_password)
    """
    try:
        # 验证新密码强度
        if len(request.new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="密码长度至少8位"
            )

        if not any(c.isupper() for c in request.new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="密码必须包含大写字母"
            )

        if not any(c.islower() for c in request.new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="密码必须包含小写字母"
            )

        if not any(c.isdigit() for c in request.new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="密码必须包含数字"
            )

        access_token = extract_access_token_from_header(authorization)
        client = create_authing_client_for_user(access_token)

        print(f"[INFO] 用户 {current_user.sub} 请求更新密码")

        # v3 SDK方法：update_password(new_password, old_password)
        response = client.update_password(
            new_password=request.new_password, old_password=request.old_password
        )

        print("[INFO] 密码更新成功")

        return APIResponse(success=True, message="密码更新成功")

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e).lower()
        print(f"[ERROR] 更新密码失败: {e}")

        # 检查常见错误
        if (
            "旧密码" in str(e)
            or "old password" in error_msg
            or "incorrect" in error_msg
            or "wrong" in error_msg
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="旧密码不正确"
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"密码更新失败: {str(e)}",
        )
