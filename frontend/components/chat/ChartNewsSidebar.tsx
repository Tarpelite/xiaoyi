'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { TrendingUp, Clock, Calendar, Eye, MessageCircle, ExternalLink, Loader2, Zap } from 'lucide-react';

interface NewsItem {
    id: string;
    title: string;
    summary?: string;
    content_type: string;
    publish_time: string;
    url?: string;
    read_count: number;
    comment_count: number;
    institution?: string;
    grade?: string;
    notice_type?: string;
}

interface ChartNewsSidebarProps {
    isOpen: boolean;
    onClose: () => void;
    news: NewsItem[];
    loading: boolean;
    selectedDate: string | null;
    ticker?: string;
}

const formatDate = (dateStr: string) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
};

const formatDateTime = (dateStr: string) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
};

const formatReadCount = (count: number) => {
    if (count >= 10000) return (count / 10000).toFixed(1) + '万';
    return count.toString();
};

const getContentTypeStyle = (type: string) => {
    // 处理中英文content_type
    const normalizedType = type.toLowerCase();

    if (normalizedType === '研报' || normalizedType === 'report') {
        return { badge: 'bg-purple-500/20 text-purple-300 border-purple-500/30', border: 'border-purple-500/30', icon: '📊' };
    }
    if (normalizedType === '公告' || normalizedType === 'notice') {
        return { badge: 'bg-amber-500/20 text-amber-300 border-amber-500/30', border: 'border-amber-500/30', icon: '📢' };
    }
    // 默认为资讯
    return { badge: 'bg-violet-500/20 text-violet-300 border-violet-500/30', border: 'border-violet-500/30', icon: '📰' };
};

