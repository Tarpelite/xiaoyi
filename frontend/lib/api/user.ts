/**
 * User API Client
 * 用户资料和密码管理相关API
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/**
 * 获取访问令牌
 */
function getAccessToken(): string | null {
    if (typeof window === 'undefined') return null
    return localStorage.getItem('authing_access_token')
}

/**
 * 用户资料更新参数
 */
export interface UpdateUserProfileParams {
    nickname?: string
    bio?: string
}

/**
 * 用户资料响应
 */
export interface UserProfile {
    id: string
    email: string
    nickname?: string
    bio?: string
    picture?: string
    created_at: string
    updated_at: string
}

/**
 * 密码更新参数
 */
export interface UpdatePasswordParams {
    oldPassword: string
    newPassword: string
}

/**
 * API响应类型
 */
interface ApiResponse<T = any> {
    success: boolean
    data?: T
    message?: string
    error?: string
}

/**
 * 更新用户基本资料
 * @param params 更新参数（昵称、简介等）
 * @returns 更新后的用户资料
 */
export async function updateUserProfile(params: UpdateUserProfileParams): Promise<UserProfile> {
    const token = getAccessToken()
    if (!token) {
        throw new Error('未登录，请先登录')
    }

    const response = await fetch(`${API_BASE_URL}/api/users/me`, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(params),
    })

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.message || errorData.error || `更新失败: ${response.status}`)
    }

    const result: ApiResponse<UserProfile> = await response.json()

    if (!result.success || !result.data) {
        throw new Error(result.message || result.error || '更新失败')
    }

    return result.data
}

/**
 * 更新用户密码
 * @param params 旧密码和新密码
 * @returns 成功状态
 */
export async function updateUserPassword(params: UpdatePasswordParams): Promise<void> {
    const token = getAccessToken()
    if (!token) {
        throw new Error('未登录，请先登录')
    }

    const response = await fetch(`${API_BASE_URL}/api/users/password`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
            old_password: params.oldPassword,
            new_password: params.newPassword,
        }),
    })

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.message || errorData.error || `密码更新失败: ${response.status}`)
    }

    const result: ApiResponse = await response.json()

    if (!result.success) {
        throw new Error(result.message || result.error || '密码更新失败')
    }
}

/**
 * 验证密码强度
 * @param password 密码
 * @returns 验证结果和错误消息
 */
export function validatePassword(password: string): { valid: boolean; error?: string } {
    if (password.length < 8) {
        return { valid: false, error: '密码长度至少8位' }
    }

    if (!/[A-Z]/.test(password)) {
        return { valid: false, error: '密码必须包含大写字母' }
    }

    if (!/[a-z]/.test(password)) {
        return { valid: false, error: '密码必须包含小写字母' }
    }

    if (!/[0-9]/.test(password)) {
        return { valid: false, error: '密码必须包含数字' }
    }

    return { valid: true }
}
