import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: '小易猜猜 - TimeAgent',
  description: '人机友好的时间序列预测助手',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN">
      <body className="font-sans antialiased">
        {children}
      </body>
    </html>
  )
}