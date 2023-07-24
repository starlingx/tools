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

RUN echo "deb-src http://deb.debian.org/debian bullseye main" >> /etc/apt/sources.list
ARG DEBIAN_FRONTEND=noninteractive

# Update certificates
RUN apt-get -y update && apt-get -y install --no-install-recommends ca-certificates && update-ca-certificates

# Download required dependencies by mirror/build processes.
RUN     apt-get update && apt-get install --no-install-recommends -y \
        build-essential \
        live-build \
        pbuilder \
        debootstrap \
        devscripts \
        schroot \
        debmake \
        dpkg-dev \
        apt-utils \
        sbuild \
        osc \
        python3-pip \
        git \
        wget \
        curl \
        vim \
        sudo \
        emacs \
        tini \
        procps && \
        apt-get clean && \
        rm -rf /var/lib/apt/lists/* && \
        pip3 install Flask && \
        sudo sbuild-adduser root

# workaround for docker debootstrap bug
# https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=968927
RUN cd /tmp && \
    wget \
    http://snapshot.debian.org/archive/debian/20211128T160803Z/pool/main/d/debootstrap/debootstrap_1.0.126%2Bnmu1_all.deb && \
    dpkg -i debootstrap_1.0.126+nmu1_all.deb
RUN groupadd crontab

COPY stx/toCOPY/pkgbuilder/app.py /opt/
COPY stx/toCOPY/pkgbuilder/debbuilder.py /opt/
COPY stx/toCOPY/pkgbuilder/schrootspool.py /opt/
COPY stx/toCOPY/pkgbuilder/setup.sh /opt/
COPY stx/toCOPY/pkgbuilder/debbuilder.conf /etc/sbuild/sbuild.conf

COPY stx/toCOPY/pkgbuilder/pubkey.rsa /root
RUN apt-key add /root/pubkey.rsa && rm -f /root/pubkey.rsa

# Add vimrc
RUN mkdir -p /etc/vim
COPY stx/toCOPY/common/vimrc.local /etc/vim/vimrc.local
RUN chmod 0644 /etc/vim/vimrc.local

ENTRYPOINT ["/usr/bin/tini", "--"]
WORKDIR /opt
CMD ["python3", "app.py"]
