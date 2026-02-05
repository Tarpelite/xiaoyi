/**
 * Settings Modal Component
 * 用户设置模态框 - 支持修改资料和密码
 */

'use client'

import { useState, useEffect } from 'react'
import { X, User, Lock, Loader2 } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '@/context/AuthContext'
import { updateUserProfile, updateUserPassword, validatePassword } from '@/lib/api/user'
import type { UpdateUserProfileParams, UpdatePasswordParams } from '@/lib/api/user'

interface SettingsModalProps {
    isOpen: boolean
    onClose: () => void
}

type TabType = 'profile' | 'password'

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
    const { user, updateUser } = useAuth()
    const [activeTab, setActiveTab] = useState<TabType>('profile')

    // Profile tab state
    const [nickname, setNickname] = useState('')
    const [bio, setBio] = useState('')

    // Password tab state
    const [oldPassword, setOldPassword] = useState('')
    const [newPassword, setNewPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')

    // UI state
    const [isLoading, setIsLoading] = useState(false)
    const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

    // Initialize form with user data
    useEffect(() => {
        if (user) {
            setNickname(user.name || user.username || '')
            setBio(user.bio || '')
        }
    }, [user])

    // Clear message after 3 seconds
    useEffect(() => {
        if (message) {
            const timer = setTimeout(() => setMessage(null), 3000)
            return () => clearTimeout(timer)
        }
    }, [message])

    // Reset form when modal closes
    useEffect(() => {
        if (!isOpen) {
            setActiveTab('profile')
            setOldPassword('')
            setNewPassword('')
            setConfirmPassword('')
            setMessage(null)
        }
    }, [isOpen])

    const handleUpdateProfile = async (e: React.FormEvent) => {
        e.preventDefault()
        setIsLoading(true)
        setMessage(null)

        try {
            const params: UpdateUserProfileParams = {
                nickname: nickname.trim() || undefined,
                bio: bio.trim() || undefined,
            }

            const updatedUser = await updateUserProfile(params)

            // Update local auth context - ensure nickname is mapped to name
            if (updateUser) {
                updateUser({
                    ...updatedUser,
                    name: updatedUser.nickname || updatedUser.name, // 确保name字段被更新
                })
            }

            setMessage({ type: 'success', text: '资料更新成功！' })
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : '更新失败，请稍后重试'
            setMessage({ type: 'error', text: errorMessage })
        } finally {
            setIsLoading(false)
        }
    }

    const handleUpdatePassword = async (e: React.FormEvent) => {
        e.preventDefault()
        setIsLoading(true)
        setMessage(null)

        // Validate passwords
        if (newPassword !== confirmPassword) {
            setMessage({ type: 'error', text: '两次输入的密码不一致' })
            setIsLoading(false)
            return
        }

        const validation = validatePassword(newPassword)
        if (!validation.valid) {
            setMessage({ type: 'error', text: validation.error || '密码不符合要求' })
            setIsLoading(false)
            return
        }

        try {
            const params: UpdatePasswordParams = {
                oldPassword,
                newPassword,
            }

            await updateUserPassword(params)

            setMessage({ type: 'success', text: '密码更新成功！' })

            // Clear password fields
            setOldPassword('')
            setNewPassword('')
            setConfirmPassword('')
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : '密码更新失败，请检查旧密码是否正确'
            setMessage({ type: 'error', text: errorMessage })
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <AnimatePresence>
            {isOpen && (
                <>
                    {/* Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={onClose}
                        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
                    />

                    {/* Modal */}
                    <div className="fixed inset-0 flex items-center justify-center z-50 p-4">
                        <motion.div
                            initial={{ opacity: 0, scale: 0.95, y: 20 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.95, y: 20 }}
                            className="glass w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden"
                            onClick={(e) => e.stopPropagation()}
                        >
                            {/* Header */}
                            <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
                                <h2 className="text-xl font-semibold text-white">设置</h2>
                                <button
                                    onClick={onClose}
                                    className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                                >
                                    <X className="w-5 h-5 text-gray-400" />
                                </button>
                            </div>

                            {/* Tabs */}
                            <div className="flex border-b border-white/10">
                                <button
                                    onClick={() => setActiveTab('profile')}
                                    className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium transition-colors ${activeTab === 'profile'
                                        ? 'text-violet-400 border-b-2 border-violet-500'
                                        : 'text-gray-400 hover:text-gray-300'
                                        }`}
                                >
                                    <User className="w-4 h-4" />
                                    基本信息
                                </button>
                                <button
                                    onClick={() => setActiveTab('password')}
                                    className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium transition-colors ${activeTab === 'password'
                                        ? 'text-violet-400 border-b-2 border-violet-500'
                                        : 'text-gray-400 hover:text-gray-300'
                                        }`}
                                >
                                    <Lock className="w-4 h-4" />
                                    密码管理
                                </button>
                            </div>

                            {/* Content */}
                            <div className="p-6">
                                {/* Message */}
                                {message && (
                                    <motion.div
                                        initial={{ opacity: 0, y: -10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        className={`mb-4 p-3 rounded-lg text-sm ${message.type === 'success'
                                            ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                                            : 'bg-red-500/20 text-red-400 border border-red-500/30'
                                            }`}
                                    >
                                        {message.text}
                                    </motion.div>
                                )}

                                {/* Profile Form */}
                                {activeTab === 'profile' && (
                                    <form onSubmit={handleUpdateProfile} className="space-y-4">
                                        <div>
                                            <label className="block text-sm font-medium text-gray-300 mb-2">
                                                昵称
                                            </label>
                                            <input
                                                type="text"
                                                value={nickname}
                                                onChange={(e) => setNickname(e.target.value)}
                                                placeholder="请输入昵称"
                                                maxLength={50}
                                                className="w-full px-4 py-2 bg-dark-700 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500 transition-all"
                                            />
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-300 mb-2">
                                                个人简介
                                            </label>
                                            <textarea
                                                value={bio}
                                                onChange={(e) => setBio(e.target.value)}
                                                placeholder="介绍一下自己..."
                                                maxLength={200}
                                                rows={4}
                                                className="w-full px-4 py-2 bg-dark-700 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500 transition-all resize-none"
                                            />
                                            <p className="text-xs text-gray-500 mt-1">
                                                {bio.length} / 200
                                            </p>
                                        </div>

                                        <button
                                            type="submit"
                                            disabled={isLoading}
                                            className="w-full px-4 py-2 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 disabled:from-violet-600/50 disabled:to-purple-600/50 rounded-lg font-medium text-white transition-all flex items-center justify-center gap-2"
                                        >
                                            {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
                                            {isLoading ? '保存中...' : '保存修改'}
                                        </button>
                                    </form>
                                )}

                                {/* Password Form */}
                                {activeTab === 'password' && (
                                    <form onSubmit={handleUpdatePassword} className="space-y-4">
                                        <div>
                                            <label className="block text-sm font-medium text-gray-300 mb-2">
                                                当前密码
                                            </label>
                                            <input
                                                type="password"
                                                value={oldPassword}
                                                onChange={(e) => setOldPassword(e.target.value)}
                                                placeholder="请输入当前密码"
                                                required
                                                className="w-full px-4 py-2 bg-dark-700 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500 transition-all"
                                            />
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-300 mb-2">
                                                新密码
                                            </label>
                                            <input
                                                type="password"
                                                value={newPassword}
                                                onChange={(e) => setNewPassword(e.target.value)}
                                                placeholder="至少8位，包含大小写字母和数字"
                                                required
                                                className="w-full px-4 py-2 bg-dark-700 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500 transition-all"
                                            />
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-300 mb-2">
                                                确认新密码
                                            </label>
                                            <input
                                                type="password"
                                                value={confirmPassword}
                                                onChange={(e) => setConfirmPassword(e.target.value)}
                                                placeholder="再次输入新密码"
                                                required
                                                className="w-full px-4 py-2 bg-dark-700 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500 transition-all"
                                            />
                                        </div>

                                        <button
                                            type="submit"
                                            disabled={isLoading}
                                            className="w-full px-4 py-2 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 disabled:from-violet-600/50 disabled:to-purple-600/50 rounded-lg font-medium text-white transition-all flex items-center justify-center gap-2"
                                        >
                                            {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
                                            {isLoading ? '更新中...' : '更新密码'}
                                        </button>
                                    </form>
                                )}
                            </div>
                        </motion.div>
                    </div>
                </>
            )}
        </AnimatePresence>
    )
}
