#!/bin/sh

set -ex

# Update/replace config files provided in the image
\cp -f -v /configmap/nginx-default.conf /etc/nginx/conf.d/default.conf

# Call entrypoint script provided by the image
exec /docker-entrypoint.sh "$@"
