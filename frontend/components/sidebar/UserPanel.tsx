/**
 * UserPanel Component
 * 显示用户登录状态和登录/登出按钮
 */

'use client'

import { useAuth } from '@/context/AuthContext'

export function UserPanel() {
    const { user, isAuthenticated, isLoading, login } = useAuth()

    const handleLogout = async () => {
        // 清除 localStorage
        if (typeof window !== 'undefined') {
            localStorage.removeItem('authing_access_token')
        }

        // 重定向到登出端点（会清除 Cookies 和 Authing session）
        window.location.href = '/api/auth/logout'
    }

    // 加载状态
    if (isLoading) {
        return (
            <div className="border-t border-gray-200 dark:border-gray-700 p-4">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-gray-200 dark:bg-gray-700 animate-pulse" />
                    <div className="flex-1">
                        <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded animate-pulse mb-2" />
                        <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded animate-pulse w-2/3" />
                    </div>
                </div>
            </div>
        )
    }

    // 已登录状态
    if (isAuthenticated && user) {
        return (
            <div className="border-t border-gray-200 dark:border-gray-700 p-4">
                <div className="flex items-center gap-3 mb-3">
                    {/* 用户头像 */}
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white font-semibold">
                        {user.name?.[0]?.toUpperCase() || user.email?.[0]?.toUpperCase() || '?'}
                    </div>

                    {/* 用户信息 */}
                    <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                            {user.name || user.email || '用户'}
                        </div>
                        {user.email && (
                            <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                                {user.email}
                            </div>
                        )}
                    </div>
                </div>

                {/* 登出按钮 */}
                <button
                    onClick={handleLogout}
                    className="w-full px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors flex items-center justify-center gap-2"
                >
                    <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                    >
                        <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                        />
                    </svg>
                    退出登录
                </button>
            </div>
        )
    }

    // 未登录状态
    return (
        <div className="border-t border-gray-200 dark:border-gray-700 p-4">
            <button
                onClick={login}
                className="w-full px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 rounded-lg transition-all flex items-center justify-center gap-2"
            >
                <svg
                    className="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                >
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1"
                    />
                </svg>
                登录
            </button>
            <p className="text-xs text-center text-gray-500 dark:text-gray-400 mt-2">
                登录后保存对话记录
            </p>
        </div>
    )
}
