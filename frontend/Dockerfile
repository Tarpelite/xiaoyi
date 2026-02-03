# Stage 1: 依赖安装
FROM aqtbrodh2awvkc.xuanyuan.run/node:20-alpine AS deps
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories
RUN apk add --no-cache libc6-compat
WORKDIR /app

RUN npm install -g pnpm --registry=https://registry.npmmirror.com
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile --registry=https://registry.npmmirror.com

# Stage 2: 构建
FROM aqtbrodh2awvkc.xuanyuan.run/node:20-alpine AS builder
WORKDIR /app
RUN npm install -g pnpm --registry=https://registry.npmmirror.com
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ .

# 【关键点】接收构建参数并注入环境变量，Next.js 构建时会读取
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN mkdir -p public
# 执行构建，此时 NEXT_PUBLIC_API_URL 会被硬编码进 .next 产物中
RUN pnpm build

# Stage 3: 生产运行
FROM aqtbrodh2awvkc.xuanyuan.run/node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

# 【关键点】在最终镜像中也保留此变量，方便 docker inspect 验证
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

RUN mkdir -p ./public
COPY --from=builder /app/public/ ./public/
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# 健康检查：尝试访问 localhost 首页
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

CMD ["node", "server.js"]