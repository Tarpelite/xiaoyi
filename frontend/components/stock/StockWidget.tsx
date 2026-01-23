'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceArea, ReferenceLine, TooltipProps } from 'recharts';
import { motion, AnimatePresence } from 'framer-motion';
import { TrendingUp, Clock, Calendar, Eye, MessageCircle, ExternalLink, Loader2, Zap } from 'lucide-react';

// 接口定义
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

interface StockDataPoint {
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    is_event_triggered?: boolean;
}

interface AnomalyZone {
    startDate: string;
    endDate: string;
    summary: string;
    sentiment: 'positive' | 'negative' | 'neutral';
}

interface StockWidgetProps {
    ticker: string;
    title?: string;
}

// 工具函数
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

const formatPrice = (price: number) => price.toFixed(2);

const getContentTypeStyle = (type: string) => {
    switch (type) {
        case '研报':
            return { bg: 'bg-purple-500/20', text: 'text-purple-400', border: 'border-purple-500/30', badge: 'bg-purple-500/20 text-purple-300' };
        case '公告':
            return { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500/30', badge: 'bg-amber-500/20 text-amber-300' };
        default:
            return { bg: 'bg-violet-500/20', text: 'text-violet-400', border: 'border-violet-500/30', badge: 'bg-violet-500/20 text-violet-300' };
    }
};

const API_BASE = typeof window !== 'undefined' ? `/api` : 'http://localhost:8000/api';

// 自定义 Tooltip
const CustomTooltip = ({ active, payload }: TooltipProps<number, string>) => {
    if (active && payload && payload.length) {
        const data = payload[0].payload as StockDataPoint;
        const isUp = data.close >= data.open;
        return (
            <div className="glass rounded-lg p-3 shadow-2xl border border-white/10">
                <div className="flex items-center gap-2 mb-2">
                    <Calendar className="w-3.5 h-3.5 text-gray-400" />
                    <span className="text-gray-300 text-xs">{formatDate(data.date)}</span>
                </div>
                <div className="space-y-0.5 text-xs">
                    <div className="flex justify-between gap-6"><span className="text-gray-400">开盘</span><span className="text-gray-200 font-mono">{formatPrice(data.open)}</span></div>
                    <div className="flex justify-between gap-6"><span className="text-gray-400">收盘</span><span className={`font-mono font-medium ${isUp ? 'text-green-400' : 'text-red-400'}`}>{formatPrice(data.close)}</span></div>
                    <div className="flex justify-between gap-6"><span className="text-gray-400">最高</span><span className="text-gray-200 font-mono">{formatPrice(data.high)}</span></div>
                    <div className="flex justify-between gap-6"><span className="text-gray-400">最低</span><span className="text-gray-200 font-mono">{formatPrice(data.low)}</span></div>
                </div>
                {data.is_event_triggered && <div className="mt-2 pt-2 border-t border-white/10"><span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-400 text-xs"><Clock className="w-2.5 h-2.5" />事件驱动</span></div>}
            </div>
        );
    }
    return null;
};

// 新闻卡片组件
const NewsCard: React.FC<{ news: NewsItem; index: number }> = ({ news, index }) => {
    const style = getContentTypeStyle(news.content_type);
    const isHot = news.read_count >= 10000;
    return (
        <motion.a
            href={news.url || '#'}
            target="_blank"
            rel="noopener noreferrer"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.03 }}
            className={`block p-3 rounded-lg border ${style.border} bg-dark-700/30 hover:bg-dark-600/50 transition-all duration-200 group`}
        >
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${style.badge}`}>{news.content_type}</span>
                {isHot && <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-red-500/20 text-red-400">🔥热门</span>}
                {news.notice_type && <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-dark-600 text-gray-300">{news.notice_type}</span>}
                <span className="text-gray-500 text-xs flex items-center gap-1 ml-auto"><Clock className="w-2.5 h-2.5" />{formatDateTime(news.publish_time)}</span>
            </div>
            <h4 className="text-gray-200 text-sm font-medium mb-1.5 group-hover:text-violet-400 transition-colors line-clamp-2">{news.title}</h4>
            {news.summary && <p className="text-gray-500 text-xs line-clamp-2 mb-2">{news.summary}</p>}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-gray-500 text-xs">
                    <span className="flex items-center gap-1"><Eye className="w-2.5 h-2.5" />{formatReadCount(news.read_count)}</span>
                    <span className="flex items-center gap-1"><MessageCircle className="w-2.5 h-2.5" />{news.comment_count}</span>
                </div>
                {news.content_type === '研报' && news.institution && (
                    <span className="text-xs text-gray-400">
                        <span className="font-semibold text-gray-300">{news.institution}</span>
                        {news.grade && <span className={`ml-1 px-1 py-0.5 rounded text-xs ${news.grade.includes('买入') ? 'bg-green-500/20 text-green-400' : news.grade.includes('增持') ? 'bg-violet-500/20 text-violet-400' : news.grade.includes('减持') ? 'bg-red-500/20 text-red-400' : 'bg-dark-600 text-gray-300'}`}>{news.grade}</span>}
                    </span>
                )}
                {news.url && <ExternalLink className="w-3 h-3 text-gray-600 group-hover:text-violet-400 transition-colors" />}
            </div>
        </motion.a>
    );
};

// 侧边栏组件
const NewsSidebar: React.FC<{ isOpen: boolean; onClose: () => void; news: NewsItem[]; loading: boolean; selectedDate: string; ticker: string }> = ({ isOpen, onClose, news, loading, selectedDate, ticker }) => {
    const dateRangeStart = selectedDate ? new Date(selectedDate) : new Date();
    if (selectedDate) dateRangeStart.setDate(dateRangeStart.getDate() - 1);

    const dateRangeEnd = selectedDate ? new Date(selectedDate) : new Date();
    if (selectedDate) dateRangeEnd.setDate(dateRangeEnd.getDate() + 1);

    const sortedNews = [...news].sort((a, b) => {
        const scoreA = a.read_count + a.comment_count * 5;
        const scoreB = b.read_count + b.comment_count * 5;
        return scoreB - scoreA;
    });

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
                            <h2 className="text-base font-semibold text-gray-200">{ticker} 相关资讯</h2>
                            <p className="text-gray-500 text-xs">{dateRangeText}</p>
                        </div>
                    </div>
                    <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-dark-600 transition-colors text-gray-400 hover:text-white">
                        ×
                    </button>
                </div>
                <div className="flex-1 overflow-y-auto">
                    {loading ? (
                        <div className="flex items-center justify-center py-8"><Loader2 className="w-6 h-6 text-violet-500 animate-spin" /></div>
                    ) : sortedNews.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-8 text-gray-500"><TrendingUp className="w-10 h-10 mb-2 opacity-50" /><p className="text-sm">暂无相关新闻</p></div>
                    ) : (
                        <div className="p-3 space-y-2">
                            <div className="flex items-center gap-1.5 mb-2 text-xs text-gray-400"><Zap className="w-3 h-3 text-amber-400" /><span>按热度排序</span></div>
                            {sortedNews.map((item, index) => <NewsCard key={item.id} news={item} index={index} />)}
                        </div>
                    )}
                </div>
            </motion.aside>
        </>
    );
};

// 主组件
export function StockWidget({ ticker, title }: StockWidgetProps) {
    const [stockData, setStockData] = useState<StockDataPoint[]>([]);
    const [anomalyZones, setAnomalyZones] = useState<AnomalyZone[]>([]);
    const [news, setNews] = useState<NewsItem[]>([]);
    const [selectedDate, setSelectedDate] = useState<string>('');
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const [loading, setLoading] = useState(true);
    const [newsLoading, setNewsLoading] = useState(false);
    const [activeZone, setActiveZone] = useState<AnomalyZone | null>(null);

    // 加载股票数据
    useEffect(() => {
        const loadData = async () => {
            setLoading(true);
            try {
                const response = await fetch(`${API_BASE}/stock_events?code=${ticker}`);
                if (!response.ok) throw new Error('Failed to fetch');
                const data = await response.json();
                setStockData(data.price_data);
                setAnomalyZones(data.anomaly_zones);
                if (data.price_data.length > 0 && !selectedDate) {
                    setSelectedDate(data.price_data[data.price_data.length - 1].date);
                }
            } catch (error) {
                console.error('Failed to load stock data:', error);
            } finally {
                setLoading(false);
            }
        };
        loadData();
    }, [ticker]);

    // 加载新闻
    useEffect(() => {
        const loadNews = async () => {
            if (!sidebarOpen || !selectedDate) return;
            setNewsLoading(true);
            try {
                const response = await fetch(`${API_BASE}/news?ticker=${ticker}&date=${selectedDate}&range=1`);
                if (!response.ok) throw new Error('Failed to fetch news');
                const data = await response.json();
                setNews(data.news);
            } catch (error) {
                console.error('Failed to load news:', error);
            } finally {
                setNewsLoading(false);
            }
        };
        loadNews();
    }, [sidebarOpen, selectedDate, ticker]);

    const handleDateSelect = useCallback((date: string) => {
        setSelectedDate(date);
        setSidebarOpen(true);
    }, []);

    const currentPrice = stockData[stockData.length - 1]?.close || 0;
    const previousPrice = stockData[stockData.length - 2]?.close || currentPrice;
    const priceChange = currentPrice - previousPrice;
    const priceChangePercent = previousPrice > 0 ? (priceChange / previousPrice) * 100 : 0;

    const gradientOffset = () => {
        if (!stockData.length) return 0;
        const dataMax = Math.max(...stockData.map(i => i.close));
        const dataMin = Math.min(...stockData.map(i => i.close));
        if (dataMax === dataMin) return 0;
        return (dataMax - stockData[stockData.length - 1].close) / (dataMax - dataMin);
    };

    const off = gradientOffset();

    return (
        <div className="w-full max-w-4xl">
            {/* 标题区 */}
            {title && (
                <div className="flex items-center gap-2 mb-3">
                    <TrendingUp className="w-5 h-5 text-violet-400" />
                    <h3 className="text-base font-semibold text-gray-200">{title}</h3>
                    <span className="px-2 py-0.5 rounded bg-violet-500/20 text-violet-300 text-xs font-medium">{ticker}</span>
                </div>
            )}

            {/* 价格信息 */}
            <div className="flex items-center gap-4 mb-3">
                <div className="text-2xl font-bold text-gray-200">${currentPrice.toFixed(2)}</div>
                <div className={`text-sm ${priceChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(2)} ({priceChangePercent.toFixed(2)}%)
                </div>
            </div>

            {/* 图表区 */}
            <div className="glass rounded-lg p-4">
                {loading ? (
                    <div className="h-80 flex items-center justify-center">
                        <Loader2 className="w-8 h-8 text-violet-500 animate-spin" />
                    </div>
                ) : (
                    <ResponsiveContainer width="100%" height={320}>
                        <AreaChart data={stockData} onClick={(e) => { if (e && e.activeLabel) { const dp = stockData.find(d => d.date === e.activeLabel); if (dp) handleDateSelect(dp.date); } }} margin={{ top: 5, right: 10, left: 0, bottom: 20 }}>
                            <defs>
                                <linearGradient id="colorCloseViolet" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.3} />
                                    <stop offset={off} stopColor="#8b5cf6" stopOpacity={0.1} />
                                    <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#3a3a4a" vertical={false} />
                            <XAxis dataKey="date" stroke="#6b7280" tick={{ fill: '#6b7280', fontSize: 11 }} tickFormatter={formatDate} tickLine={false} axisLine={false} />
                            <YAxis stroke="#6b7280" tick={{ fill: '#6b7280', fontSize: 11 }} tickFormatter={(v) => v.toFixed(2)} tickLine={false} axisLine={false} domain={['auto', 'auto']} />
                            <Tooltip content={<CustomTooltip />} />
                            {anomalyZones.map((zone, idx) => (
                                <ReferenceArea key={idx} x1={zone.startDate} x2={zone.endDate} fill={zone.sentiment === 'positive' ? 'rgba(16, 185, 129, 0.15)' : zone.sentiment === 'negative' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(139, 92, 246, 0.15)'} fillOpacity={1} stroke={zone.sentiment === 'positive' ? '#10b981' : zone.sentiment === 'negative' ? '#ef4444' : '#8b5cf6'} strokeOpacity={0.5} onMouseEnter={() => setActiveZone(zone)} onMouseLeave={() => setActiveZone(null)} className="cursor-pointer transition-all duration-300" />
                            ))}
                            {selectedDate && <ReferenceLine x={selectedDate} stroke="#8b5cf6" strokeDasharray="5 5" strokeWidth={2} />}
                            <Area type="monotone" dataKey="close" stroke="#8b5cf6" strokeWidth={2} fill="url(#colorCloseViolet)" dot={(props) => {
                                const { cx, cy, payload } = props;
                                const isSelected = payload.date === selectedDate;
                                const isEvent = payload.is_event_triggered;
                                return (
                                    <g>
                                        <circle cx={cx} cy={cy} r={isSelected ? 6 : isEvent ? 5 : 3} fill={payload.close >= payload.open ? '#10b981' : '#ef4444'} stroke={isSelected ? '#8b5cf6' : 'none'} strokeWidth={2} className="transition-all duration-200 cursor-pointer" />
                                        {isEvent && (
                                            <circle cx={cx} cy={cy} r="5" fill="none" stroke="#a855f7" strokeWidth="2" opacity="0.6">
                                                <animate attributeName="r" values="5;9;5" dur="2s" repeatCount="indefinite" />
                                                <animate attributeName="opacity" values="0.6;0;0.6" dur="2s" repeatCount="indefinite" />
                                            </circle>
                                        )}
                                    </g>
                                );
                            }} />
                        </AreaChart>
                    </ResponsiveContainer>
                )}
            </div>

            {/* 浮动卡片 */}
            <AnimatePresence>
                {activeZone && (
                    <motion.div initial={{ opacity: 0, y: 10, scale: 0.95 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 10, scale: 0.95 }} transition={{ duration: 0.2 }} className="fixed z-50" style={{ left: '50%', bottom: '100px', transform: 'translateX(-50%)' }}>
                        <div className="glass rounded-xl p-3 shadow-2xl max-w-md border border-white/10">
                            <div className="flex items-center justify-between mb-2">
                                <div className="flex items-center gap-2">
                                    <div className={`w-2 h-2 rounded-full ${activeZone.sentiment === 'positive' ? 'bg-green-500' : activeZone.sentiment === 'negative' ? 'bg-red-500' : 'bg-violet-500'}`} />
                                    <span className="text-gray-400 text-xs">{formatDate(activeZone.startDate)} - {formatDate(activeZone.endDate)}</span>
                                </div>
                                <button onClick={() => setActiveZone(null)} className="text-gray-500 hover:text-gray-300 transition-colors text-lg leading-none">×</button>
                            </div>
                            <p className="text-gray-200 text-sm leading-relaxed">{activeZone.summary}</p>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* 侧边栏 */}
            <NewsSidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} news={news} loading={newsLoading} selectedDate={selectedDate} ticker={ticker} />
        </div>
    );
}