export function ChartNewsSidebar({ isOpen, onClose, news, loading, selectedDate, ticker }: ChartNewsSidebarProps) {
    const dateRangeStart = selectedDate ? new Date(selectedDate) : new Date();
    if (selectedDate) dateRangeStart.setDate(dateRangeStart.getDate() - 1);

    const dateRangeEnd = selectedDate ? new Date(selectedDate) : new Date();
    if (selectedDate) dateRangeEnd.setDate(dateRangeEnd.getDate() + 1);

    // 四层排序：热门资讯 → 所有公告 → 所有研报 → 其他资讯
    const hotNews = news.filter(n => n.read_count >= 10000);
    const allAnnouncements = news.filter(n => {
        const type = (n.content_type || '').toLowerCase();
        return n.read_count < 10000 && (type === '公告' || type === 'notice');
    });
    const allReports = news.filter(n => {
        const type = (n.content_type || '').toLowerCase();
        return n.read_count < 10000 && (type === '研报' || type === 'report');
    });
    const regularNews = news.filter(n => {
        const type = (n.content_type || '').toLowerCase();
        return n.read_count < 10000 && !['研报', 'report', '公告', 'notice'].includes(type);
    });

    // 热门和其他资讯按热度排序
    const sortByScore = (a: NewsItem, b: NewsItem) => {
        const scoreA = a.read_count + a.comment_count * 5;
        const scoreB = b.read_count + b.comment_count * 5;
        return scoreB - scoreA;
    };

    // 公告和研报按时间排序
    const sortByTime = (a: NewsItem, b: NewsItem) => {
        return new Date(b.publish_time).getTime() - new Date(a.publish_time).getTime();
    };

    hotNews.sort(sortByScore);
    allAnnouncements.sort(sortByTime);
    allReports.sort(sortByTime);
    regularNews.sort(sortByScore);

    const sortedNews = [...hotNews, ...allAnnouncements, ...allReports, ...regularNews];

    const dateRangeText = selectedDate
        ? `${formatDate(dateRangeStart.toISOString())} - ${formatDate(dateRangeEnd.toISOString())}`
        : '选择日期以查看新闻';

    return (
        <>
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={onClose}
                        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden"
                    />
                )}
            </AnimatePresence>
            <motion.aside
                initial={{ x: '100%' }}
                animate={{ x: isOpen ? 0 : '100%' }}
                exit={{ x: '100%' }}
                transition={{ type: 'spring', damping: 25, stiffness: 200 }}
                className="fixed right-0 top-0 bottom-0 z-50 w-full sm:w-[340px] glass border-l border-white/5 shadow-2xl overflow-hidden flex flex-col"
            >
                <div className="flex items-center justify-between p-3 border-b border-white/5 bg-dark-700/30">
                    <div className="flex items-center gap-2">
                        <div className="p-1.5 rounded bg-violet-500/20"><TrendingUp className="w-4 h-4 text-violet-400" /></div>
                        <div>
                            <h2 className="text-base font-semibold text-gray-200">{ticker || '股票'} 相关资讯</h2>
                            <p className="text-gray-500 text-xs">{dateRangeText}</p>
                        </div>
                    </div>
                    <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-dark-600 transition-colors text-gray-400 hover:text-white text-xl leading-none">
                        ×
                    </button>
                </div>
                <div className="flex-1 overflow-y-auto">
                    {loading ? (
                        <div className="flex items-center justify-center py-8"><Loader2 className="w-6 h-6 text-violet-500 animate-spin" /></div>
                    ) : sortedNews.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-8 text-gray-500">
                            <TrendingUp className="w-10 h-10 mb-2 opacity-50" />
                            <p className="text-sm">暂无相关新闻</p>
                        </div>
                    ) : (
                        <div className="p-3 space-y-2">
                            <div className="flex items-center gap-1.5 mb-2 text-xs text-gray-400">
                                <Zap className="w-3 h-3 text-amber-400" />
                                <span>按热度排序</span>
                            </div>
                            {sortedNews.map((item, index) => {
                                const style = getContentTypeStyle(item.content_type);
                                const isHot = item.read_count >= 10000;
                                return (
                                    <motion.a
                                        key={item.id}
                                        href={item.url || '#'}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        initial={{ opacity: 0, x: 20 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        transition={{ delay: index * 0.03 }}
                                        className={`block p-3 rounded-lg border ${style.border} bg-dark-700/30 hover:bg-dark-600/50 transition-all duration-200 group`}
                                    >
                                        <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                                            <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${style.badge}`}>{item.content_type}</span>
                                            {isHot && <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-red-500/20 text-red-400">🔥热门</span>}
                                            {item.notice_type && <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-dark-600 text-gray-300">{item.notice_type}</span>}
                                            <span className="text-gray-500 text-xs flex items-center gap-1 ml-auto">
                                                <Clock className="w-2.5 h-2.5" />{formatDateTime(item.publish_time)}
                                            </span>
                                        </div>
                                        <h4 className="text-gray-200 text-sm font-medium mb-1.5 group-hover:text-violet-400 transition-colors line-clamp-2">
                                            {item.title}
                                        </h4>
                                        {item.summary && <p className="text-gray-500 text-xs line-clamp-2 mb-2">{item.summary}</p>}
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2 text-gray-500 text-xs">
                                                <span className="flex items-center gap-1"><Eye className="w-2.5 h-2.5" />{formatReadCount(item.read_count)}</span>
                                                <span className="flex items-center gap-1"><MessageCircle className="w-2.5 h-2.5" />{item.comment_count}</span>
                                            </div>
                                            {item.content_type === '研报' && item.institution && (
                                                <span className="text-xs text-gray-400">
                                                    <span className="font-semibold text-gray-300">{item.institution}</span>
                                                    {item.grade && (
                                                        <span className={`ml-1 px-1 py-0.5 rounded text-xs ${item.grade.includes('买入') ? 'bg-green-500/20 text-green-400' :
                                                            item.grade.includes('增持') ? 'bg-violet-500/20 text-violet-400' :
                                                                item.grade.includes('减持') ? 'bg-red-500/20 text-red-400' :
                                                                    'bg-dark-600 text-gray-300'
                                                            }`}>{item.grade}</span>
                                                    )}
                                                </span>
                                            )}
                                            {item.url && <ExternalLink className="w-3 h-3 text-gray-600 group-hover:text-violet-400 transition-colors" />}
                                        </div>
                                    </motion.a>
                                );
                            })}
                        </div>
                    )}
                </div>
            </motion.aside>
        </>
    );
}
