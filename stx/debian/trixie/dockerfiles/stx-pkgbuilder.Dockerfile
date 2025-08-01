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
FROM debian:trixie
ARG os_mirror_url="http://"
ARG os_mirror_dist_path=""

ARG DEBIAN_FRONTEND=noninteractive

# Add retry to apt config
RUN echo 'Acquire::Retries "3";' > /etc/apt/apt.conf.d/99custom

# Update certificates via upsteam repos
RUN apt-get -y update && apt-get -y install --no-install-recommends ca-certificates && update-ca-certificates

RUN echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian trixie contrib main non-free-firmware" > /etc/apt/sources.list && \
    echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian trixie-updates contrib main non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian trixie-backports contrib main non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian-security trixie-security contrib main non-free-firmware" >> /etc/apt/sources.list && \
    rm /etc/apt/sources.list.d/debian.sources

# pass --break-system-packages to pip
# https://salsa.debian.org/cpython-team/python3/-/blob/python3.11/debian/README.venv#L58
RUN echo "[global]" >> /etc/pip.conf && \
    echo "break-system-packages = true" >> /etc/pip.conf

# Download required dependencies by mirror/build processes.
RUN     apt-get update && apt-get install --no-install-recommends -y \
            apt-utils \
            build-essential \
            coreutils \
            curl \
            debmake \
            debootstrap \
            devscripts \
            dpkg-dev \
            emacs \
            git \
            live-build \
            osc \
            pbuilder \
            procps \
            python3-fs \
            python3-pip \
            python3-psutil \
            sbuild \
            schroot \
            sudo \
            tini \
            util-linux \
            vim \
            wget \
        && \
        apt-get clean && \
        rm -rf /var/lib/apt/lists/* && \
        pip3 install Flask && \
        sudo sbuild-adduser root

RUN groupadd crontab

COPY stx/debian/trixie/toCOPY/pkgbuilder/app.py /opt/
COPY stx/debian/trixie/toCOPY/pkgbuilder/debbuilder.py /opt/
COPY stx/debian/trixie/toCOPY/pkgbuilder/schrootspool.py /opt/
COPY stx/debian/trixie/toCOPY/pkgbuilder/utils.py /opt/
COPY stx/debian/trixie/toCOPY/pkgbuilder/setup.sh /opt/
COPY stx/debian/trixie/toCOPY/pkgbuilder/debbuilder.conf /etc/sbuild/sbuild.conf

COPY stx/debian/trixie/toCOPY/pkgbuilder/pubkey.rsa /opt/
RUN gpg --no-default-keyring --keyring ./temp-keyring.gpg --import /opt/pubkey.rsa && \
    gpg --no-default-keyring --keyring ./temp-keyring.gpg --export --output aptly_pubkey.gpg && \
    rm temp-keyring.gpg && \
    mv aptly_pubkey.gpg /etc/apt/trusted.gpg.d/

# Add vimrc
RUN mkdir -p /etc/vim
COPY stx/debian/trixie/toCOPY/common/vimrc.local /etc/vim/vimrc.local
RUN chmod 0644 /etc/vim/vimrc.local

ENTRYPOINT ["/usr/bin/tini", "--"]
WORKDIR /opt
CMD [ "ionice", "-c", "3", "nice", "-n", "15", "python3", "app.py"]
