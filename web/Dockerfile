# Interfaz web (sesión 7). Node solo construye; nginx sin privilegios sirve los archivos
# estáticos y lleva /api/, /health, /docs y /openapi.json al servicio api (nginx.conf).
# docker-compose.yml le pasa el contexto «contrato» (docs/api) para la prueba que compara
# los catálogos de la interfaz con el OpenAPI. Fuera de Compose:
#   docker build --build-context contrato=docs/api web
# Railway no pasa ese contexto: usa web/Dockerfile.railway, que construye desde la raíz.
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
# nginx.conf es una plantilla: al arrancar, la imagen reemplaza solo las variables RADICA_
# y deja el resultado en /tmp, lo único escribible con el read_only de Compose. Los valores
# por defecto son los de la red de Compose; Railway define los suyos (web/Dockerfile.railway).
ENV RADICA_RESOLVER="127.0.0.11 ipv6=off" \
    RADICA_API_URL="http://api:8000" \
    NGINX_ENVSUBST_FILTER="^RADICA_" \
    NGINX_ENVSUBST_OUTPUT_DIR="/tmp"
COPY nginx.conf /etc/nginx/templates/radica.conf.template
RUN echo "include /tmp/radica.conf;" > /etc/nginx/conf.d/default.conf
COPY --from=construccion /web/dist /usr/share/nginx/html
EXPOSE 8080
