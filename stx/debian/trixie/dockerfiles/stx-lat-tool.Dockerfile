# Copyright (c) 2021 Wind River Systems, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

FROM debian:trixie
ARG os_mirror_url="http://"
ARG os_mirror_dist_path=""
ARG lat_mirror_url="https://mirror.starlingx.windriver.com/mirror/"
ARG lat_mirror_lat_path="lat-sdk/"
ARG lat_version="lat-sdk-20231206"
ARG max_retry_count=5
ARG retry_delay=60

MAINTAINER Chen Qi <Qi.Chen@windriver.com>

ARG LAT_BINARY_RESOURCE_PATH="${lat_mirror_url}${lat_mirror_lat_path}${lat_version}"

# Add retry and parallel download to apt config
RUN ( echo 'Acquire::Retries "3";'; \
      echo 'Acquire::Queue-Mode "access";'; \
      echo 'APT::Get::Max-Parallel-Downloads "3";' \
    ) > /etc/apt/apt.conf.d/99custom

# Update certificates via upsteam repos
RUN apt-get -y update && apt-get -y install --no-install-recommends ca-certificates && update-ca-certificates

# Temporarily disable the valid-until check.  Trixie's repos are not updating as quickly as they should while in pre-release state
RUN echo "Acquire::Check-Valid-Until "false";" > /etc/apt/apt.conf.d/99ignore-release-expiration

RUN echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian trixie contrib main non-free-firmware" > /etc/apt/sources.list && \
    echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian trixie-updates contrib main non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian trixie-backports contrib main non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian-security trixie-security contrib main non-free-firmware" >> /etc/apt/sources.list && \
    rm /etc/apt/sources.list.d/debian.sources

# pass --break-system-packages to pip
# https://salsa.debian.org/cpython-team/python3/-/blob/python3.11/debian/README.venv#L58
RUN echo "[global]" >> /etc/pip.conf && \
    echo "break-system-packages = true" >> /etc/pip.conf

# Install necessary packages
RUN apt-get -y update && apt-get --no-install-recommends -y install \
            bzip2 \
            coreutils \
            cpio \
            file \
            locales-all \
            openssh-client \
            procps \
            python3 \
            python3-pip \
            python3-yaml \
            rsync \
            tini \
            util-linux \
            vim \
            wget \
            xz-utils \
        && \
        apt-get clean && \
        mkdir -p /opt/LAT/SDK && \
        pip3 install pycryptodomex requests_toolbelt

# Packages for pre-patched iso creation support
RUN apt-get -y install \
            bubblewrap \
            debos \
            dosfstools \
            gir1.2-ostree-1.0 \
            git \
            isomd5sum \
            mmdebstrap \
            python3-apt \
            python3-gi \
            python3-gi-cairo \
            python3-systemd \
            reprepro \
            syslinux-utils \
            xfsprogs \
        && \
        apt-get clean && \
        rm -rf /var/lib/apt/lists/*

RUN \
    attempt=1 ; \
    while true ; do \
        if pip3 install git+https://opendev.org/starlingx/apt-ostree@master ; then \
            break ; \
        fi ; \
        if [ $attempt -ge ${max_retry_count} ] ; then \
            echo "ERROR: failed to install apt-ostree" >&2 ; \
            exit 1 ; \
        fi ; \
        attempt=`expr $attempt + 1` ; \
        echo "WARNING: failed to install apt-ostree" >&2 ; \
        echo "Sleeping ${retry_delay} second(s)" >&2 ; \
        sleep ${retry_delay} ; \
        echo "Retrying ($attempt/${max_retry_count})" >&2 ; \
    done

# Insert pubkey of the package repository
COPY stx/debian/trixie/toCOPY/builder/pubkey.rsa /opt/LAT/

# Prepare executables
COPY stx/debian/trixie/toCOPY/lat-tool/lat/ /opt/LAT/lat
# Download & install LAT SDK.
RUN echo "LAT_BINARY_RESOURCE_PATH = ${LAT_BINARY_RESOURCE_PATH}"
RUN wget --quiet ${LAT_BINARY_RESOURCE_PATH}/lat-sdk.sh --output-document=/opt/LAT/AppSDK.sh && \
    chmod +x /opt/LAT/AppSDK.sh && \
    /opt/LAT/AppSDK.sh -d /opt/LAT/SDK -y && \
    rm -f /opt/LAT/AppSDK.sh

# LAT Fix: Use Debian CDN address for geo-frendly servers
RUN sed -i 's/ftp.cn.debian.org/${os_mirror_url}${os_mirror_dist_path}deb.debian.org/g' /opt/LAT/SDK/sysroots/x86_64-wrlinuxsdk-linux/usr/lib/python3.10/site-packages/genimage/debian_constant.py

# LAT Fix: Align DEFAULT_INITRD_NAME with our custom names
RUN sed -i 's/debian-initramfs-ostree-image/starlingx-initramfs-ostree-image/g' /opt/LAT/SDK/sysroots/x86_64-wrlinuxsdk-linux/usr/lib/python3.10/site-packages/genimage/debian_constant.py

# LAT Fix: Align kernel with custom starlingx kernel
RUN sed -i 's/linux-image-amd64/linux-image-stx-amd64/g' /opt/LAT/SDK/sysroots/x86_64-wrlinuxsdk-linux/usr/lib/python3.10/site-packages/genimage/debian_constant.py

RUN sed -i 's/Wind River Linux Graphics development .* ostree/StarlingX ostree/g' /opt/LAT/SDK/sysroots/corei7-64-wrs-linux/boot/efi/EFI/BOOT/grub.cfg

# LAT Fix: Update for the Trixie version of debootstrap: https://salsa.debian.org/installer-team/debootstrap/-/tree/1.0.140?ref_type=tags
COPY stx/debian/trixie/toCOPY/lat-tool/lat/debootstrap/debootstrap /opt/LAT/SDK/sysroots/x86_64-wrlinuxsdk-linux/usr/bin/debootstrap
COPY stx/debian/trixie/toCOPY/lat-tool/lat/debootstrap/functions /opt/LAT/SDK/sysroots/x86_64-wrlinuxsdk-linux/usr/share/debootstrap/functions
COPY stx/debian/trixie/toCOPY/lat-tool/lat/debootstrap/scripts/debian-common /opt/LAT/SDK/sysroots/x86_64-wrlinuxsdk-linux/usr/share/debootstrap/scripts/debian-common

# Fix: Add gpgv package needed by proper functioning by apt
RUN sed -i 's/gpg,gpg-agent/gpg,gpgv,gpg-agent/g' /opt/LAT/SDK/sysroots/x86_64-wrlinuxsdk-linux/usr/lib/python3.10/site-packages/genimage/package_manager/deb/__init__.py

# Add vimrc
COPY stx/debian/trixie/toCOPY/common/vimrc.local /etc/vim/vimrc.local
RUN chmod 0644 /etc/vim/vimrc.local

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["ionice", "-c", "3", "nice", "-n", "15", "/opt/LAT/lat/latd"]
