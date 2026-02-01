'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceArea, ReferenceLine, TooltipProps } from 'recharts';
import { motion, AnimatePresence } from 'framer-motion';
import { TrendingUp, Search, Bell, Settings, Menu, Clock, Calendar, ExternalLink, Eye, MessageCircle, Zap, Loader2 } from 'lucide-react';

interface NewsItem {
  id: string;
  title: string;
  summary?: string;
  content_type: string;
  publish_time: string;
  source?: string;
  url?: string;
  read_count: number;
  comment_count: number;
  institution?: string;
  grade?: string;
  notice_type?: string;
}

interface AnomalyPoint {
  date: string;
  price: number;
  score: number;
  description: string;
  method: string;
}

interface AnomalyZone {
  startDate: string;
  endDate: string;
  summary: string;
  sentiment: 'positive' | 'negative' | 'neutral';
  method?: string;
  avg_score?: number;
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

interface NewsSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  news: NewsItem[];
  loading: boolean;
  selectedDate: string;
  ticker: string;
}

interface FloatingCardProps {
  zone: AnomalyZone | null;
  visible: boolean;
  onClose: () => void;
}

const getContentTypeStyle = (type: string) => {
  switch (type) {
    case '研报':
      return { bg: 'bg-purple-500/20', text: 'text-purple-400', border: 'border-purple-500/30', badge: 'bg-purple-500/20 text-purple-300' };
    case '公告':
      return { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500/30', badge: 'bg-amber-500/20 text-amber-300' };
    default:
      return { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500/30', badge: 'bg-blue-500/20 text-blue-300' };
  }
};

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

const CustomTooltip = ({ active, payload }: TooltipProps<number, string>) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload as StockDataPoint;
    const isUp = data.close >= data.open;
    return (
      <div className="bg-slate-900/95 backdrop-blur-xl border border-slate-700/50 rounded-lg p-4 shadow-2xl">
        <div className="flex items-center gap-2 mb-2">
          <Calendar className="w-4 h-4 text-slate-400" />
          <span className="text-slate-300 text-sm">{formatDate(data.date)}</span>
        </div>
        <div className="space-y-1 text-sm">
          <div className="flex justify-between gap-8"><span className="text-slate-400">开盘</span><span className="text-white font-mono">{formatPrice(data.open)}</span></div>
          <div className="flex justify-between gap-8"><span className="text-slate-400">收盘</span><span className={`font-mono font-medium ${isUp ? 'text-green-400' : 'text-red-400'}`}>{formatPrice(data.close)}</span></div>
          <div className="flex justify-between gap-8"><span className="text-slate-400">最高</span><span className="text-white font-mono">{formatPrice(data.high)}</span></div>
          <div className="flex justify-between gap-8"><span className="text-slate-400">最低</span><span className="text-white font-mono">{formatPrice(data.low)}</span></div>
          <div className="flex justify-between gap-8"><span className="text-slate-400">成交量</span><span className="text-white font-mono">{(data.volume / 10000).toFixed(0)}万</span></div>
        </div>
        {data.is_event_triggered && <div className="mt-3 pt-3 border-t border-slate-700/50"><span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-amber-500/20 text-amber-400 text-xs"><Clock className="w-3 h-3" />事件驱动</span></div>}
      </div>
    );
  }
  return null;
};

const FloatingCard: React.FC<FloatingCardProps> = ({ zone, visible, onClose }) => (
  <AnimatePresence>
    {visible && zone && (
      <motion.div
        initial={{ opacity: 0, y: 10, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 10, scale: 0.95 }}
        transition={{ duration: 0.2 }}
        className="fixed z-50"
        style={{ left: '50%', bottom: '100px', transform: 'translateX(-50%)' }}
      >
        <div className="bg-slate-900/95 backdrop-blur-xl border border-slate-700/50 rounded-xl p-4 shadow-2xl max-w-md">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${zone.sentiment === 'positive' ? 'bg-green-500' : zone.sentiment === 'negative' ? 'bg-red-500' : 'bg-blue-500'}`} />
              <span className="text-slate-400 text-xs">{formatDate(zone.startDate)} - {formatDate(zone.endDate)}</span>
            </div>
            <button onClick={onClose} className="text-slate-500 hover:text-slate-300 transition-colors">×</button>
          </div>
          <p className="text-slate-200 text-sm leading-relaxed">{zone.summary}</p>
        </div>
      </motion.div>
    )}
  </AnimatePresence>
);

const SidebarOverlay: React.FC<{ onClick: () => void }> = ({ onClick }) => (
  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClick} className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden" />
);

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
      transition={{ delay: index * 0.05 }}
      className={`block p-4 rounded-lg border ${style.border} bg-slate-900/50 hover:bg-slate-800/50 transition-all duration-200 group`}
    >
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${style.badge}`}>{news.content_type}</span>
        {isHot && <span className="px-2 py-0.5 rounded text-xs font-medium bg-red-500/20 text-red-400">🔥热门</span>}
        {news.notice_type && <span className="px-2 py-0.5 rounded text-xs font-medium bg-slate-700 text-slate-300">{news.notice_type}</span>}
        <span className="text-slate-500 text-xs flex items-center gap-1 ml-auto"><Clock className="w-3 h-3" />{formatDateTime(news.publish_time)}</span>
      </div>
      <h4 className="text-slate-200 font-medium mb-2 group-hover:text-blue-400 transition-colors line-clamp-2">{news.title}</h4>
      {news.summary && <p className="text-slate-500 text-sm line-clamp-2 mb-3">{news.summary}</p>}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 text-slate-500 text-xs">
          <span className="flex items-center gap-1"><Eye className="w-3 h-3" />{formatReadCount(news.read_count)}</span>
          <span className="flex items-center gap-1"><MessageCircle className="w-3 h-3" />{news.comment_count}</span>
        </div>
        {news.content_type === '研报' && news.institution && (
          <span className="text-xs text-slate-400">
            <span className="font-semibold text-slate-300">{news.institution}</span>
            {news.grade && <span className={`ml-1 px-1.5 py-0.5 rounded text-xs ${news.grade.includes('买入') ? 'bg-green-500/20 text-green-400' : news.grade.includes('增持') ? 'bg-blue-500/20 text-blue-400' : news.grade.includes('减持') ? 'bg-red-500/20 text-red-400' : 'bg-slate-700 text-slate-300'}`}>{news.grade}</span>}
          </span>
        )}
        {news.url && <ExternalLink className="w-4 h-4 text-slate-600 group-hover:text-blue-400 transition-colors" />}
      </div>
    </motion.a>
  );
};

const NewsSidebar: React.FC<NewsSidebarProps> = ({ isOpen, onClose, news, loading, selectedDate, ticker }) => {
  // Safely handle date range calculation
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
      <AnimatePresence>{isOpen && <SidebarOverlay onClick={onClose} />}</AnimatePresence>
      <motion.aside
        initial={{ x: '100%' }}
        animate={{ x: isOpen ? 0 : '100%' }}
        exit={{ x: '100%' }}
        transition={{ type: 'spring', damping: 25, stiffness: 200 }}
        className="fixed right-0 top-0 bottom-0 z-50 w-full sm:w-[350px] bg-slate-950 border-l border-slate-800/50 shadow-2xl overflow-hidden flex flex-col"
      >
        <div className="flex items-center justify-between p-4 border-b border-slate-800/50 bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-500/20"><TrendingUp className="w-5 h-5 text-blue-400" /></div>
            <div>
              <h2 className="text-lg font-semibold text-white">{ticker} 相关资讯</h2>
              <p className="text-slate-500 text-sm">{dateRangeText}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-800 transition-colors text-slate-400 hover:text-white">
              <span className="sr-only">关闭</span>
              ×
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-12"><Loader2 className="w-8 h-8 text-blue-500 animate-spin" /></div>
          ) : sortedNews.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-slate-500"><TrendingUp className="w-12 h-12 mb-3 opacity-50" /><p>暂无相关新闻</p></div>
          ) : (
            <div className="p-4 space-y-3">
              <div className="flex items-center gap-2 mb-4 text-sm text-slate-400"><Zap className="w-4 h-4 text-amber-400" /><span>按热度排序</span></div>
              {sortedNews.map((item, index) => <NewsCard key={item.id} news={item} index={index} />)}
            </div>
          )}
        </div>
        <div className="p-3 border-t border-slate-800/50 bg-slate-900/50 text-center text-slate-500 text-xs">数据来源: 东方财富股吧</div>
      </motion.aside>
    </>
  );
};

