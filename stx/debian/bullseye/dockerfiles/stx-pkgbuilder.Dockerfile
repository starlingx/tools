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
FROM debian:bullseye
ARG os_mirror_url="http://"
ARG os_mirror_dist_path=""

ARG DEBIAN_FRONTEND=noninteractive

# Add retry to apt config
RUN echo 'Acquire::Retries "3";' > /etc/apt/apt.conf.d/99custom

# Update certificates via upsteam repos
RUN apt-get -y update && apt-get -y install --no-install-recommends ca-certificates && update-ca-certificates

# Now point to the mirror for specific package builds
RUN echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian bullseye main" > /etc/apt/sources.list && \
    echo "deb ${os_mirror_url}${os_mirror_dist_path}security.debian.org/debian-security bullseye-security main" >> /etc/apt/sources.list && \
    echo "deb ${os_mirror_url}${os_mirror_dist_path}deb.debian.org/debian bullseye-updates main" >> /etc/apt/sources.list
#RUN echo "deb-src http://deb.debian.org/debian bullseye main" >> /etc/apt/sources.list

# Download required dependencies by mirror/build processes.
RUN     apt-get update && apt-get install --no-install-recommends -y \
            apt-utils \
            build-essential \
            coreutils \
            curl \
            debmake \
            debootstrap \
            devscripts \
            dpkg-dev \
            emacs \
            git \
            live-build \
            osc \
            pbuilder \
            procps \
            python3-fs \
            python3-pip \
            python3-psutil \
            sbuild \
            schroot \
            sudo \
            tini \
            util-linux \
            vim \
            wget \
        && \
        apt-get clean && \
        rm -rf /var/lib/apt/lists/* && \
        pip3 install Flask && \
        sudo sbuild-adduser root

# workaround for docker debootstrap bug
# https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=968927
RUN cd /tmp && \
    wget ${os_mirror_url}${os_mirror_dist_path}snapshot.debian.org/archive/debian/20220331T000000Z/pool/main/d/debootstrap/debootstrap_1.0.128%2Bnmu2%2Bdeb12u1_all.deb && \
    dpkg -i debootstrap_1.0.128+nmu2+deb12u1_all.deb
RUN groupadd crontab

COPY stx/debian/bullseye/toCOPY/pkgbuilder/app.py /opt/
COPY stx/debian/bullseye/toCOPY/pkgbuilder/debbuilder.py /opt/
COPY stx/debian/bullseye/toCOPY/pkgbuilder/schrootspool.py /opt/
COPY stx/debian/bullseye/toCOPY/pkgbuilder/utils.py /opt/
COPY stx/debian/bullseye/toCOPY/pkgbuilder/setup.sh /opt/
COPY stx/debian/bullseye/toCOPY/pkgbuilder/debbuilder.conf /etc/sbuild/sbuild.conf

COPY stx/debian/bullseye/toCOPY/pkgbuilder/pubkey.rsa /opt/
RUN apt-key add /opt/pubkey.rsa

# Add vimrc
RUN mkdir -p /etc/vim
COPY stx/debian/bullseye/toCOPY/common/vimrc.local /etc/vim/vimrc.local
RUN chmod 0644 /etc/vim/vimrc.local

ENTRYPOINT ["/usr/bin/tini", "--"]
WORKDIR /opt
CMD [ "ionice", "-c", "3", "nice", "-n", "15", "python3", "app.py"]
