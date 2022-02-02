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

ARG LAT_BINARY_RESOURCE_PATH=http://mirror.starlingx.cengn.ca/mirror/lat-sdk/lat-sdk-20211216

# Install necessary packages
RUN apt-get -y update && apt-get --no-install-recommends -y install \
        python3 \
        xz-utils \
        file \
        bzip2 \
        procps \
        tini \
        locales-all \
        python3-yaml && \
        apt-get clean && \
        rm -rf /var/lib/apt/lists/* && \
        mkdir -p /opt/LAT/SDK

# Prepare executables
COPY stx/toCOPY/lat-tool/lat/ /opt/LAT/lat
# Prepare LAT SDK.
ADD ${LAT_BINARY_RESOURCE_PATH}/lat-sdk.sh /opt/LAT/AppSDK.sh
RUN chmod +x /opt/LAT/AppSDK.sh
RUN /opt/LAT/AppSDK.sh -d /opt/LAT/SDK -y

# Workaround for using minbase variant for debootstrap
# See https://bugs.launchpad.net/starlingx/+bug/1959607
RUN sed -i -e 's#--no-check-gpg#--variant=minbase --no-check-gpg#g' \
  /opt/LAT/SDK/sysroots/x86_64-wrlinuxsdk-linux/usr/lib/python3.10/site-packages/genimage/package_manager/deb/__init__.py

# Fix: Use Debian CDN address for geo-frendly servers
RUN sed -i 's/ftp.cn.debian.org/deb.debian.org/g' /opt/LAT/SDK/sysroots/x86_64-wrlinuxsdk-linux/usr/lib/python3.10/site-packages/genimage/debian_constant.py

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/opt/LAT/lat/latd"]
