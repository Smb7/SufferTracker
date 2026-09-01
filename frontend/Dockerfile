FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG MAP_APIKEY=
ENV MAP_APIKEY=$MAP_APIKEY
RUN node -e "require('fs').writeFileSync('src/environments/environment.ts', 'export const environment = { mapApiKey: ' + JSON.stringify(process.env.MAP_APIKEY || '') + ' };\n')"
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist/suffertracker-web/browser /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
