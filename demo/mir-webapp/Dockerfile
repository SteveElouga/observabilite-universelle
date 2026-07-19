# syntax=docker/dockerfile:1
# mir-webapp — build Angular (Node) puis service statique + proxy par nginx. Image multi-stage.
FROM node:20-bookworm-slim AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Le builder Angular 18 (@angular-devkit/build-angular:application) écrit le bundle dans dist/browser.
COPY --from=build /app/dist/browser /usr/share/nginx/html
EXPOSE 80
