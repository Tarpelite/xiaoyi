/**
 * UserPanel Component
 * 显示用户登录状态，包含紧凑型资料卡和下拉菜单
 */

'use client'

import { useState, useRef, useEffect } from 'react'
import { Settings, LogOut } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { SettingsModal } from '@/components/modals/SettingsModal'

export function UserPanel() {
    const { user, isAuthenticated, isLoading, login } = useAuth()
    const [showDropdown, setShowDropdown] = useState(false)
    const [showSettings, setShowSettings] = useState(false)
    const dropdownRef = useRef<HTMLDivElement>(null)

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setShowDropdown(false)
            }
        }

        if (showDropdown) {
            document.addEventListener('mousedown', handleClickOutside)
        }

        return () => {
            document.removeEventListener('mousedown', handleClickOutside)
        }
    }, [showDropdown])

    const handleLogout = async () => {
        // 清除 localStorage
        if (typeof window !== 'undefined') {
            localStorage.removeItem('authing_access_token')
        }

        // 重定向到登出端点（会清除 Cookies 和 Authing session）
        window.location.href = '/api/auth/logout'
    }

    const handleOpenSettings = () => {
        setShowDropdown(false)
        setShowSettings(true)
    }

    // 加载状态
    if (isLoading) {
        return (
            <div className="border-t border-white/5 p-4">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-dark-700 animate-pulse" />
                    <div className="flex-1">
                        <div className="h-4 bg-dark-700 rounded animate-pulse mb-2" />
                        <div className="h-3 bg-dark-700 rounded animate-pulse w-2/3" />
                    </div>
                </div>
            </div>
        )
    }

    // 已登录状态
    if (isAuthenticated && user) {
        return (
            <>
                <div className="border-t border-white/5 p-4" ref={dropdownRef}>
                    {/* 用户资料卡 */}
                    <button
                        onClick={() => setShowDropdown(!showDropdown)}
                        className="w-full flex items-center gap-3 p-2 hover:bg-white/5 rounded-lg transition-colors group"
                    >
                        {/* 用户头像 */}
                        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center text-white font-semibold flex-shrink-0">
                            {user.name?.[0]?.toUpperCase() || user.email?.[0]?.toUpperCase() || '?'}
                        </div>

                        {/* 用户信息 */}
                        <div className="flex-1 min-w-0 text-left">
                            <div className="text-sm font-medium text-gray-100 truncate">
                                {user.name || user.username || user.email || '用户'}
                            </div>
                            {user.email && (
                                <div className="text-xs text-gray-400 truncate">
                                    {user.email}
                                </div>
                            )}
                        </div>

                        {/* 设置图标 */}
                        <Settings className="w-4 h-4 text-gray-400 group-hover:text-gray-300 transition-colors flex-shrink-0" />
                    </button>

                    {/* 下拉菜单 */}
                    {showDropdown && (
                        <div className="mt-2 glass rounded-lg overflow-hidden shadow-xl">
                            <button
                                onClick={handleOpenSettings}
                                className="w-full px-4 py-2.5 text-sm text-left text-gray-300 hover:bg-white/10 transition-colors flex items-center gap-3"
                            >
                                <Settings className="w-4 h-4" />
                                修改资料
                            </button>
                            <div className="border-t border-white/10" />
                            <button
                                onClick={handleLogout}
                                className="w-full px-4 py-2.5 text-sm text-left text-red-400 hover:bg-red-500/10 transition-colors flex items-center gap-3"
                            >
                                <LogOut className="w-4 h-4" />
                                退出登录
                            </button>
                        </div>
                    )}
                </div>

                {/* Settings Modal */}
                <SettingsModal
                    isOpen={showSettings}
                    onClose={() => setShowSettings(false)}
                />
            </>
        )
    }

    // 未登录状态
    return (
        <div className="border-t border-white/5 p-4">
            <button
                onClick={login}
                className="w-full px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 rounded-lg transition-all flex items-center justify-center gap-2"
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
            <p className="text-xs text-center text-gray-400 mt-2">
                登录后保存对话记录
            </p>
        </div>
    )
}
