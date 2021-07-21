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
# Copyright (C) 2021 Wind River Systems,Inc.
#
FROM debian:bullseye

ENV container=docker \
    MYUNAME=builder \
    PROJECT=stx \
    PATH=/opt/LAT/lat:$PATH
ARG MYUID=1000

RUN echo "deb-src http://deb.debian.org/debian bullseye main" >> /etc/apt/sources.list
RUN echo "deb-src http://deb.debian.org/debian buster main" >> /etc/apt/sources.list

# Download required dependencies by mirror/build processes.
RUN     apt-get update && apt-get install --no-install-recommends -y \
        sudo \
        ssh \
        git \
        wget \
        curl \
        vim \
        python3 \
        python3-yaml \
        python3-pip \
        xz-utils \
        file \
        bzip2 \
        dnsutils \
        locales-all \
        python3-apt \
        dpkg-dev \
        git-buildpackage \
        fakeroot \
        proxychains && \
        apt-get clean && \
        rm -rf /var/lib/apt/lists/* && \
        pip3 install \
        git \
        requests \
        python-debian \
        pulpcore_client \
        pulp_deb_client \
        pulp_file_client \
        progressbar \
        git+git://github.com/masselstine/aptly-api-client.git && \
        groupadd -g 751 cgts && \
        useradd -r -u $MYUID -g cgts -m $MYUNAME && \
        sed -i '/^proxy_dns*/d' /etc/proxychains.conf && \
        sed -i 's/^socks4.*/socks5 127.0.0.1 8080/g' /etc/proxychains.conf && \
        chown $MYUNAME /home/$MYUNAME && \
        echo "$MYUNAME ALL=(ALL:ALL) NOPASSWD:ALL" >> /etc/sudoers

COPY stx/toCOPY/builder/buildrc /home/$MYUNAME/
USER $MYUNAME
