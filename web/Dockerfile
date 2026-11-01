# Interfaz web (sesión 7). Node solo construye; nginx sin privilegios sirve los archivos
# estáticos y lleva /api/ y /health al servicio api (nginx.conf).
# docker-compose.yml le pasa el contexto «contrato» (docs/api) para la prueba que compara
# los catálogos de la interfaz con el OpenAPI. Fuera de Compose:
#   docker build --build-context contrato=docs/api web
FROM node:24.22.2-alpine3.24 AS dependencias

WORKDIR /web
COPY package.json package-lock.json .npmrc ./
RUN npm ci

# La imagen no se construye si falla una prueba.
FROM dependencias AS pruebas
COPY --from=contrato openapi-implementada.json /docs/api/openapi-implementada.json
COPY . .
RUN npm test

FROM pruebas AS construccion
RUN npm run build

# Corre como el usuario nginx (101) y escucha en el 8080.
FROM nginxinc/nginx-unprivileged:1.30.6-alpine3.24
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=construccion /web/dist /usr/share/nginx/html
EXPOSE 8080
