'use client';

import React from 'react';
import { StockWidget } from '@/components/stock/StockWidget';

export default function StockWidgetTestPage() {
    return (
        <div className="min-h-screen gradient-mesh p-8">
            <div className="max-w-5xl mx-auto space-y-6">
                {/* 页面标题 */}
                <div className="text-center mb-8">
                    <h1 className="text-3xl font-bold text-gray-100 mb-2">股票组件测试页面</h1>
                    <p className="text-gray-400 text-sm">StockWidget - 聊天消息集成演示</p>
                </div>

                {/* 模拟聊天消息气泡 */}
                <div className="glass rounded-lg p-6">
                    <div className="mb-3">
                        <div className="text-sm text-gray-400 mb-1">用户</div>
                        <div className="bg-violet-600 text-white px-4 py-2 rounded-lg inline-block max-w-md">
                            帮我分析一下贵州茅台的股价走势
                        </div>
                    </div>

                    <div className="mt-6">
                        <div className="text-sm text-gray-400 mb-3">AI 回复</div>
                        <div className="bg-dark-600/50 border border-white/5 rounded-lg p-4">
                            <p className="text-gray-300 mb-4">
                                好的，让我为您分析贵州茅台（600519）的最新股价走势：
                            </p>

                            {/* StockWidget 嵌入 */}
                            <StockWidget ticker="600519" title="贵州茅台 (600519) 近期走势" />

                            <p className="text-gray-300 mt-4 text-sm">
                                以上是基于实时数据的走势分析。您可以点击图表上的数据点查看该日期的相关新闻资讯。
                            </p>
                        </div>
                    </div>
                </div>

                {/* 使用说明 */}
                <div className="glass rounded-lg p-6 mt-8">
                    <h2 className="text-lg font-semibold text-gray-200 mb-3">组件功能</h2>
                    <ul className="text-sm text-gray-400 space-y-2">
                        <li className="flex items-start gap-2">
                            <span className="text-violet-400 mt-0.5">•</span>
                            <span><strong className="text-gray-300">交互式图表</strong>：使用 Recharts 渲染股价，支持查看开高低收价</span>
                        </li>
                        <li className="flex items-start gap-2">
                            <span className="text-violet-400 mt-0.5">•</span>
                            <span><strong className="text-gray-300">异常区标注</strong>：高亮异常波动时段，悬浮显示新闻摘要</span>
                        </li>
                        <li className="flex items-start gap-2">
                            <span className="text-violet-400 mt-0.5">•</span>
                            <span><strong className="text-gray-300">点击联动</strong>：点击数据点，右侧滑出新闻侧边栏</span>
                        </li>
                        <li className="flex items-start gap-2">
                            <span className="text-violet-400 mt-0.5">•</span>
                            <span><strong className="text-gray-300">新闻展示</strong>：展示目标日期±1天的新闻，按热度排序</span>
                        </li>
                        <li className="flex items-start gap-2">
                            <span className="text-violet-400 mt-0.5">•</span>
                            <span><strong className="text-gray-300">响应式设计</strong>：移动端侧边栏全屏显示</span>
                        </li>
                    </ul>
                </div>

                {/* 技术栈 */}
                <div className="glass rounded-lg p-6">
                    <h2 className="text-lg font-semibold text-gray-200 mb-3">技术实现</h2>
                    <div className="flex flex-wrap gap-2">
                        <span className="px-3 py-1 rounded-full bg-violet-500/20 text-violet-300 text-xs font-medium">React</span>
                        <span className="px-3 py-1 rounded-full bg-violet-500/20 text-violet-300 text-xs font-medium">Recharts</span>
                        <span className="px-3 py-1 rounded-full bg-violet-500/20 text-violet-300 text-xs font-medium">Framer Motion</span>
                        <span className="px-3 py-1 rounded-full bg-violet-500/20 text-violet-300 text-xs font-medium">Tailwind CSS</span>
                        <span className="px-3 py-1 rounded-full bg-violet-500/20 text-violet-300 text-xs font-medium">Lucide Icons</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
