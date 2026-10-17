FROM node:22-alpine

WORKDIR /app
ENV DOCKER=1

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
