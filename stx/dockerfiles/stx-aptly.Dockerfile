#
# MIT License
#
# Copyright (c) 2021 Mark Asselstine
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

FROM golang:1.16.5-buster AS builder
LABEL stage=builder


# Build Aptly with mirror API support
RUN mkdir -p $GOPATH/src/github.com/aptly-dev/aptly && \
    git clone https://github.com/masselstine/aptly $GOPATH/src/github.com/aptly-dev/aptly && \
    cd $GOPATH/src/github.com/aptly-dev/aptly && \
    go mod init && go mod download && go mod vendor && go mod verify && \
    make install && \
    cd $GOPATH && \
    curl -O https://nginx.org/keys/nginx_signing.key && apt-key add ./nginx_signing.key

# Build our actual container
FROM debian:buster

MAINTAINER mark.asselstine@windriver.com

COPY --from=builder /go/nginx_signing.key nginx_signing.key

# Add Nginx repository and install required packages
RUN apt-get -q update && apt-get -y install gnupg2 && \
    echo "deb http://nginx.org/packages/debian/ buster nginx" > /etc/apt/sources.list.d/nginx.list && \
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

# Bind mount locations
VOLUME [ "/var/aptly" ]

# Ports
EXPOSE 80 8080

# Configure startup
COPY stx/toCOPY/aptly/entrypoint.sh /bin/entrypoint.sh
ENTRYPOINT [ "/bin/entrypoint.sh" ]
