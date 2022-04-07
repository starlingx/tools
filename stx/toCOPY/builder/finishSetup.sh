#!/bin/bash

. $HOME/buildrc

REPOMGR=aptly
if [ "$REPOMGR" == "aptly" ]; then
    CENGN_MIRROR="${CENGNURL}/debian/debian/deb.debian.org/debian/bullseye-11.3 bullseye main"
    REPO_SNAPSHOT="[check-valid-until=no] ${DEBIAN_SNAPSHOT} bullseye main"
    REPO_BIN="deb [trusted=yes] ${REPOMGR_DEPLOY_URL}deb-local-binary bullseye main"
    REPO_SRC="deb-src [trusted=yes] ${REPOMGR_DEPLOY_URL}deb-local-source bullseye main"
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
    ret=`grep ${CENGNURL} /etc/apt/sources.list`
    if [ "x$ret" == "x" ]; then
        sed -i "1i\\deb ${CENGN_MIRROR}" /etc/apt/sources.list
        sed -i "1i\\deb-src ${CENGN_MIRROR}" /etc/apt/sources.list
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
if [ ! -d "/localdisk/pkgbuilder" ]; then
    mkdir /localdisk/pkgbuilder
fi
chown root:root /localdisk/pkgbuilder

cp -f /root/buildrc /home/$MYUNAME/
cp -f /root/localrc /home/$MYUNAME/
cp -f /root/userenv /home/$MYUNAME/
chown -R ${MYUNAME}:cgts /home/$MYUNAME
