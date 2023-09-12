#!/bin/bash

#
# SPDX-License-Identifier: Apache-2.0
#

#
# Replicate a yum.conf and yum.repo.d under a temporary directory and
# then modify the files to point to equivalent repos in the StarlingX mirror.
# This script was originated by Scott Little
#

MAKE_STX_MIRROR_YUM_CONF_DIR="$(dirname "$(readlink -f "${BASH_SOURCE[0]}" )" )"

source "$MAKE_STX_MIRROR_YUM_CONF_DIR/utils.sh" || exit 1

DISTRO="centos"
SUDO=sudo

TEMP_DIR=""
SRC_REPO_DIR="$MAKE_STX_MIRROR_YUM_CONF_DIR/yum.repos.d"
SRC_YUM_CONF="$MAKE_STX_MIRROR_YUM_CONF_DIR/yum.conf.sample"

RETAIN_REPODIR=0

usage () {
    echo ""
    echo "$0 -d <dest_dir> [-D <distro>] [-y <src_yum_conf>] [-r <src_repos_dir>] [-R] [-l <layer>] [-u <lower-layer>,<repo_url>]"
    echo ""
    echo "Replicate a yum.conf and yum.repo.d under a new directory and"
    echo "then modify the files to point to equivalent repos in the StarlingX"
    echo "mirror."
    echo ""
    echo "-d <dest_dir> = Place modified yum.conf and yum.repo.d into this directory"
    echo "-D <distro>   = Target distro on StarlingX mirror. Default is 'centos'"
    echo "-y <yum_conf> = Path to yum.conf file that we will modify.  Default is"
    echo "                'yum.conf.sample' in same directory as this script"
    echo "-r <repos_dir> = Path to yum.repos.d that we will modify.  Default is"
    echo "                 'yum.repos.d' in same directory as this script"
    echo "-l <layer> = Download only packages required to build a given layer"
    echo "-u <lower-layer>,<build-type>,<repo_url> = Add/change the repo baseurl for a lower layer"
    echo "-n don't use sudo"
}

declare -A layer_urls

set_layer_urls () {
    local option="${1}"
    local layer_and_build_type="${option%,*}"
    local layer="${layer_and_build_type%,*}"
    local build_type="${layer_and_build_type#*,}"
    local layer_url="${option##*,}"

    # Enforce trailing '/'
    if [ "${layer_url:${#layer_url}-1:1}" != "/" ]; then
        layer_url+="/"
    fi

    layer_urls["${layer_and_build_type}"]="${layer_url}"
}


#
# option processing
#
while getopts "D:d:l:nRr:u:y:" o; do
    case "${o}" in
        D)
            DISTRO="${OPTARG}"
            ;;
        d)
            TEMP_DIR="${OPTARG}"
            ;;
        l)
            LAYER="${OPTARG}"
            ;;
        n)
            SUDO=""
            ;;
        r)
            SRC_REPO_DIR="${OPTARG}"
            ;;
        R)
            RETAIN_REPODIR=1
            ;;
        u)
            set_layer_urls "${OPTARG}"
            ;;
        y)
            SRC_YUM_CONF="${OPTARG}"
            ;;
        *)
            usage
            exit 1
            ;;
    esac
done

#
# option validation
#
if [ ! -f $SRC_YUM_CONF ]; then
    echo "Error: yum.conf not found at '$SRC_YUM_CONF'"
    exit 1
fi

if [ ! -d $SRC_REPO_DIR ]; then
    echo "Error: repo dir not found at '$SRC_REPO_DIR'"
    exit 1
fi

if [ "$TEMP_DIR" == "" ]; then
    echo "Error: working dir not provided"
    usage
    exit 1
fi

if [ ! -d $TEMP_DIR ]; then
    echo "Error: working dir not found at '$TEMP_DIR'"
    exit 1
fi

#
# Get the value of the $releasever variable.
#
# If the source yum.conf has a releasever= setting, we will honor
# that, even though yum will not.
#
# Otherwise use yum to query the host environment (Docker).
# This assumes the host environmnet has the same releasever
# as that which will be used inside StarlingX.
#
# NOTE: In other scripts we will read releasever= out of yum.conf
# and push it back into yum via --releasever=<#>.
#
get_releasever () {
    if [ -f $SRC_YUM_CONF ] && grep -q '^releasever=' $SRC_YUM_CONF; then
        grep '^releasever=' $SRC_YUM_CONF | cut -d '=' -f 2
    else
        ${SUDO} yum version nogroups | grep Installed | cut -d ' ' -f 2 | cut -d '/' -f 1
    fi
}

#
# Get the value of the $basearch variable.
#
# Just use yum to query the host environment (Docker) as we don't support
# cross compiling.
#
get_arch () {
    ${SUDO} yum version nogroups | grep Installed | cut -d ' ' -f 2 | cut -d '/' -f 2
}


#
# Global variables we will use later.
#
STX_MIRROR_REPOS_DIR="$TEMP_DIR/yum.repos.d"
STX_MIRROR_YUM_CONF="$TEMP_DIR/yum.conf"
STX_MIRROR_YUM_LOG="$TEMP_DIR/yum.log"
STX_MIRROR_YUM_CACHDIR="$TEMP_DIR/cache/yum/\$basearch/\$releasever"

RELEASEVER=$(get_releasever)
ARCH=$(get_arch)

