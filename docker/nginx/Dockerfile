FROM nginx:1.27-alpine

RUN rm /etc/nginx/conf.d/default.conf

COPY docker/nginx/nginx.conf /etc/nginx/nginx.conf
COPY docker/nginx/certs/ /etc/nginx/certs/
COPY frontend/dist /usr/share/nginx/html

EXPOSE 80 443