const AlgoSelect: React.FC<{ label: string; value: string; options: { label: string; value: string }[]; onChange: (v: string) => void }> = ({ label, value, options, onChange }) => (
  <div className="flex items-center gap-2">
    <span className="text-xs text-slate-500">{label}</span>
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="bg-slate-800/50 border border-slate-700 text-xs text-slate-300 rounded px-2 py-1 outline-none focus:border-blue-500"
    >
      {options.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
    </select>
  </div>
);

const API_BASE = typeof window !== 'undefined' ? `/api` : 'http://localhost:8000/api';

async function fetchStockEvents(ticker: string, start?: string, end?: string): Promise<{ price_data: StockDataPoint[]; anomaly_zones: AnomalyZone[]; anomalies: AnomalyPoint[]; significant_news: NewsItem[] }> {
  const params = new URLSearchParams({ code: ticker });
  if (start) params.append('start', start);
  if (end) params.append('end', end);
  const response = await fetch(`${API_BASE}/v2/stock_events?${params}`);
  if (!response.ok) throw new Error('Failed to fetch stock events');
  return response.json();
}

async function fetchNews(ticker: string, date: string, range: number = 1): Promise<NewsItem[]> {
  const params = new URLSearchParams({ ticker, date, range: range.toString() });
  const response = await fetch(`${API_BASE}/v2/news?${params}`);
  if (!response.ok) throw new Error('Failed to fetch news');
  const data = await response.json();
  return data.news;
}

async function fetchAnomalyZones(ticker: string, days: number = 30): Promise<AnomalyZone[]> {
  const params = new URLSearchParams({ ticker, days: days.toString() });
  const response = await fetch(`${API_BASE}/v2/anomaly_zones?${params}`);
  if (!response.ok) throw new Error('Failed to fetch anomaly zones');
  const data = await response.json();
  return data.anomaly_zones;
}



export const StockTerminal: React.FC<{ ticker?: string; initialDate?: string }> = ({ ticker = '600519', initialDate }) => {
  const [stockData, setStockData] = useState<StockDataPoint[]>([]);
  const [anomalyZones, setAnomalyZones] = useState<AnomalyZone[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyPoint[]>([]); // New state
  const [news, setNews] = useState<NewsItem[]>([]);

  // Algorithm Selection State
  const [trendAlgo, setTrendAlgo] = useState<string>('plr');
  const [anomalyAlgo, setAnomalyAlgo] = useState<string>('all');

  const [selectedDate, setSelectedDate] = useState<string>(initialDate || '');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [newsLoading, setNewsLoading] = useState(false);
  const [activeZone, setActiveZone] = useState<AnomalyZone | null>(null);
  const tickerRef = useRef(ticker);

  useEffect(() => {
    tickerRef.current = ticker;
  }, [ticker]);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        console.log('Fetching stock events for:', tickerRef.current);
        const data = await fetchStockEvents(tickerRef.current);
        console.log('Received data:', {
          priceDataCount: data.price_data.length,
          anomalyZonesCount: data.anomaly_zones.length,
          anomaliesCount: (data.anomalies || []).length,
          significantNewsCount: data.significant_news.length
        });
        setStockData(data.price_data);
        setAnomalyZones(data.anomaly_zones);
        setAnomalies(data.anomalies || []); // Set anomalies
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

  useEffect(() => {
    const loadNews = async () => {
      if (!sidebarOpen || !selectedDate) return;
      setNewsLoading(true);
      try {
        console.log('Fetching news for:', { ticker: tickerRef.current, date: selectedDate });
        const newsData = await fetchNews(tickerRef.current, selectedDate, 1);
        console.log('News count:', newsData.length);
        setNews(newsData);
      } catch (error) {
        console.error('Failed to load news:', error);
      } finally {
        setNewsLoading(false);
      }
    };
    loadNews();
  }, [sidebarOpen, selectedDate]);

  // Filtered Data
  const visibleZones = anomalyZones.filter(z => {
    if (trendAlgo === 'all') return true;
    return z.method === trendAlgo;
  });

  const visibleAnomalies = anomalies.filter(a => {
    if (anomalyAlgo === 'all') return true;
    return a.method === anomalyAlgo;
  });

  const handleDateSelect = useCallback((date: string) => {
    console.log('Date selected:', date);
    setSelectedDate(date);
    setSidebarOpen(true);
  }, []);

  const handleCloseSidebar = useCallback(() => setSidebarOpen(false), []);

  const handleManualRefresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchStockEvents(tickerRef.current);
      setStockData(data.price_data);
      setAnomalyZones(data.anomaly_zones);
    } catch (error) {
      console.error('Failed to refresh:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  const currentPrice = stockData.length > 0 ? stockData[stockData.length - 1]?.close : 0;
  const previousPrice = stockData.length > 1 ? stockData[stockData.length - 2]?.close : currentPrice;
  const priceChange = currentPrice - previousPrice;
  const priceChangePercent = previousPrice > 0 ? (priceChange / previousPrice) * 100 : 0;

  const gradientOffset = () => {
    if (!stockData.length) return 0;
    const dataMax = Math.max(...stockData.map((i) => i.close));
    const dataMin = Math.min(...stockData.map((i) => i.close));
    if (dataMax === dataMin) return 0;
    return (dataMax - stockData[stockData.length - 1].close) / (dataMax - dataMin);
  };

  const off = gradientOffset();

  return (
    <div className="min-h-screen bg-[#050505] text-white">
      <header className="border-b border-slate-800/50 bg-slate-900/50 backdrop-blur-xl sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Menu className="w-5 h-5 text-slate-400 lg:hidden" />
            <div className="flex items-center gap-2">
              <TrendingUp className="w-6 h-6 text-blue-500" />
              <span className="text-xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">FinanceAI</span>
            </div>
          </div>
          <div className="hidden sm:flex items-center gap-4">
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800/50 border border-slate-700/50">
              <span className="text-2xl font-bold text-white">{ticker}</span>
              <span className="text-slate-400">股票</span>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold text-white">${currentPrice.toFixed(2)}</div>
              <div className={`text-sm ${priceChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(2)} ({priceChangePercent.toFixed(2)}%)
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative hidden sm:block">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input type="text" placeholder="搜索股票..." className="pl-10 pr-4 py-2 rounded-lg bg-slate-800/50 border border-slate-700/50 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors w-48" />
            </div>
            <button className="p-2 rounded-lg hover:bg-slate-800/50 transition-colors text-slate-400 hover:text-white"><Bell className="w-5 h-5" /></button>
            <button className="p-2 rounded-lg hover:bg-slate-800/50 transition-colors text-slate-400 hover:text-white"><Settings className="w-5 h-5" /></button>
          </div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto p-4 lg:p-6">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="lg:col-span-3">
            {loading ? (
              <div className="h-[500px] rounded-xl bg-slate-900/50 border border-slate-800/50 animate-pulse flex items-center justify-center">
                <div className="flex items-center gap-3 text-slate-500">
                  <Loader2 className="w-8 h-8 border-2 border-slate-700 border-t-blue-500 rounded-full animate-spin" />
                  <span>加载数据中...</span>
                </div>
              </div>
            ) : (
              <div className="relative w-full h-full min-h-[400px] bg-slate-950/50 backdrop-blur-md rounded-xl border border-slate-800/50 p-4 shadow-2xl">
                <div className="absolute top-4 left-4 right-4 flex items-center justify-between z-10">
                  <div className="flex items-center gap-4">
                    <h3 className="text-lg font-semibold text-white">股价走势</h3>
                    <div className="flex gap-3 ml-2">
                      <AlgoSelect
                        label="趋势"
                        value={trendAlgo}
                        options={[
                          { label: 'PLR (线性分段)', value: 'plr' },
                          { label: 'PELT (变点检测)', value: 'pelt' },
                          { label: 'HMM (马尔可夫)', value: 'hmm' },
                          { label: '全部', value: 'all' }
                        ]}
                        onChange={setTrendAlgo}
                      />
                      <AlgoSelect
                        label="异常"
                        value={anomalyAlgo}
                        options={[
                          { label: '全部', value: 'all' },
                          { label: 'BCPD (贝叶斯)', value: 'bcpd' },
                          { label: 'STL+CUSUM', value: 'stl_cusum' },
                          { label: 'Matrix Profile', value: 'matrix_profile' }
                        ]}
                        onChange={setAnomalyAlgo}
                      />
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-slate-400">
                    <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-green-500/50" />上涨</span>
                    <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-500/50" />下跌</span>
                  </div>
                  <button onClick={handleManualRefresh} className="px-2 py-1 text-xs bg-blue-500/20 text-blue-400 rounded hover:bg-blue-500/30 transition-colors">
                    刷新数据
                  </button>
                </div>
                <ResponsiveContainer width="100%" height="100%" className="pt-12">
                  <AreaChart data={stockData} onClick={(e) => { if (e && e.activeLabel) { const dp = stockData.find(d => d.date === e.activeLabel); if (dp) handleDateSelect(dp.date); } }} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorClose" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
                        <stop offset={off} stopColor="#3b82f6" stopOpacity={0.1} />
                        <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                    <XAxis dataKey="date" stroke="#64748b" tick={{ fill: '#64748b', fontSize: 12 }} tickFormatter={formatDate} tickLine={false} axisLine={false} />
                    <YAxis stroke="#64748b" tick={{ fill: '#64748b', fontSize: 12 }} tickFormatter={(v) => v.toFixed(2)} tickLine={false} axisLine={false} domain={['auto', 'auto']} />
                    <Tooltip content={<CustomTooltip />} />

                    {/* Render Filtered Zones */}
                    {visibleZones.map((zone, idx) => (
                      <ReferenceArea
                        key={`zone-${idx}`}
                        x1={zone.startDate}
                        x2={zone.endDate}
                        fill={zone.sentiment === 'positive' ? 'rgba(34, 197, 94, 0.1)' : zone.sentiment === 'negative' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(59, 130, 246, 0.1)'}
                        fillOpacity={1}
                        stroke={zone.sentiment === 'positive' ? '#22c55e' : zone.sentiment === 'negative' ? '#ef4444' : '#3b82f6'}
                        strokeOpacity={0.4}
                        onMouseEnter={() => setActiveZone(zone)}
                        onMouseLeave={() => setActiveZone(null)}
                        className="cursor-pointer transition-all duration-300"
                      />
                    ))}

                    {/* Render Filtered Anomalies */}
                    {visibleAnomalies.map((anom, idx) => (
                      <ReferenceLine
                        key={`anom-${idx}`}
                        x={anom.date}
                        stroke="rgba(255, 255, 255, 0.3)"
                        strokeDasharray="3 3"
                      />
                    ))}

                    {selectedDate && <ReferenceLine x={selectedDate} stroke="#3b82f6" strokeDasharray="5 5" strokeWidth={2} />}

                    <Area type="monotone" dataKey="close" stroke="#3b82f6" strokeWidth={2} fill="url(#colorClose)" dot={(props) => {
                      const { cx, cy, payload, index } = props;
                      const isSelected = payload.date === selectedDate;
                      const isEvent = payload.is_event_triggered;

                      // Check for anomaly match
                      const isAnomaly = visibleAnomalies.find(a => a.date === payload.date);

                      if (isAnomaly) {
                        return (
                          <circle key={`anom-dot-${index}`} cx={cx} cy={cy} r={6} fill="#fbbf24" stroke="#fff" strokeWidth={2} className="cursor-pointer animate-pulse" />
                        );
                      }

                      return (
                        <g key={index}>
                          <circle
                            cx={cx}
                            cy={cy}
                            r={isSelected ? 8 : isEvent ? 6 : 4}
                            fill={payload.close >= payload.open ? '#22c55e' : '#ef4444'}
                            stroke={isSelected ? '#3b82f6' : 'none'}
                            strokeWidth={2}
                            className="transition-all duration-200 cursor-pointer"
                          />
                          {isEvent && (
                            <circle cx={cx} cy={cy} r="6" fill="none" stroke="#fbbf24" strokeWidth="2" opacity="0.6">
                              <animate attributeName="r" values="6;12;6" dur="2s" repeatCount="indefinite" />
                              <animate attributeName="opacity" values="0.6;0;0.6" dur="2s" repeatCount="indefinite" />
                            </circle>
                          )}
                        </g>
                      );
                    }} />
                  </AreaChart>
                </ResponsiveContainer>
                <FloatingCard zone={activeZone} visible={!!activeZone} onClose={() => setActiveZone(null)} />
              </div>
            )}
          </div>
          <div className="lg:col-span-1 space-y-4">
            <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800/50">
              <h3 className="text-sm font-semibold text-slate-400 mb-3">快速统计</h3>
              <div className="space-y-3">
                <div className="flex justify-between"><span className="text-slate-500">最高价</span><span className="text-white font-mono">${stockData.length > 0 ? Math.max(...stockData.map(d => d.high)).toFixed(2) : '-'}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">最低价</span><span className="text-white font-mono">${stockData.length > 0 ? Math.min(...stockData.map(d => d.low)).toFixed(2) : '-'}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">成交量</span><span className="text-white font-mono">{stockData.length > 0 ? (stockData.reduce((acc, d) => acc + d.volume, 0) / 10000).toFixed(0) + '万' : '-'}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">事件天数</span><span className="text-amber-400 font-mono">{stockData.filter(d => d.is_event_triggered).length}天</span></div>
              </div>
            </div>
            <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800/50">
              <h3 className="text-sm font-semibold text-slate-400 mb-3">波动区间</h3>
              <div className="space-y-2">
                {anomalyZones.slice(0, 5).map((zone, idx) => (
                  <div key={idx} className="p-3 rounded-lg bg-slate-800/50 hover:bg-slate-800 transition-colors cursor-pointer" onMouseEnter={() => setActiveZone(zone)} onMouseLeave={() => setActiveZone(null)} onClick={() => handleDateSelect(zone.startDate)}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`w-2 h-2 rounded-full ${zone.sentiment === 'positive' ? 'bg-green-500' : zone.sentiment === 'negative' ? 'bg-red-500' : 'bg-blue-500'}`} />
                      <span className="text-xs text-slate-400">{formatDate(zone.startDate)} - {formatDate(zone.endDate)}</span>
                    </div>
                    <p className="text-sm text-slate-300 line-clamp-2">{zone.summary}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </main>
      <NewsSidebar isOpen={sidebarOpen} onClose={handleCloseSidebar} news={news} loading={newsLoading} selectedDate={selectedDate} ticker={ticker} />
    </div>
  );
};

export default StockTerminal;
