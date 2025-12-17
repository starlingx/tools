# syntax=docker/dockerfile:1.4
# Copyright (c) 2021,2025 Wind River Systems, Inc.
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

FROM debian:bullseye
ARG os_mirror_url="http://"
ARG os_mirror_dist_path=""
ARG lat_mirror_url="https://mirror.starlingx.windriver.com/mirror/"
ARG lat_mirror_lat_path="lat-sdk/"
ARG lat_version="lat-sdk-20231206"
ARG max_retry_count=5
ARG retry_delay=60

MAINTAINER Chen Qi <Qi.Chen@windriver.com>

ARG LAT_BINARY_RESOURCE_PATH="${lat_mirror_url}${lat_mirror_lat_path}${lat_version}"

# Add retry to apt config
RUN echo 'Acquire::Retries "3";' > /etc/apt/apt.conf.d/99custom

# Update certificates via upsteam repos
RUN apt-get -y update && apt-get -y install --no-install-recommends ca-certificates && update-ca-certificates

# Now point to the mirror for specific package builds
RUN echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian bullseye main" > /etc/apt/sources.list && \
    echo "deb ${os_mirror_url}${os_mirror_dist_path}security.debian.org/debian-security bullseye-security main" >> /etc/apt/sources.list && \
    echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian bullseye-updates main" >> /etc/apt/sources.list

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
COPY stx/debian/bullseye/toCOPY/builder/pubkey.rsa /opt/LAT/

# Prepare executables
COPY stx/debian/bullseye/toCOPY/lat-tool/lat/ /opt/LAT/lat
# Download & install LAT SDK.
# Try to use cached version from additional build context, fallback to wget
# Note: lat-cache is provided via --build-context lat-cache=<dir>
RUN echo "LAT_BINARY_RESOURCE_PATH = ${LAT_BINARY_RESOURCE_PATH}"
COPY --from=lat-cache lat-sdk.sh* /tmp/
RUN set -ex; \
    if [ -f /tmp/lat-sdk.sh ]; then \
        echo "Using cached LAT SDK from build context"; \
        mv /tmp/lat-sdk.sh /opt/LAT/AppSDK.sh; \
    else \
        echo "Downloading LAT SDK from: ${LAT_BINARY_RESOURCE_PATH}/lat-sdk.sh"; \
        wget --quiet "${LAT_BINARY_RESOURCE_PATH}/lat-sdk.sh" --output-document=/opt/LAT/AppSDK.sh; \
    fi; \
    chmod +x /opt/LAT/AppSDK.sh; \
    /opt/LAT/AppSDK.sh -d /opt/LAT/SDK -y; \
    rm -f /opt/LAT/AppSDK.sh /tmp/lat-sdk.sh*

# Fix: Use Debian CDN address for geo-frendly servers
RUN sed -i "s#ftp.cn.debian.org#${os_mirror_url}${os_mirror_dist_path}deb.debian.org#g" /opt/LAT/SDK/sysroots/x86_64-wrlinuxsdk-linux/usr/lib/python3.10/site-packages/genimage/debian_constant.py

# Fix: Align DEFAULT_INITRD_NAME with our custom names
RUN sed -i 's/debian-initramfs-ostree-image/starlingx-initramfs-ostree-image/g' /opt/LAT/SDK/sysroots/x86_64-wrlinuxsdk-linux/usr/lib/python3.10/site-packages/genimage/debian_constant.py

# Fix: Align kernel with custom starlingx kernel
RUN sed -i 's/linux-image-amd64/linux-image-stx-amd64/g' /opt/LAT/SDK/sysroots/x86_64-wrlinuxsdk-linux/usr/lib/python3.10/site-packages/genimage/debian_constant.py

RUN sed -i 's/Wind River Linux Graphics development .* ostree/StarlingX ostree/g' /opt/LAT/SDK/sysroots/corei7-64-wrs-linux/boot/efi/EFI/BOOT/grub.cfg

# Add vimrc
COPY stx/debian/bullseye/toCOPY/common/vimrc.local /etc/vim/vimrc.local
RUN chmod 0644 /etc/vim/vimrc.local

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["ionice", "-c", "3", "nice", "-n", "15", "/opt/LAT/lat/latd"]
