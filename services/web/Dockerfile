# syntax=docker/dockerfile:1
# Der Build laeuft nativ auf der Plattform des Builders (--platform=$BUILDPLATFORM),
# denn das Ergebnis sind statische Dateien und damit architekturunabhaengig.
# Nur die winzige nginx-Schicht wird fuer arm64 gebaut. Das spart in der CI den
# kompletten QEMU-Aufwand fuer "npm ci".

FROM --platform=$BUILDPLATFORM node:22-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .

# Zur Build-Zeit fest ins Bundle geschrieben, nicht zur Laufzeit gelesen.
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

# ---------------------------------------------------------------------------
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s \
    CMD wget -qO- http://localhost/ >/dev/null || exit 1
