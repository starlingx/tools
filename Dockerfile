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
# Copyright (C) 2019 Intel Corporation
#

FROM centos:7.8.2003

# Proxy configuration
#ENV http_proxy  "http://your.actual_http_proxy.com:your_port"
#ENV https_proxy "https://your.actual_https_proxy.com:your_port"
#ENV ftp_proxy   "http://your.actual_ftp_proxy.com:your_port"

#RUN echo "proxy=$http_proxy" >> /etc/yum.conf && \
#    echo -e "export http_proxy=$http_proxy\nexport https_proxy=$https_proxy\n\
#export ftp_proxy=$ftp_proxy" >> /root/.bashrc

# username you will docker exec into the container as.
# It should NOT be your host username so you can easily tell
# if you are in our out of the container.
ARG MYUNAME=builder
ARG MYUID=1000
# CentOS & EPEL URLs that match the base image
# Override these with --build-arg if you have a mirror
ARG CENTOS_7_8_URL=https://vault.centos.org/centos/7.8.2003
ARG CENTOS_7_9_URL=http://mirror.centos.org/centos-7/7.9.2009
ARG EPEL_7_8_URL=https://archives.fedoraproject.org/pub/archive/epel/7.2020-04-20
ARG MY_EMAIL=

ENV container=docker

