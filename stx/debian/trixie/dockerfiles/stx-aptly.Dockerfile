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
# Copyright (C) 2021-2022,2025 Wind River Systems,Inc.
#

# Build our actual container
FROM debian:trixie
ARG os_mirror_url="http://"
ARG os_mirror_dist_path=""

# Add retry to apt config
RUN echo 'Acquire::Retries "3";' > /etc/apt/apt.conf.d/99custom

# Update certificates
RUN apt-get -q -y update && apt-get -y install --no-install-recommends curl ca-certificates && update-ca-certificates

RUN echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian trixie contrib main non-free-firmware" > /etc/apt/sources.list && \
    echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian trixie-updates contrib main non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian trixie-backports contrib main non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian-security trixie-security contrib main non-free-firmware" >> /etc/apt/sources.list && \
    rm /etc/apt/sources.list.d/debian.sources

RUN curl -O https://nginx.org/keys/nginx_signing.key

# Add Nginx repository and install required packages
#   Currently there is no "testing" repo for this so use the debian stable release
#   directly here. Change to a trixie package once trixie moves to the stable branch
RUN apt-get -q update && apt-get -y install gnupg2 gpg-wks-server && \
    echo "deb [signed-by=/etc/apt/keyrings/nginx_signing.gpg] http://nginx.org/packages/debian/ bookworm nginx" > /etc/apt/sources.list.d/nginx.list && \
    gpg --no-default-keyring --keyring ./temp-keyring.gpg --import ./nginx_signing.key && \
    gpg --no-default-keyring --keyring ./temp-keyring.gpg --export --output nginx_signing.gpg && \
    rm -f temp-keyring.gpg temp-keyring.gpg~ && \
    mkdir -p /etc/apt/keyrings && chmod 0775 /etc/apt/keyrings && \
    mv nginx_signing.gpg /etc/apt/keyrings && \
    groupadd --system --gid 201 nginx && \
    useradd --system --gid nginx --no-create-home --home /nonexistent --comment "nginx user" --shell /bin/false --uid 201 nginx && \
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

# Configure Aptly
COPY stx/debian/trixie/toCOPY/aptly/aptly.conf /etc/aptly.conf
COPY stx/debian/trixie/toCOPY/aptly/supervisord.aptly.conf /etc/supervisor/conf.d/aptly.conf

# Configure Nginx
COPY stx/debian/trixie/toCOPY/aptly/nginx.conf.template /etc/nginx/nginx.conf.template
COPY stx/debian/trixie/toCOPY/aptly/supervisord.nginx.conf /etc/supervisor/conf.d/nginx.conf
COPY stx/debian/trixie/toCOPY/aptly/nginx.conf /etc/nginx/nginx.conf
COPY stx/debian/trixie/toCOPY/aptly/nginx.logrotate /etc/logrotate.d/nginx

# Bind mount locations
VOLUME [ "/var/aptly" ]

# Ports
EXPOSE 80 8080

# Import private key for repo signatures
COPY stx/debian/trixie/toCOPY/aptly/privkey.rsa /root
RUN gpg --import --pinentry-mode loopback --batch --passphrase starlingx /root/privkey.rsa && \
    rm -f /root/privkey.rsa

# Add vimrc
RUN mkdir -p /etc/vim
COPY stx/debian/trixie/toCOPY/common/vimrc.local /etc/vim/vimrc.local
RUN chmod 0644 /etc/vim/vimrc.local

# Configure startup
COPY stx/debian/trixie/toCOPY/aptly/entrypoint.sh /bin/entrypoint.sh
ENTRYPOINT [ "ionice", "-c", "3", "nice", "-n", "15", "/bin/entrypoint.sh" ]
