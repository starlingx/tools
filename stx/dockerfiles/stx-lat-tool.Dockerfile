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

FROM debian:bullseye

MAINTAINER Chen Qi <Qi.Chen@windriver.com>

ARG LAT_BINARY_RESOURCE_PATH=https://mirror.starlingx.windriver.com/mirror/lat-sdk/lat-sdk-20230510

# Update certificates
RUN apt-get -y update && apt-get -y install --no-install-recommends ca-certificates && update-ca-certificates

# Install necessary packages
RUN apt-get -y update && apt-get --no-install-recommends -y install \
        openssh-client \
        python3 \
        python3-pip \
        xz-utils \
        file \
        bzip2 \
        procps \
        tini \
        wget \
        locales-all \
        python3-yaml \
        rsync \
        cpio \
        vim \
        && \
        apt-get clean && \
        rm -rf /var/lib/apt/lists/* && \
        mkdir -p /opt/LAT/SDK && \
        pip3 install pycryptodomex requests_toolbelt

# Insert pubkey of the package repository
COPY stx/toCOPY/builder/pubkey.rsa /opt/LAT/

# Prepare executables
COPY stx/toCOPY/lat-tool/lat/ /opt/LAT/lat
# Download & install LAT SDK.
RUN wget --quiet ${LAT_BINARY_RESOURCE_PATH}/lat-sdk.sh --output-document=/opt/LAT/AppSDK.sh && \
    chmod +x /opt/LAT/AppSDK.sh && \
    /opt/LAT/AppSDK.sh -d /opt/LAT/SDK -y && \
    rm -f /opt/LAT/AppSDK.sh

# Fix: Use Debian CDN address for geo-frendly servers
RUN sed -i 's/ftp.cn.debian.org/deb.debian.org/g' /opt/LAT/SDK/sysroots/x86_64-wrlinuxsdk-linux/usr/lib/python3.10/site-packages/genimage/debian_constant.py

# Fix: Align DEFAULT_INITRD_NAME with our custom names
RUN sed -i 's/debian-initramfs-ostree-image/starlingx-initramfs-ostree-image/g' /opt/LAT/SDK/sysroots/x86_64-wrlinuxsdk-linux/usr/lib/python3.10/site-packages/genimage/debian_constant.py

# Fix: Align kernel with custom starlingx kernel
RUN sed -i 's/linux-image-amd64/linux-image-stx-amd64/g' /opt/LAT/SDK/sysroots/x86_64-wrlinuxsdk-linux/usr/lib/python3.10/site-packages/genimage/debian_constant.py

RUN sed -i 's/Wind River Linux Graphics development .* ostree/StarlingX ostree/g' /opt/LAT/SDK/sysroots/corei7-64-wrs-linux/boot/efi/EFI/BOOT/grub.cfg

# Add vimrc
COPY stx/toCOPY/common/vimrc.local /etc/vim/vimrc.local
RUN chmod 0644 /etc/vim/vimrc.local

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/opt/LAT/lat/latd"]
