FROM node:22-slim

WORKDIR /app

COPY package.json ./
RUN npm install --no-audit --no-fund

COPY . .

EXPOSE 5173
# Dev server with the /api -> backend proxy (see vite.config.ts). Fine for the
# pilot's internal tool; swap for `npm run build` + a static server for prod.
CMD ["npm", "run", "dev"]
