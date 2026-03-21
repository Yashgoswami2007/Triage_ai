FROM node:20-slim

WORKDIR /web

COPY package.json ./
RUN npm install --no-audit --no-fund

COPY . ./

RUN npm run build

ENV NODE_ENV=production
EXPOSE 3000

CMD ["npm", "run", "start"]

