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

ARG LAT_BINARY_RESOURCE_PATH=http://mirror.starlingx.cengn.ca/mirror/lat-sdk/lat-sdk-20211013

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

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/opt/LAT/lat/latd"]
