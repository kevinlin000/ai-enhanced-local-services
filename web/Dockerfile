# Build context 必須是 repo 根目錄（copy-taxonomy 需要 ../shared/taxonomy.json）：
#   docker build -f web/Dockerfile -t bytebites-web .
FROM node:22-alpine AS build
# pnpm 11 對未核准 build scripts 直接 fail（ERR_PNPM_IGNORED_BUILDS 行為變更），釘 10.x
RUN corepack enable && corepack prepare pnpm@10.14.0 --activate
WORKDIR /repo
COPY shared ./shared
COPY web ./web
WORKDIR /repo/web
RUN pnpm install --frozen-lockfile
# Next rewrites 的 proxy 目標在 build 時決定（next.config.ts 讀 env），
# 預設對準 compose 服務名；本機測試可用 --build-arg 覆蓋
ARG JAVA_API_PROXY_TARGET=http://java:8081
ARG AI_API_PROXY_TARGET=http://ai:8000
ENV JAVA_API_PROXY_TARGET=$JAVA_API_PROXY_TARGET AI_API_PROXY_TARGET=$AI_API_PROXY_TARGET
RUN pnpm build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3000 \
    JAVA_API_PROXY_TARGET=http://java:8081 AI_API_PROXY_TARGET=http://ai:8000
# standalone 已含裁剪過的 node_modules 與 server.js（於輸出根目錄）
COPY --from=build /repo/web/.next/standalone ./
COPY --from=build /repo/web/.next/static ./.next/static
COPY --from=build /repo/web/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
