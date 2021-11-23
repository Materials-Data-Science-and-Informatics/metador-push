FROM nikolaik/python-nodejs:python3.9-nodejs16

# Copy app
COPY . /app
WORKDIR /app
ARG DEBIAN_FRONTEND=noninteractive
RUN ./docker-scripts.sh setup

ENTRYPOINT ["/app/docker-scripts.sh"]
CMD ["run"]
