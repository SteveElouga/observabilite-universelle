# syntax=docker/dockerfile:1
# mir-webapp — build Angular (Node) puis service statique + proxy par nginx. Image multi-stage.
FROM node:20-bookworm-slim AS build
WORKDIR /app
# package-lock.json optionnel (glob *) : npm ci si présent (build reproductible), sinon npm install.
COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
COPY . .
RUN npm run build

# Image nginx NON-ROOT (utilisateur 101, écoute sur 8080) : aucun privilège root requis
# (durcissement, bilan §sécurité ; remplace nginx:alpine qui tournait en root).
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Le builder Angular 18 (@angular-devkit/build-angular:application) écrit le bundle dans dist/browser.
COPY --from=build /app/dist/browser /usr/share/nginx/html
EXPOSE 8080
