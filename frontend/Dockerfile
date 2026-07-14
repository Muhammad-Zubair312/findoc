# ── Stage 1: Dependencies ─────────────────────────────────────────────────────
FROM node:20-alpine AS base
WORKDIR /app

# ── Stage 2: Dev (unchanged — keep for local dev) ─────────────────────────────
FROM base AS dev
COPY package.json package-lock.json ./
RUN npm install
COPY . .
CMD ["npm", "run", "dev"]

# ── Stage 3: Production Build ──────────────────────────────────────────────────
FROM base AS prod

# Accept build-time env vars (NEXT_PUBLIC_* must be baked in at build time)
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_WS_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Install only production deps
COPY package.json package-lock.json ./
RUN npm ci --only=production && npm cache clean --force

# Copy source and build
COPY . .
RUN npm run build

EXPOSE 3000
# Uses Next.js built-in production server (fast, no hot reload)
CMD ["npm", "run", "start"]