# Lock down centos & epel repos
RUN rm -f /etc/yum.repos.d/*
COPY toCOPY/yum.repos.d/*.repo /etc/yum.repos.d/
COPY centos-mirror-tools/rpm-gpg-keys/RPM-GPG-KEY-EPEL-7 /etc/pki/rpm-gpg/
RUN rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY* && \
    echo "http_caching=packages" >> /etc/yum.conf && \
    echo "skip_missing_names_on_install=0" >>/etc/yum.conf && \
    # yum variables must be in lower case ; \
    echo "$CENTOS_7_8_URL" >/etc/yum/vars/centos_7_8_url && \
    echo "$EPEL_7_8_URL" >/etc/yum/vars/epel_7_8_url && \
    echo "$CENTOS_7_9_URL" >/etc/yum/vars/centos_7_9_url && \
    # disable fastestmirror plugin because we are not using mirrors ; \
    # FIXME: use a mirrorlist URL for centos/vault/epel archives. I couldn't find one.
    sed -i 's/enabled=1/enabled=0/' /etc/yum/pluginconf.d/fastestmirror.conf && \
    echo "[main]" >> /etc/yum/pluginconf.d/subscription-manager.conf && \
    echo "enabled=0" >> /etc/yum/pluginconf.d/subscription-manager.conf && \
    yum clean all && \
    yum makecache && \
    yum install -y deltarpm

# Without this, init won't start the enabled services and exec'ing and starting
# them reports "Failed to get D-Bus connection: Operation not permitted".
VOLUME /run /tmp

# root CA cert expired on October 1st, 2021
RUN yum update -y --enablerepo=centos-7.9-updates ca-certificates

# Download required dependencies by mirror/build processes.
RUN yum install -y \
        anaconda \
        anaconda-runtime \
        autoconf-archive \
        autogen \
        automake \
        bc \
        bind \
        bind-utils \
        bison \
        cpanminus \
        createrepo \
        createrepo_c \
        deltarpm \
        docker-client \
        expat-devel \
        flex \
        isomd5sum \
        gcc \
        gettext \
        git \
        libguestfs-tools \
        libtool \
        libxml2 \
        lighttpd \
        lighttpd-fastcgi \
        lighttpd-mod_geoip \
        net-tools \
        mkisofs \
        mongodb \
        mongodb-server \
        pax \
        perl-CPAN \
        python-deltarpm \
        python-pep8 \
        python-pip \
        python-psutil \
        python2-psutil \
        python36-psutil \
        python3-devel \
        python-sphinx \
        python-subunit \
        python-testrepository \
        python-tox \
        python-yaml \
        python2-ruamel-yaml \
        postgresql \
        qemu-kvm \
        quilt \
        rpm-build \
        rpm-sign \
        rpm-python \
        squashfs-tools \
        sudo \
        systemd \
        syslinux \
        udisks2 \
        vim-enhanced \
        wget

# Finally install a locked down version of mock
RUN groupadd -g 751 cgts && \
    echo "mock:x:751:root" >> /etc/group && \
    echo "mockbuild:x:9001:" >> /etc/group && \
    yum install -y \
        http://mirror.starlingx.cengn.ca/mirror/centos/epel/dl.fedoraproject.org/pub/epel/7/x86_64/Packages/m/mock-1.4.16-1.el7.noarch.rpm \
        http://mirror.starlingx.cengn.ca/mirror/centos/epel/dl.fedoraproject.org/pub/epel/7/x86_64/Packages/m/mock-core-configs-31.6-1.el7.noarch.rpm

# mock custumizations
# forcing chroots since a couple of packages naughtily insist on network access and
# we dont have nspawn and networks happy together.
RUN useradd -s /sbin/nologin -u 9001 -g 9001 mockbuild && \
    rmdir /var/lib/mock && \
    ln -s /localdisk/loadbuild/mock /var/lib/mock && \
    rmdir /var/cache/mock && \
    ln -s /localdisk/loadbuild/mock-cache /var/cache/mock && \
    echo "config_opts['use_nspawn'] = False" >> /etc/mock/site-defaults.cfg && \
    echo "config_opts['rpmbuild_networking'] = True" >> /etc/mock/site-defaults.cfg && \
    echo  >> /etc/mock/site-defaults.cfg


# cpan modules, installing with cpanminus to avoid stupid questions since cpan is whack
RUN cpanm --notest Fatal && \
    cpanm --notest XML::SAX  && \
    cpanm --notest XML::SAX::Expat && \
    cpanm --notest XML::Parser && \
    cpanm --notest XML::Simple

# Install repo tool
RUN curl https://storage.googleapis.com/git-repo-downloads/repo > /usr/local/bin/repo && \
    chmod a+x /usr/local/bin/repo

# installing go and setting paths
ENV GOPATH="/usr/local/go"
ENV PATH="${GOPATH}/bin:${PATH}"
RUN yum install -y golang && \
    mkdir -p ${GOPATH}/bin && \
    curl https://raw.githubusercontent.com/golang/dep/master/install.sh | sh

# Uprev git, repo
RUN yum install -y dh-autoreconf curl-devel expat-devel gettext-devel  openssl-devel perl-devel zlib-devel asciidoc xmlto docbook2X && \
    cd /tmp && \
    wget https://github.com/git/git/archive/v2.29.2.tar.gz -O git-2.29.2.tar.gz && \
    tar xzvf git-2.29.2.tar.gz && \
    cd git-2.29.2 && \
    make configure && \
    ./configure --prefix=/usr/local && \
    make all doc && \
    make install install-doc && \
    cd /tmp && \
    rm -rf git-2.29.2.tar.gz git-2.29.2

# Systemd Enablement
RUN (cd /lib/systemd/system/sysinit.target.wants/; for i in *; do [ $i == systemd-tmpfiles-setup.service ] || rm -f $i; done); \
    rm -f /lib/systemd/system/multi-user.target.wants/*;\
    rm -f /etc/systemd/system/*.wants/*;\
    rm -f /lib/systemd/system/local-fs.target.wants/*; \
    rm -f /lib/systemd/system/sockets.target.wants/*udev*; \
    rm -f /lib/systemd/system/sockets.target.wants/*initctl*; \
    rm -f /lib/systemd/system/basic.target.wants/*;\
    rm -f /lib/systemd/system/anaconda.target.wants/*

# pip installs
COPY toCOPY/builder-constraints.txt /home/$MYUNAME/
RUN pip install -c /home/$MYUNAME/builder-constraints.txt pbr==5.6.0 --upgrade && \
    pip install -c /home/$MYUNAME/builder-constraints.txt git-review==2.1.0 --upgrade && \
    pip install -c /home/$MYUNAME/builder-constraints.txt python-subunit==1.4.0 junitxml==0.7 testtools==2.4.0 --upgrade && \
    pip install -c /home/$MYUNAME/builder-constraints.txt tox==3.23.0 --upgrade

# Inherited  tools for mock stuff
# we at least need the mock_cache_unlock tool
# they install into /usr/bin
COPY toCOPY/mock_overlay /opt/mock_overlay
RUN cd /opt/mock_overlay && \
    make && \
    make install

# This image requires a set of scripts and helpers
# for working correctly, in this section they are
# copied inside the image.
COPY toCOPY/finishSetup.sh /usr/local/bin
COPY toCOPY/populate_downloads.sh /usr/local/bin
COPY toCOPY/generate-local-repo.sh /usr/local/bin
COPY toCOPY/generate-centos-repo.sh /usr/local/bin
COPY toCOPY/lst_utils.sh /usr/local/bin
COPY toCOPY/.inputrc /home/$MYUNAME/

# Thes are included for backward compatibility, and
# should be removed after a reasonable time.
COPY toCOPY/generate-cgcs-tis-repo /usr/local/bin
COPY toCOPY/generate-cgcs-centos-repo.sh /usr/local/bin

# centos locales are broken. this needs to be run after the last yum install/update
RUN localedef -i en_US -f UTF-8 en_US.UTF-8

# setup
RUN mkdir -p /www/run && \
    mkdir -p /www/logs && \
    mkdir -p /www/home && \
    mkdir -p /www/root/htdocs/localdisk && \
    chown -R $MYUID:cgts /www && \
    ln -s /localdisk/loadbuild /www/root/htdocs/localdisk/loadbuild && \
    ln -s /import/mirrors/CentOS /www/root/htdocs/CentOS && \
    ln -s /import/mirrors/fedora /www/root/htdocs/fedora && \
    ln -s /localdisk/designer /www/root/htdocs/localdisk/designer

# lighthttpd setup
# chmod for /var/log/lighttpd fixes a centos issue
# in place sed for server root since it's expanded soon thereafter
#     echo "server.bind = \"localhost\"" >> /etc/lighttpd/lighttpd.conf && \
RUN echo "$MYUNAME ALL=(ALL:ALL) NOPASSWD:ALL" >> /etc/sudoers && \
    mkdir -p  /var/log/lighttpd  && \
    chmod a+rwx /var/log/lighttpd/ && \
    sed -i 's%^var\.log_root.*$%var.log_root = "/www/logs"%g' /etc/lighttpd/lighttpd.conf  && \
    sed -i 's%^var\.server_root.*$%var.server_root = "/www/root"%g' /etc/lighttpd/lighttpd.conf  && \
    sed -i 's%^var\.home_dir.*$%var.home_dir = "/www/home"%g' /etc/lighttpd/lighttpd.conf  && \
    sed -i 's%^var\.state_dir.*$%var.state_dir = "/www/run"%g' /etc/lighttpd/lighttpd.conf  && \
    sed -i "s/server.port/#server.port/g" /etc/lighttpd/lighttpd.conf  && \
    sed -i "s/server.use-ipv6/#server.use-ipv6/g" /etc/lighttpd/lighttpd.conf && \
    sed -i "s/server.username/#server.username/g" /etc/lighttpd/lighttpd.conf && \
    sed -i "s/server.groupname/#server.groupname/g" /etc/lighttpd/lighttpd.conf && \
    sed -i "s/server.bind/#server.bind/g" /etc/lighttpd/lighttpd.conf && \
    sed -i "s/server.document-root/#server.document-root/g" /etc/lighttpd/lighttpd.conf && \
    sed -i "s/server.dirlisting/#server.dirlisting/g" /etc/lighttpd/lighttpd.conf && \
    echo "server.port = 8088" >> /etc/lighttpd/lighttpd.conf && \
    echo "server.use-ipv6 = \"disable\"" >> /etc/lighttpd/lighttpd.conf && \
    echo "server.username = \"$MYUNAME\"" >> /etc/lighttpd/lighttpd.conf && \
    echo "server.groupname = \"cgts\"" >> /etc/lighttpd/lighttpd.conf && \
    echo "server.bind = \"localhost\"" >> /etc/lighttpd/lighttpd.conf && \
    echo "server.document-root   = \"/www/root/htdocs\"" >> /etc/lighttpd/lighttpd.conf && \
    sed -i "s/dir-listing.activate/#dir-listing.activate/g" /etc/lighttpd/conf.d/dirlisting.conf && \
    echo "dir-listing.activate = \"enable\"" >> /etc/lighttpd/conf.d/dirlisting.conf

#  ENV setup
RUN echo "# Load stx-builder configuration" >> /etc/profile.d/stx-builder-conf.sh && \
    echo "if [[ -r \${HOME}/buildrc ]]; then" >> /etc/profile.d/stx-builder-conf.sh && \
    echo "    source \${HOME}/buildrc" >> /etc/profile.d/stx-builder-conf.sh && \
    echo "    export PROJECT SRC_BUILD_ENVIRONMENT MYPROJECTNAME MYUNAME" >> /etc/profile.d/stx-builder-conf.sh && \
    echo "    export MY_BUILD_CFG MY_BUILD_CFG_RT MY_BUILD_CFG_STD MY_BUILD_DIR MY_BUILD_ENVIRONMENT MY_BUILD_ENVIRONMENT_FILE MY_BUILD_ENVIRONMENT_FILE_RT MY_BUILD_ENVIRONMENT_FILE_STD MY_DEBUG_BUILD_CFG_RT MY_DEBUG_BUILD_CFG_STD MY_LOCAL_DISK MY_MOCK_ROOT MY_REPO MY_REPO_ROOT_DIR MY_SRC_RPM_BUILD_DIR MY_RELEASE MY_WORKSPACE LAYER" >> /etc/profile.d/stx-builder-conf.sh && \
    echo "fi" >> /etc/profile.d/stx-builder-conf.sh && \
    echo "export FORMAL_BUILD=0" >> /etc/profile.d/stx-builder-conf.sh && \
    echo "export PATH=\$MY_REPO/build-tools:\$PATH" >> /etc/profile.d/stx-builder-conf.sh

RUN useradd -r -u $MYUID -g cgts -m $MYUNAME && \
    ln -s /home/$MYUNAME/.ssh /mySSH && \
    rsync -av /etc/skel/ /home/$MYUNAME/

# now that we are doing systemd, make the startup script be in bashrc
# also we need to SHADOW the udev centric mkefiboot script with a sudo centric one
RUN echo "bash -C /usr/local/bin/finishSetup.sh" >> /home/$MYUNAME/.bashrc && \
    echo "export PATH=/usr/local/bin:/localdisk/designer/$MYUNAME/bin:\$PATH" >> /home/$MYUNAME/.bashrc && \
    chmod a+x /usr/local/bin/*

# Genrate a git configuration file in order to save an extra step
# for end users, this file is required by "repo" tool.
RUN chown $MYUNAME /home/$MYUNAME && \
    if [ -z $MY_EMAIL ]; then MY_EMAIL=$MYUNAME@opendev.org; fi && \
    runuser -u $MYUNAME -- git config --global user.email $MY_EMAIL && \
    runuser -u $MYUNAME -- git config --global user.name $MYUNAME && \
    runuser -u $MYUNAME -- git config --global color.ui false

# Customizations for mirror creation
RUN rm /etc/yum.repos.d/*
COPY centos-mirror-tools/yum.repos.d/* /etc/yum.repos.d/
COPY centos-mirror-tools/rpm-gpg-keys/* /etc/pki/rpm-gpg/

# Import GPG keys
RUN rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY*

# Try to continue a yum command even if a StarlingX repo is unavailable.
RUN yum-config-manager --setopt=StarlingX\*.skip_if_unavailable=1 --save

# When we run 'init' below, it will run systemd, and systemd requires RTMIN+3
# to exit cleanly. By default, docker stop uses SIGTERM, which systemd ignores.
STOPSIGNAL RTMIN+3

# Don't know if it's possible to run services without starting this
CMD /usr/sbin/init
