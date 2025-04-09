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
# Copyright (C) 2021-2022.2025 Wind River Systems,Inc.
#
FROM debian:trixie
ARG os_mirror_url="http://"
ARG os_mirror_dist_path=""

ENV container=docker \
    PATH=/opt/LAT/lat:$PATH

RUN echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian trixie contrib main non-free-firmware" > /etc/apt/sources.list && \
    echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian trixie-updates contrib main non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian trixie-backports contrib main non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian-security trixie-security contrib main non-free-firmware" >> /etc/apt/sources.list && \
    rm /etc/apt/sources.list.d/debian.sources

# pass --break-system-packages to pip
# https://salsa.debian.org/cpython-team/python3/-/blob/python3.11/debian/README.venv#L58
RUN echo "[global]" >> /etc/pip.conf && \
    echo "break-system-packages = true" >> /etc/pip.conf

# Add retry to apt config
RUN echo 'Acquire::Retries "3";' > /etc/apt/apt.conf.d/99custom

# Update certificates via upsteam repos
RUN apt-get -y update && apt-get -y install --no-install-recommends ca-certificates && update-ca-certificates

# Download required dependencies by mirror/build processes.
RUN apt-get update && apt-get install --no-install-recommends -y \
        bzip2 \
        coreutils \
        cpio \
        cpp \
        curl \
        debian-keyring \
        debmake \
        dnsutils \
        docker-cli \
        dpkg-dev \
        fakeroot \
        file \
        git \
        git-buildpackage \
        isomd5sum \
        less \
        libdistro-info-perl \
        locales-all \
        mkisofs \
        pristine-tar \
        proxychains \
        python3 \
        python3-apt \
        python3-pip \
        python3-ruamel.yaml \
        python3-yaml \
        repo \
        rpm2cpio \
        ssh \
        sudo \
        syslinux-utils \
        tini \
        unzip \
        util-linux \
        vim \
        wget \
        xz-utils \
        && \
        apt-get clean && \
        rm -rf /var/lib/apt/lists/*

# Python modules
RUN pip3 --no-cache-dir install \
    gitpython \
    requests \
    python-debian \
    pulpcore_client \
    pulp_deb_client \
    pulp_file_client \
    progressbar \
    git+https://github.com/rchurch-wrs/aptly-api-client.git \
    click \
    lxml \
    pycryptodomex

# Misc files
RUN sed -i '/^proxy_dns*/d' /etc/proxychains.conf && \
    sed -i 's/^socks4.*/socks5 127.0.0.1 8080/g' /etc/proxychains.conf && \
    ln -sf /usr/local/bin/stx/stx-localrc /root/localrc && \
    echo '. /usr/local/bin/finishSetup.sh' >> /root/.bashrc

COPY stx/debian/trixie/toCOPY/lat-tool/lat /opt/LAT/lat
COPY stx/debian/trixie/toCOPY/builder/finishSetup.sh /usr/local/bin
COPY stx/debian/trixie/toCOPY/builder/userenv /root/
COPY stx/debian/trixie/toCOPY/builder/buildrc /root/

COPY stx/debian/trixie/toCOPY/builder/pubkey.rsa /root
RUN gpg --no-default-keyring --keyring ./temp-keyring.gpg --import /root/pubkey.rsa && \
    gpg --no-default-keyring --keyring ./temp-keyring.gpg --export --output aptly_pubkey.gpg && \
    rm -f temp-keyring.gpg temp-keyring.gpg~ && \
    mv aptly_pubkey.gpg /etc/apt/trusted.gpg.d/

# Add vimrc
RUN mkdir -p /etc/vim
COPY stx/debian/trixie/toCOPY/common/vimrc.local /etc/vim/vimrc.local
RUN chmod 0644 /etc/vim/vimrc.local

ENTRYPOINT ["ionice", "-c", "3", "nice", "-n", "15", "/usr/bin/tini", "-g", "--"]
CMD ["/bin/bash", "-i", "-c", "exec /bin/sleep infinity" ]