#
# Copy as yet unmodified yum.conf and yum.repos.d from source to dest.
#
mkdir -p "$STX_MIRROR_REPOS_DIR"
echo "\cp -r '$SRC_REPO_DIR/*' '$STX_MIRROR_REPOS_DIR/'"
\cp -r "$SRC_REPO_DIR"/* "$STX_MIRROR_REPOS_DIR/"
echo "\cp '$SRC_YUM_CONF' '$STX_MIRROR_YUM_CONF'"
\cp "$SRC_YUM_CONF" "$STX_MIRROR_YUM_CONF"

if [ "$LAYER" != "all" ]; then
    if [ -d ${MAKE_STX_MIRROR_YUM_CONF_DIR}/config/${DISTRO}/${LAYER}/yum.repos.d ]; then
        \cp -f ${MAKE_STX_MIRROR_YUM_CONF_DIR}/config/${DISTRO}/${LAYER}/yum.repos.d/*.repo $STX_MIRROR_REPOS_DIR
    fi
fi

#
# Add or modify reposdir= value in our new yum.conf
#
if grep -q '^reposdir=' $STX_MIRROR_YUM_CONF; then
    # reposdir= already exists, modify it
    if [ $RETAIN_REPODIR -eq 1 ]; then
        # Append STX_MIRROR_REPOS_DIR
        sed "s#^reposdir=\(.*\)\$#reposdir=\1 $STX_MIRROR_REPOS_DIR#" -i $STX_MIRROR_YUM_CONF
    else
        # replace with STX_MIRROR_REPOS_DIR
        sed "s#^reposdir=.*\$#reposdir=$STX_MIRROR_REPOS_DIR#" -i $STX_MIRROR_YUM_CONF
    fi
else
    # reposdir= doeas not yet exist, add it
    if [ $RETAIN_REPODIR -eq 1 ]; then
        # Add both SRC_REPO_DIR and STX_MIRROR_REPOS_DIR
        echo "reposdir=$SRC_REPO_DIR $STX_MIRROR_REPOS_DIR" >> $STX_MIRROR_YUM_CONF
    else
        # Add STX_MIRROR_REPOS_DIR only
        echo "reposdir=$STX_MIRROR_REPOS_DIR" >> $STX_MIRROR_YUM_CONF
    fi
fi

#
# modify or add logfile= value in our new yum.conf
#
if grep -q '^logfile=' $STX_MIRROR_YUM_CONF; then
    sed "s#^logfile=.*\$#logfile=$STX_MIRROR_YUM_LOG#" -i $STX_MIRROR_YUM_CONF
else
    echo "logfile=$STX_MIRROR_YUM_LOG" >> $STX_MIRROR_YUM_CONF
fi

#
# modify or add cachedir= value in our new yum.conf
#
if grep -q '^cachedir=' $STX_MIRROR_YUM_CONF; then
    sed "s#^cachedir=.*\$#cachedir=$STX_MIRROR_YUM_CACHDIR#" -i $STX_MIRROR_YUM_CONF
else
    echo "cachedir=$STX_MIRROR_YUM_CACHDIR" >> $STX_MIRROR_YUM_CONF
fi


#
# Modify all the repo files in our new yum.repos.d
#
for REPO in $(find "$STX_MIRROR_REPOS_DIR" -type f -name '*repo'); do
    #
    # Replace mirrorlist with baseurl if required
    #
    if grep -q '^mirrorlist=' "$REPO" ; then
        sed '/^mirrorlist=/d' -i "$REPO"
        sed 's%^#baseurl%baseurl%' -i "$REPO"
    fi

    #
    # Substitute any $releasever or $basearch variables
    #
    sed "s#/[$]releasever/#/$RELEASEVER/#g" -i "$REPO"
    sed "s#/[$]basearch/#/$ARCH/#g" -i "$REPO"

    #
    # Turn off gpgcheck for now.
    # Must revisit this at a later date!
    #
    sed 's#^gpgcheck=1#gpgcheck=0#' -i "$REPO"
    sed '/^gpgkey=/d' -i "$REPO"

    #
    # Convert baseurl(s) to StarlingX mirror equivalent
    #
    for URL in $(grep '^baseurl=' "$REPO" | sed 's#^baseurl=##'); do
        STX_MIRROR_URL="$(url_to_stx_mirror_url "$URL" "$DISTRO")"

        # Test STX_MIRROR url
        url_exists --quiet "$STX_MIRROR_URL"
        if [ $? -eq 0 ]; then
            # OK, make substitution
            sed "s#^baseurl=$URL\$#baseurl=$STX_MIRROR_URL#" -i "$REPO"
        fi
    done

    #
    # Prefix repoid and name with STX_MIRROR
    #
    sed "s#^name=\(.*\)#name=STX_MIRROR_\1#" -i "$REPO"
    sed "s#^\[\([^]]*\)\]#[STX_MIRROR_\1]#" -i "$REPO"
done

for key in "${!layer_urls[@]}"; do
    lower_layer="${key%,*}"
    build_type="${key#*,}"
    REPO="$STX_MIRROR_REPOS_DIR/StarlingX_mirror_${lower_layer}_layer.repo"
    if [ -f "$REPO" ]; then
        sed "s#^baseurl=.*/${lower_layer}/.*/${build_type}/\$#baseurl=${layer_urls[${key}]}#" -i "$REPO"
    else
        REPO="$STX_MIRROR_REPOS_DIR/StarlingX_local_${lower_layer}_${build_type}_layer.repo"
        (
        echo "[Starlingx-local_${lower_layer}_${build_type}_layer]"
        echo "name=Starlingx-mirror_${lower_layer}_${build_type}_layer"
        echo "baseurl=${layer_urls[${key}]}"
        echo "enabled=1"
        ) > "$REPO"
    fi
done

echo $TEMP_DIR
