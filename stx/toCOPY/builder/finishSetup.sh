#!/bin/bash

. $HOME/buildrc

REPOMGR=aptly
if [ "$REPOMGR" == "aptly" ]; then
    STX_MIRROR="${STX_MIRROR_URL}/debian/debian/deb.debian.org/debian/${DEBIAN_DISTRIBUTION}-${DEBIAN_VERSION} ${DEBIAN_DISTRIBUTION} main"
    REPO_SNAPSHOT="[check-valid-until=no] ${DEBIAN_SNAPSHOT} ${DEBIAN_DISTRIBUTION} main"
    REPO_BIN="deb [trusted=yes] ${REPOMGR_DEPLOY_URL}deb-local-binary ${DEBIAN_DISTRIBUTION} main"
    REPO_SRC="deb-src [trusted=yes] ${REPOMGR_DEPLOY_URL}deb-local-source ${DEBIAN_DISTRIBUTION} main"
    ret=`grep 'deb-local-binary' /etc/apt/sources.list`
    if [ "x$ret" == "x" ]; then
        sed -i "1i\\${REPO_BIN}" /etc/apt/sources.list
    fi
    ret=`grep 'deb-local-source' /etc/apt/sources.list`
    if [ "x$ret" == "x" ]; then
        sed -i "1i\\${REPO_SRC}" /etc/apt/sources.list
    fi
    ret=`grep ${DEBIAN_SNAPSHOT} /etc/apt/sources.list`
    if [ "x$ret" == "x" ]; then
        sed -i "1i\\deb ${REPO_SNAPSHOT}" /etc/apt/sources.list
        sed -i "1i\\deb-src ${REPO_SNAPSHOT}" /etc/apt/sources.list
    fi
    ret=`grep ${STX_MIRROR_URL} /etc/apt/sources.list`
    if [ "x$ret" == "x" ]; then
        sed -i "1i\\deb ${STX_MIRROR}" /etc/apt/sources.list
        sed -i "1i\\deb-src ${STX_MIRROR}" /etc/apt/sources.list
    fi
fi

addgroup -gid 751 cgts > /dev/null 2>&1
adduser --uid $MYUID --ingroup cgts --home /home/$MYUNAME --shell /bin/bash --disabled-password --gecos "" $MYUNAME > /dev/null 2>&1
ret=`cat /etc/sudoers | grep "${MYUNAME}"`
if [ "x$ret" == "x" ]; then
    echo "${MYUNAME} ALL=(ALL:ALL) NOPASSWD:ALL" >> /etc/sudoers
fi

chown ${MYUNAME}:cgts /localdisk
chown ${MYUNAME}:cgts /localdisk/channel
chown ${MYUNAME}:cgts /localdisk/designer
chown ${MYUNAME}:cgts /localdisk/loadbuild
if [ ! -d "/localdisk/pkgbuilder" ]; then
    mkdir /localdisk/pkgbuilder
fi
chown root:root /localdisk/pkgbuilder

cp -f /root/buildrc /home/$MYUNAME/
cp -f /root/localrc /home/$MYUNAME/
cp -f /root/userenv /home/$MYUNAME/
chown -R ${MYUNAME}:cgts /home/$MYUNAME
