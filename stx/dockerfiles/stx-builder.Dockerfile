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
# Copyright (C) 2021-2022 Wind River Systems,Inc.
#
FROM debian:bullseye

ARG STX_MIRROR_URL=https://mirror.starlingx.windriver.com/mirror

ENV container=docker \
    PATH=/opt/LAT/lat:$PATH

# Add retry to apt config
RUN echo 'Acquire::Retries "3";' > /etc/apt/apt.conf.d/99custom

# Update certificates
RUN apt-get -y update && apt-get -y install --no-install-recommends ca-certificates && update-ca-certificates

RUN echo "deb-src http://deb.debian.org/debian bullseye main" >> /etc/apt/sources.list && \
    echo "deb-src ${STX_MIRROR_URL}/debian/debian/deb.debian.org/debian buster main" >> /etc/apt/sources.list && \
    echo "deb http://deb.debian.org/debian bullseye contrib" >> /etc/apt/sources.list

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

# 3rd party apt repositories
# docker-cli
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg && \
    echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    apt-get update && \
    apt-get install --no-install-recommends -y docker-ce-cli

# Python modules
RUN pip3 --no-cache-dir install \
        gitpython \
        requests \
        python-debian \
        pulpcore_client \
        pulp_deb_client \
        pulp_file_client \
        progressbar \
        git+https://github.com/masselstine/aptly-api-client.git \
        click \
        lxml \
        pycryptodomex

# Misc files
RUN sed -i '/^proxy_dns*/d' /etc/proxychains.conf && \
    sed -i 's/^socks4.*/socks5 127.0.0.1 8080/g' /etc/proxychains.conf && \
    ln -sf /usr/local/bin/stx/stx-localrc /root/localrc && \
    echo '. /usr/local/bin/finishSetup.sh' >> /root/.bashrc

COPY stx/toCOPY/lat-tool/lat /opt/LAT/lat
COPY stx/toCOPY/builder/finishSetup.sh /usr/local/bin
COPY stx/toCOPY/builder/userenv /root/
COPY stx/toCOPY/builder/buildrc /root/

COPY stx/toCOPY/builder/pubkey.rsa /root
RUN apt-key add /root/pubkey.rsa && rm -f /root/pubkey.rsa

# Add vimrc
RUN mkdir -p /etc/vim
COPY stx/toCOPY/common/vimrc.local /etc/vim/vimrc.local
RUN chmod 0644 /etc/vim/vimrc.local

ENTRYPOINT ["ionice", "-c", "3", "nice", "-n", "15", "/usr/bin/tini", "-g", "--"]
CMD ["/bin/bash", "-i", "-c", "exec /bin/sleep infinity" ]
