FROM node:22-alpine
WORKDIR /app
COPY package.json server.mjs ./
COPY lib ./lib
COPY public ./public
ENV HOST=0.0.0.0
ENV PORT=3210
USER node
EXPOSE 3210
CMD ["node", "server.mjs"]
