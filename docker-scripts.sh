#!/usr/bin/env bash
# This script is wrapping functionality for the docker image creation and usage.
# It is both the setup script as well as the container entry point.
# --
# When called with special arguments, it performs corresponding functionality.
# Otherwise, it just runs the arguments as a command (pass through).
# See https://docs.docker.com/develop/develop-images/dockerfile_best-practices/#entrypoint

if [ "$1" = 'setup' ]; then
    # called during image creation

    echo "Installing nginx..."
    printf '#!/bin/sh\nexit 0' > /usr/sbin/policy-rc.d
    apt-get update && apt-get --yes install nginx ssl-cert

    echo "Setting up nginx..."
    rm /etc/nginx/sites-enabled/default
    cp metador-tusd-nginx.conf /etc/nginx/conf.d/
    make-ssl-cert generate-default-snakeoil --force-overwrite

    echo "Installing tusd..."
    curl -sSL https://github.com/tus/tusd/releases/download/v1.6.0/tusd_linux_amd64.tar.gz -o tusd.tar.gz && tar xf tusd.tar.gz && mv tusd_linux_amd64/tusd /usr/local/bin

    echo "Building metador frontend..."
    cd frontend
    npm install
    cd ..

    echo "Building metador backend..."
    poetry config virtualenvs.in-project true
    poetry install --no-dev


elif [ "$1" = 'run' ]; then
    # called when the container is started

    # if user provides certificate, overwrite the snakeoil with it
    if [  -f "/mnt/cert.pem" ]; then
        cp /mnt/cert.pem /etc/ssl/certs/ssl-cert-snakeoil.pem
        cp /mnt/cert.key /etc/ssl/private/ssl-cert-snakeoil.key
    fi

    nginx &
    source .venv/bin/activate
    cd /mnt
    tusd -behind-proxy -hooks-http https://localhost/tusd-events &
    metador-cli run

else
    # run passed command and arguments
    exec "$@"
fi
