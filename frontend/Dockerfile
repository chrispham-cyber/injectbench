# Frontend image: the Next.js dashboard (production build).
# Build context is ./frontend (see docker-compose.yml).
FROM node:20-slim

WORKDIR /app

# Install deps from the lockfile first (cached unless the lockfile changes).
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start"]
