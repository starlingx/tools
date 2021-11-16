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
    PATH=/opt/LAT/lat:$PATH

RUN echo "deb-src http://deb.debian.org/debian bullseye main" >> /etc/apt/sources.list && \
    echo "deb-src http://deb.debian.org/debian buster main" >> /etc/apt/sources.list && \
    echo "deb http://ftp.de.debian.org/debian bullseye main contrib" >> /etc/apt/sources.list

# Download required dependencies by mirror/build processes.
RUN     apt-get update && apt-get install --no-install-recommends -y \
        sudo \
        ssh \
        git \
        wget \
        curl \
        vim \
        rpm2cpio \
        cpio \
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
        pristine-tar \
        repo \
        libdistro-info-perl \
        debian-keyring \
        unzip \
        proxychains && \
        apt-get clean && \
        rm -rf /var/lib/apt/lists/* && \
        pip3 install \
        gitpython \
        requests \
        python-debian \
        pulpcore_client \
        pulp_deb_client \
        pulp_file_client \
        progressbar \
        git+https://github.com/masselstine/aptly-api-client.git && \
        sed -i '/^proxy_dns*/d' /etc/proxychains.conf && \
        sed -i 's/^socks4.*/socks5 127.0.0.1 8080/g' /etc/proxychains.conf && \
        ln -sf /usr/local/bin/stx/stx-localrc /root/localrc && \
        echo '. /usr/local/bin/finishSetup.sh' >> /root/.bashrc

# 3rd party apt repositories
# docker-cli
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg && \
    echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null && \
  apt-get update

COPY stx/toCOPY/lat-tool/lat /opt/LAT/lat
COPY stx/toCOPY/builder/finishSetup.sh /usr/local/bin
COPY stx/toCOPY/builder/userenv /root/
COPY stx/toCOPY/builder/buildrc /root/
