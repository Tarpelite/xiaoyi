/**
 * 用户资料补全模态框
 * 
 * 在新用户注册后自动弹出，要求用户设置昵称
 */

'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { User, AlertCircle, CheckCircle2 } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { updateUserProfile } from '@/lib/api/user'

interface ProfileCompletionModalProps {
    isOpen: boolean
    onClose: () => void
}

export function ProfileCompletionModal({ isOpen, onClose }: ProfileCompletionModalProps) {
    const { user, updateUser } = useAuth()
    const [nickname, setNickname] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [success, setSuccess] = useState(false)

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()

        if (!nickname.trim()) {
            setError('请输入昵称')
            return
        }

        if (nickname.trim().length < 2) {
            setError('昵称至少需要2个字符')
            return
        }

        setIsLoading(true)
        setError(null)

        try {
            const result = await updateUserProfile({ nickname: nickname.trim() })

            // 更新本地用户状态
            updateUser({ name: nickname.trim() })

            setSuccess(true)

            // 1.5秒后自动关闭
            setTimeout(() => {
                onClose()
            }, 1500)
        } catch (err: any) {
            console.error('更新昵称失败:', err)
            setError(err.message || '更新失败，请重试')
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <AnimatePresence>
            {isOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center">
                    {/* 背景遮罩 - 不可点击关闭 */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
                    />

                    {/* 模态框内容 */}
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: 20 }}
                        className="relative bg-dark-800 rounded-xl p-8 w-full max-w-md border border-white/10 shadow-2xl"
                    >
                        {/* 顶部图标和标题 */}
                        <div className="flex flex-col items-center mb-6">
                            <div className="p-4 bg-gradient-to-br from-violet-500/20 to-purple-500/20 rounded-2xl mb-4">
                                <User className="w-8 h-8 text-violet-400" />
                            </div>
                            <h2 className="text-2xl font-bold text-center mb-2">
                                欢迎加入！
                            </h2>
                            <p className="text-gray-400 text-sm text-center">
                                请设置您的显示昵称，让其他人更好地认识您
                            </p>
                        </div>

                        {/* 表单 */}
                        <form onSubmit={handleSubmit} className="space-y-5">
                            <div>
                                <label className="block text-sm font-medium mb-2 text-gray-300">
                                    昵称 <span className="text-red-400">*</span>
                                </label>
                                <input
                                    type="text"
                                    value={nickname}
                                    onChange={(e) => {
                                        setNickname(e.target.value)
                                        setError(null)
                                    }}
                                    className="w-full px-4 py-3 bg-dark-700 border border-white/10 rounded-lg 
                           focus:outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20
                           transition-all text-gray-200 placeholder-gray-500"
                                    placeholder="输入您的昵称"
                                    maxLength={50}
                                    autoFocus
                                    disabled={isLoading || success}
                                />
                                <p className="mt-1.5 text-xs text-gray-500">
                                    {nickname.length}/50
                                </p>
                            </div>

                            {/* 错误提示 */}
                            {error && (
                                <motion.div
                                    initial={{ opacity: 0, y: -10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    className="flex items-start gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg"
                                >
                                    <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                                    <p className="text-red-400 text-sm">{error}</p>
                                </motion.div>
                            )}

                            {/* 成功提示 */}
                            {success && (
                                <motion.div
                                    initial={{ opacity: 0, scale: 0.95 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    className="flex items-center gap-2 p-3 bg-green-500/10 border border-green-500/20 rounded-lg"
                                >
                                    <CheckCircle2 className="w-5 h-5 text-green-400" />
                                    <p className="text-green-400 text-sm font-medium">设置成功！正在跳转...</p>
                                </motion.div>
                            )}

                            {/* 提交按钮 */}
                            <button
                                type="submit"
                                disabled={isLoading || !nickname.trim() || success}
                                className="w-full py-3.5 bg-gradient-to-r from-violet-600 to-purple-600 
                         hover:from-violet-700 hover:to-purple-700 
                         disabled:opacity-50 disabled:cursor-not-allowed 
                         rounded-lg font-medium transition-all shadow-lg
                         hover:shadow-violet-500/25 active:scale-[0.98]"
                            >
                                {isLoading ? (
                                    <span className="flex items-center justify-center gap-2">
                                        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                        </svg>
                                        保存中...
                                    </span>
                                ) : success ? (
                                    '✓ 完成'
                                ) : (
                                    '开始使用'
                                )}
                            </button>
                        </form>

                        {/* 底部提示 */}
                        <p className="mt-6 text-center text-xs text-gray-500">
                            您稍后也可以在设置中修改昵称
                        </p>
                    </motion.div>
                </div>
            )}
        </AnimatePresence>
    )
}
