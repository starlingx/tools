#!/bin/bash

. $HOME/buildrc

REPOMGR=aptly
if [ "$REPOMGR" == "aptly" ]; then
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
fi

addgroup -gid 751 cgts > /dev/null 2>&1
adduser --uid $MYUID --ingroup cgts --home /home/$MYUNAME --shell /bin/bash --disabled-password --gecos "" $MYUNAME > /dev/null 2>&1
ret=`cat /etc/sudoers | grep "${MYUNAME}"`
if [ "x$ret" == "x" ]; then
    echo "${MYUNAME} ALL=(ALL:ALL) NOPASSWD:ALL" >> /etc/sudoers
fi
dirs_list=$(find /localdisk -maxdepth 1)
for path in $dirs_list; do
    if [[ $path != "/localdisk" && $path != "/localdisk/pkgbuilder" ]]; then
        chown -R ${MYUNAME}:cgts $path
    fi
done
[ ! -d "/localdisk/pkgbuilder" ] && mkdir /localdisk/pkgbuilder
cp -f /root/buildrc /home/$MYUNAME/
cp -f /root/localrc /home/$MYUNAME/
cp -f /root/userenv /home/$MYUNAME/
chown -R ${MYUNAME}:cgts /home/$MYUNAME
