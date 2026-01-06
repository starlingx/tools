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

ARG STX_MIRROR_URL=https://mirror.starlingx.windriver.com/mirror
ARG APT_CHROOT_DIR=/usr/local/apt-chroot

ENV container=docker \
    PATH=/opt/LAT/lat:$PATH

# Add retry and parallel download to apt config
RUN ( echo 'Acquire::Retries "3";'; \
      echo 'Acquire::Queue-Mode "access";'; \
      echo 'APT::Get::Max-Parallel-Downloads "3";' \
    ) > /etc/apt/apt.conf.d/99custom

# Update certificates via upsteam repos
RUN apt-get -y update && apt-get -y install --no-install-recommends ca-certificates && update-ca-certificates

# Temporarily disable the valid-until check.  Trixie's repos are not updating as quickly as they should while in pre-release state
RUN echo "Acquire::Check-Valid-Until "false";" > /etc/apt/apt.conf.d/99ignore-release-expiration

RUN echo "deb ${os_mirror_url}${os_mirror_dist_path}snapshot.debian.org/archive/debian/20250902T143411Z trixie contrib main non-free" > /etc/apt/sources.list && \
    echo "deb ${os_mirror_url}${os_mirror_dist_path}snapshot.debian.org/archive/debian/20250902T143411Z trixie-updates contrib main non-free" >> /etc/apt/sources.list && \
    echo "deb ${os_mirror_url}${os_mirror_dist_path}snapshot.debian.org/archive/debian/20250902T143411Z trixie-backports contrib main non-free" >> /etc/apt/sources.list && \
    echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian trixie non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian trixie-updates non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian trixie-backports non-free-firmware" >> /etc/apt/sources.list && \
    rm -rf /etc/apt/sources.list.d/debian.sources /var/lib/apt/lists/*

# RUN echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian trixie contrib main non-free-firmware" > /etc/apt/sources.list && \
#     echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian trixie-updates contrib main non-free-firmware" >> /etc/apt/sources.list && \
#     echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian trixie-backports contrib main non-free-firmware" >> /etc/apt/sources.list && \
#     echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian-security trixie-security contrib main non-free-firmware" >> /etc/apt/sources.list && \
#     rm /etc/apt/sources.list.d/debian.sources

RUN cat /etc/apt/sources.list

# pass --break-system-packages to pip
# https://salsa.debian.org/cpython-team/python3/-/blob/python3.11/debian/README.venv#L58
RUN echo "[global]" >> /etc/pip.conf && \
    echo "break-system-packages = true" >> /etc/pip.conf

# Download required dependencies by mirror/build processes.
RUN apt-get update && apt-get install --no-install-recommends -y \
        binutils \
        bzip2 \
        coreutils \
        cpio \
        cpp \
        curl \
        debian-keyring \
        debmake \
        debootstrap \
        dnsutils \
        docker-cli \
        dpkg \
        dpkg-dev \
        fakeroot \
        file \
        git \
        git-buildpackage \
        gnupg \
        isomd5sum \
        less \
        libdistro-info-perl \
        locales-all \
        mkisofs \
        pristine-tar \
        proot \
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
        tar \
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
    click \
    lxml \
    pycryptodomex

RUN pip3 --no-cache-dir install \
    git+https://github.com/slittle1/aptly-api-client.git

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

# setup chroot for apt queries
RUN mkdir -p $APT_CHROOT_DIR
RUN debootstrap --variant=minbase --include=ca-certificates,debian-archive-keyring,gnupg,procps --foreign trixie $APT_CHROOT_DIR http://deb.debian.org/debian
RUN chroot $APT_CHROOT_DIR debootstrap/debootstrap --second-stage
RUN rm -rf $APT_CHROOT_DIR/etc/apt/sources.list $APT_CHROOT_DIR/etc/apt/sources.list.d && \
    rm -rf $APT_CHROOT_DIR/etc/apt/apt.conf     $APT_CHROOT_DIR/etc/apt/apt.conf.d && \
    rm -rf $APT_CHROOT_DIR/var/lib/apt/lists/partial  $APT_CHROOT_DIR/var/cache/apt/archives/partial

ENTRYPOINT ["ionice", "-c", "3", "nice", "-n", "15", "/usr/bin/tini", "-g", "--"]
CMD ["/bin/bash", "-i", "-c", "exec /bin/sleep infinity" ]
