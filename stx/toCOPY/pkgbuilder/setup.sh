#!/bin/bash

if [ -f "/etc/fstab" ]; then
    speed_up=`cat /etc/fstab | grep 'speeding up sbuild'`
    [ "x${speed_up}" != "x" ] && exit 0
fi

cat >>/etc/fstab << EOF
# For speeding up sbuild/schroot and prevent SSD wear-out
tmpfs /var/lib/schroot/session        tmpfs uid=root,gid=root,mode=0755 0 0
tmpfs /var/lib/schroot/union/overlay  tmpfs uid=root,gid=root,mode=0755 0 0
tmpfs /var/lib/sbuild/build           tmpfs uid=sbuild,gid=sbuild,mode=2770 0 0
EOF

mount -a
