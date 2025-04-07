#!/bin/bash

SCHROOT_FSTAB="/etc/schroot/sbuild/fstab"

if [ -f "/etc/fstab" ]; then
    speed_up=`cat /etc/fstab | grep 'speeding up sbuild'`
    [ "x${speed_up}" != "x" ] && exit 0
fi

cat >>/etc/fstab << EOF
# For speeding up sbuild/schroot and prevent SSD wear-out
tmpfs /var/lib/schroot/session        tmpfs uid=root,gid=root,mode=0755 0 0
tmpfs /var/lib/schroot/union/overlay  tmpfs uid=root,gid=root,mode=0755 0 0
EOF

# The root '/' of the container is on docker overlay, so the
# original '/build' of chroot is on overlay, here remove the
# setting and make the '/build' to the shared volume of container
sed -i "/\/var\/lib\/sbuild\/build/d" ${SCHROOT_FSTAB}

mount -a
