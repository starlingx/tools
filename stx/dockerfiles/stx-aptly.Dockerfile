# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Copyright (C) 2021-2022 Wind River Systems,Inc.
#
FROM golang:1.17.5-bullseye AS builder
LABEL stage=builder


# Build Aptly with mirror API support
RUN mkdir -p $GOPATH/src/github.com/aptly-dev/aptly && \
    git clone https://github.com/masselstine/aptly $GOPATH/src/github.com/aptly-dev/aptly && \
    cd $GOPATH/src/github.com/aptly-dev/aptly && \
    go mod init && go mod download && go mod vendor && go mod verify && \
    export TRAVIS_TAG="StarlingX_Master_v1.0.0" && \
    make install && \
    cd $GOPATH && \
    curl -O https://nginx.org/keys/nginx_signing.key && apt-key add ./nginx_signing.key

# Build our actual container
FROM debian:bullseye

MAINTAINER mark.asselstine@windriver.com

COPY --from=builder /go/nginx_signing.key nginx_signing.key

# Update certificates
RUN apt-get -q -y update && apt-get -y install --no-install-recommends ca-certificates && update-ca-certificates

# Add Nginx repository and install required packages
RUN apt-get -q update && apt-get -y install gnupg2 && \
    echo "deb http://nginx.org/packages/debian/ bullseye nginx" > /etc/apt/sources.list.d/nginx.list && \
    apt-key add ./nginx_signing.key && \
    apt-get -q update && apt-get -y install \
                                            aptly \
                                            supervisor \
                                            gettext-base \
                                            nginx && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /usr/share/man && \
    rm -rf /usr/share/doc && \
    rm -rf /usr/share/grub2 && \
    rm -rf /usr/share/texmf/fonts && \
    rm -rf /usr/share/texmf/doc

# Copy our  Aptly build and configure Aptly
COPY --from=builder /go/bin/aptly /usr/bin/aptly
COPY stx/toCOPY/aptly/aptly.conf /etc/aptly.conf
COPY stx/toCOPY/aptly/supervisord.aptly.conf /etc/supervisor/conf.d/aptly.conf

# Configure Nginx
COPY stx/toCOPY/aptly/nginx.conf.template /etc/nginx/nginx.conf.template
COPY stx/toCOPY/aptly/supervisord.nginx.conf /etc/supervisor/conf.d/nginx.conf
COPY stx/toCOPY/aptly/nginx.conf /etc/nginx/nginx.conf
COPY stx/toCOPY/aptly/nginx.logrotate /etc/logrotate.d/nginx

# Bind mount locations
VOLUME [ "/var/aptly" ]

# Ports
EXPOSE 80 8080

# Import private key for repo signatures
COPY stx/toCOPY/aptly/privkey.rsa /root
RUN gpg --import --pinentry-mode loopback --batch --passphrase starlingx /root/privkey.rsa && \
    rm -f /root/privkey.rsa

# Add vimrc
RUN mkdir -p /etc/vim
COPY stx/toCOPY/common/vimrc.local /etc/vim/vimrc.local
RUN chmod 0644 /etc/vim/vimrc.local

# Configure startup
COPY stx/toCOPY/aptly/entrypoint.sh /bin/entrypoint.sh
ENTRYPOINT [ "/bin/entrypoint.sh" ]
