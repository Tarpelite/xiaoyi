import dynamic from 'next/dynamic';

const StockTerminal = dynamic(
  () => import('@/components/stock/StockTerminal'),
  {
    ssr: false,
    loading: () => (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="flex items-center gap-3 text-slate-500">
          <div className="w-8 h-8 border-2 border-slate-700 border-t-blue-500 rounded-full animate-spin" />
          <span>加载中...</span>
        </div>
      </div>
    )
  }
);

export default function StockPage() {
  return <StockTerminal ticker="600519" />;
}
