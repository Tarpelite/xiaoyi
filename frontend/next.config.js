/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Docker 部署需要 standalone 输出
  // 逻辑说明：
  // 1. 如果设置了 NEXT_OUTPUT_STANDALONE=true，强制启用
  // 2. 如果设置了 NEXT_OUTPUT_STANDALONE=false，强制禁用
  // 3. 否则，在非 Windows 系统（Linux/Docker）上自动启用，Windows 上禁用
  //    这样可以避免 Windows 上的符号链接权限问题（EPERM 错误）
  ...(process.env.NEXT_OUTPUT_STANDALONE === 'true' ||
    (process.env.NEXT_OUTPUT_STANDALONE !== 'false' && process.platform !== 'win32')
    ? { output: 'standalone' }
    : {}),
  experimental: {
    serverActions: {
      bodySizeLimit: '2mb',
    },
  },
}

module.exports = nextConfig