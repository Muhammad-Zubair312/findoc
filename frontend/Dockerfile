# ── Stage 1: Base ────────────────────────────────────────────────────────────
FROM node:20-alpine AS base
WORKDIR /app

# ── Stage 2: Dev (hot reload — for development only) ─────────────────────────
FROM base AS dev
COPY package.json package-lock.json ./
RUN npm install
COPY . .
CMD ["npm", "run", "dev"]

# ── Stage 3: Production Build (fast — for demo recording) ────────────────────
FROM base AS prod

# NEXT_PUBLIC_* vars MUST be baked in at build time (not runtime)
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_WS_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Install ALL deps including devDeps (needed for TypeScript/Tailwind build)
COPY package.json package-lock.json ./
RUN npm install && npm cache clean --force

# Copy source and build
COPY . .
RUN npm run build

EXPOSE 3000
# Production server — instant page loads, no hot reload overhead
CMD ["npm", "run", "start"]
