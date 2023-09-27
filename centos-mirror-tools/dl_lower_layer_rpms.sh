#!/bin/bash

#
# Copyright (c) 2020 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

#
# Fast download of StarlingX built rpms using verifytree and repsync
#

DL_LOWER_LAYER_RPMS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE[0]}" )" )"

source $DL_LOWER_LAYER_RPMS_DIR/utils.sh

usage() {
    echo "$0 -l <layer> -b <build_type> -r <url> <rpms_list> <match_level> [ -c <yum.conf> ] [-D <distro> ] [-s|-S|-u|-U] [-x]"
    echo ""
    echo "Options:"
    echo "  -b: <build type>:  e.g. std, rt, installer."
    echo "  -c: Use an alternate yum.conf rather than the system file"
    echo "  -l: <layer>: e.g. compiler, distro, flock."
    echo "  -r: <url>: Url of the root of the repo.  Expect to find a repodata dir there."
    echo "  -x: Clean log files only, do not run."
    echo "  rpm_list: a list of RPM files to be downloaded."
    echo "  match_level: value could be L1, L2 or L3:"
    echo "    L1: use name, major version and minor version:"
    echo "        vim-7.4.160-2.el7 to search vim-7.4.160-2.el7.src.rpm"
    echo "    L2: use name and major version:"
    echo "        using vim-7.4.160 to search vim-7.4.160-2.el7.src.rpm"
    echo "    L3: use name:"
    echo "        using vim to search vim-7.4.160-2.el7.src.rpm"
    echo "    K1: Use Koji rather than yum repos as a source."
    echo "        Koji has a longer retention period than epel mirrors."
    echo ""
    echo "  Download Source Options:  Only select one of these."
    echo "    -s: Download from StarlingX mirror only"
    echo "    -S: Download from StarlingX mirror, upstream as backup (default)"
    echo "    -u: Download from original upstream sources only"
    echo "    -U: Download from original upstream sources, StarlingX mirror as backup"
    echo ""
    echo "Returns: 0 = All files downloaded successfully"
    echo "         1 = Some files could not be downloaded"
    echo "         2 = Bad arguements or other error"
    echo ""
}


CLEAN_LOGS_ONLY=0
dl_rc=0

# Permitted values of dl_source
dl_from_stx_mirror="stx_mirror"
dl_from_upstream="upstream"
dl_from_stx_then_upstream="$dl_from_stx_mirror $dl_from_upstream"
dl_from_upstream_then_stx="$dl_from_upstream $dl_from_stx_mirror"

# Download from what source?
#   dl_from_stx_mirror = StarlingX mirror only
#   dl_from_upstream   = Original upstream source only
#   dl_from_stx_then_upstream = Either source, STX prefered (default)"
#   dl_from_upstream_then_stx = Either source, UPSTREAM prefered"
dl_source="$dl_from_stx_then_upstream"
dl_flag=""
build_type=""
lower_layer=""
url_root=""
distro="centos"

# Set a default yum.conf which can be overridden by use of '-c' option.
# I assume we are called from download_mirror.sh and are already in
# stx-tools/centos-mirror-tools directory.
YUM_CONF=yum.conf.sample

MULTIPLE_DL_FLAG_ERROR_MSG="Error: Please use only one of: -s,-S,-u,-U"

multiple_dl_flag_check () {
    if [ "$dl_flag" != "" ]; then
        echo "$MULTIPLE_DL_FLAG_ERROR_MSG"
        usage
        exit 1
    fi
}

# Parse option flags
while getopts "b:c:l:D:hr:sSuUx" o; do
    case "${o}" in
        b)
            build_type="$OPTARG"
            ;;
        c)
            # Use an alternate yum.conf
            YUM_CONF="$OPTARG"
            ;;
        D)
            distro="${OPTARG}"
            ;;
        l)
            lower_layer="$OPTARG"
            ;;
        r)
            # URL
            url_root="${OPTARG}"
            ;;
        s)
            # Download from StarlingX mirror only. Do not use upstream sources.
            multiple_dl_flag_check
            dl_source="$dl_from_stx_mirror"
            dl_flag="-s"
            ;;
        S)
            # Download from StarlingX mirror first, only use upstream source as a fallback.
            multiple_dl_flag_check
            dl_source="$dl_from_stx_then_upstream"
            dl_flag="-S"
            ;;
        u)
            # Download from upstream only. Do not use StarlingX mirror.
            multiple_dl_flag_check
            dl_source="$dl_from_upstream"
            dl_flag="-u"
            ;;
        U)
            # Download from upstream first, only use StarlingX mirror as a fallback.
            multiple_dl_flag_check
            dl_source="$dl_from_upstream_then_stx"
            dl_flag="-U"
            ;;
        x)
            # Clean only
            CLEAN_LOGS_ONLY=1
            ;;
        h)
            # Help
            usage
            exit 0
            ;;
        *)
            usage
            exit 2
            ;;
    esac
done
shift $((OPTIND-1))

if [ -z "${build_type}" ] || [ -z "${lower_layer}" ] || [ -z "${url_root}" ]; then
    usage
    exit 2
fi

if [ $# -lt 2 ]; then
    usage
    exit 2
fi

if [ "$1" == "" ]; then
    echo "Need to supply the rpm file list"
    exit 2;
else
    rpms_list=$1
    echo "using $rpms_list as the download name lists"
fi

match_level="L1"

if [ ! -z "$2" -a "$2" != " " ];then
    match_level=$2
fi

if [ ! -f ${YUM_CONF} ]; then
    echo "ERROR: failed to find ${YUM_CONF}"
    usage
    exit 2
fi

timestamp=$(date +%F_%H%M)
echo $timestamp

export DL_MIRROR_LOG_DIR="${DL_MIRROR_LOG_DIR:-./logs}"
export DL_MIRROR_OUTPUT_DIR="${DL_MIRROR_OUTPUT_DIR:-./output/stx/CentOS}"

dl_dir="$(readlink -f ${DL_MIRROR_OUTPUT_DIR})/layer_repos/${lower_layer}/${build_type}"

LOGSDIR="${DL_MIRROR_LOG_DIR}"
MISSING_RPMS="$LOGSDIR/${match_level}_rpms_missing_${lower_layer}_${build_type}.log"
FOUND_RPMS="$LOGSDIR/${match_level}_rpms_found_${lower_layer}_${build_type}.log"
cat /dev/null > $MISSING_RPMS
cat /dev/null > $FOUND_RPMS


if [ $CLEAN_LOGS_ONLY -eq 1 ];then
    exit 0
fi

CREATEREPO=$(which createrepo_c)
if [ $? -ne 0 ]; then
    CREATEREPO="createrepo"
fi

number_of_cpus () {
    /usr/bin/nproc
}

# FIXME: curl would work better here, but it doesn't support recursive downloads.
#
# Wget corrupts files in some cases:
# - if the download stalls half-way and --tries is set to > 1, and the web
#   server doesn't support the Range header with the upper limit omitted,
#   (eg Range: bytes=18671712-) wget returns success (0) and leaves a partial
#   file behind
# - if download fails half-way, or wget is interrupted, wget returns
#   non-zero, but may leave a partial file behind. This is to be expected,
#   but we can't easily tell which files were downloaded fully in this case.
#
# See https://bugs.launchpad.net/starlingx/+bug/1950017
get_remote_dir () {
    local url="${1}"
    local dest_dir="${2}"
    mkdir -p "${dest_dir}" || return 1
    \rm "${dest_dir}/"index.html*
    wget -c -N --timeout 15 --recursive --no-parent --no-host-directories --no-directories --directory-prefix="${dest_dir}" "${url}/"
}

get_remote_file_overwrite () {
    local url="${1}"
    local dest_dir="${2}"
    local dest_file="${dest_dir}/$(basename ${url})"
    mkdir -p "${dest_dir}" || return 1

    if [ -f "${dest_file}" ]; then
        \rm "${dest_file}"
    fi
    download_file --timestamps "$url" "$dest_file"
}

clean_repodata () {
    local repodata="${1}"
    local f=""
    local f2=""

    if [ ! -f "${repodata}/repomd.xml" ]; then
        echo "Error: clean_repodata: file not found: ${repodata}/repomd.xml"
        return 1
    fi

    for f in $(find "${repodata}" -name '[a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9]*'); do
        f2=$(basename "${f}")
        if ! grep -q "${f2}" "${repodata}/repomd.xml"; then
            \rm "${f}"
        fi
    done
}


dl_repo () {
    local base_url="${1}"
    local dl_dir="${2}"
    local rpms_list="${3}"

    if [ -z "${base_url}" ] || [ -z "${dl_dir}" ] || [ -z "${rpms_list}" ]; then
        echo "ERROR: dl_repo: missing arguement"
        return 1
    fi

    if [ ! -f "${rpms_list}" ]; then
        echo "ERROR: dl_repo: no such file '${rpms_list}'"
        return 1
    fi

    local REPO_URL="${base_url}"
    local DOWNLOAD_PATH="${dl_dir}"
    local DOWNLOAD_PATH_NEW="${DOWNLOAD_PATH}.new"
    local DOWNLOAD_PATH_OLD="${DOWNLOAD_PATH}.old"

    mkdir -p "${DOWNLOAD_PATH}"

    local YUM_CONF_TMP
    local TMP
    local YUM_CONF_DIR_TMP
    local MUNGED_LIST
    local YUM_CONF_NAME
    YUM_CONF_NAME=$(basename "${YUM_CONF}")
    YUM_CONF_TMP="$(mktemp "/tmp/${YUM_CONF_NAME}.XXXXXX")"
    TMP=$(basename "${YUM_CONF_TMP}" | sed "s#^${YUM_CONF_NAME}.##")
    YUM_CONF_DIR=$(dirname "${YUM_CONF_TMP}")
    YUM_REPOS_DIR_TMP="${YUM_CONF_DIR}/yum.repos.d.${TMP}"
    MUNGED_LIST="${YUM_CONF_DIR}/yum.lst.${TMP}"

    grep -v '^$' "${rpms_list}" | grep -v '^#' | sed 's#^\(.*\)[.]rpm#\t\1#' | sort --unique > ${MUNGED_LIST}
    \cp "${YUM_CONF}" "${YUM_CONF_TMP}"
    sed -i "s#^reposdir=.*#reposdir=${YUM_REPOS_DIR_TMP}#" "${YUM_CONF_TMP}"
    mkdir -p "${YUM_REPOS_DIR_TMP}"

    REPOID=${lower_layer}_${build_type}
    REPO_FILE="${YUM_REPOS_DIR_TMP}/${REPOID}.repo"
    echo "[${REPOID}]" > "${REPO_FILE}"
    echo "name=${REPOID}" >> "${REPO_FILE}"
    echo "baseurl=${REPO_URL}" >> "${REPO_FILE}"
    echo "includepkgs=" >> "${REPO_FILE}"
    echo "include=file://${MUNGED_LIST}" >> "${REPO_FILE}"
    echo "enabled=0" >> "${REPO_FILE}"

    # copy repo to a temp location
    if [ -d "${DOWNLOAD_PATH_NEW}" ]; then
        \rm -rf "${DOWNLOAD_PATH_NEW}"
    fi

    if [ -d "${DOWNLOAD_PATH}" ]; then
        CMD="\cp --archive --link '${DOWNLOAD_PATH}' '${DOWNLOAD_PATH_NEW}'"
        echo "$CMD"
        eval $CMD
        if [ $? -ne 0 ]; then
            echo "Error: $CMD"
            return 1
        fi
    fi

    #  Download latest repodata
    get_remote_dir "${REPO_URL}/repodata" "${DOWNLOAD_PATH_NEW}/repodata.upstream"
    if [ $? -ne 0 ]; then
        echo "Error: get_remote_dir ${REPO_URL}/repodata ${DOWNLOAD_PATH_NEW}/repodata.upstream"
        return 1
    fi

    get_remote_file_overwrite "${REPO_URL}/repodata/repomd.xml" "${DOWNLOAD_PATH_NEW}/repodata.upstream/"
    if [ $? -ne 0 ]; then
        echo "Error: get_remote_file_overwrite ${REPO_URL}/repodata/repomd.xml ${DOWNLOAD_PATH_NEW}/repodata.upstream/"
        return 1
    fi

    clean_repodata "${DOWNLOAD_PATH_NEW}/repodata.upstream/"

    #  Download latest rpm.lst
    get_remote_file_overwrite "${REPO_URL}/rpm.lst" "${DOWNLOAD_PATH_NEW}/"

    #
    # Delete rpms that are no longer valid
    #

    # Save active repodata as local
    if [ -d "${DOWNLOAD_PATH_NEW}/repodata" ]; then
        CMD="\mv '${DOWNLOAD_PATH_NEW}/repodata' '${DOWNLOAD_PATH_NEW}/repodata.local'"
        echo "$CMD"
        eval $CMD
        if [ $? -ne 0 ]; then
            echo "Error: $CMD"
            return 1
        fi
    fi

    # Make upstream repodata the active copy
    CMD="\mv '${DOWNLOAD_PATH_NEW}/repodata.upstream' '${DOWNLOAD_PATH_NEW}/repodata'"
    echo "$CMD"
    eval $CMD
    if [ $? -ne 0 ]; then
        echo "Error: $CMD"
        return 1
    fi

    # Do the audit, delete anything broken
    for f in $(verifytree -a "file://${DOWNLOAD_PATH_NEW}" | \
                    sed '1,/Checking all packages/d' | \
                    grep -v ' FAILED$' | \
                    awk '{ print $2 }' | \
                    sed 's/^[0-9]*://'); do
        echo "Already have $f"
    done
    for f in $(verifytree -a "file://${DOWNLOAD_PATH_NEW}" | \
                    sed '1,/Checking all packages/d' | \
                    grep ' FAILED$' | \
                    awk '{ print $2 }' | \
                    sed 's/^[0-9]*://'); do
        echo "Downloading $f"
        for f_path in $(find "${DOWNLOAD_PATH_NEW}" -name ${f}.rpm); do
            CMD="\rm '${f_path}'"
            echo "$CMD"
            eval $CMD
            if [ $? -ne 0 ]; then
                echo "Error: $CMD"
                return 1
            fi
        done
    done

    # deactivate and restore upstream repo data
    CMD="\mv '${DOWNLOAD_PATH_NEW}/repodata' '${DOWNLOAD_PATH_NEW}/repodata.upstream'"
    echo "$CMD"
    eval $CMD
    if [ $? -ne 0 ]; then
        echo "Error: $CMD"
        return 1
    fi

    # Restore our active repodata
    if [ -d "${DOWNLOAD_PATH_NEW}/repodata.local" ]; then
        CMD="\mv '${DOWNLOAD_PATH_NEW}/repodata.local' '${DOWNLOAD_PATH_NEW}/repodata'"
        echo "$CMD"
        eval $CMD
        if [ $? -ne 0 ]; then
            echo "Error: $CMD"
            return 1
        fi
    fi

    # Sync the repo's rpms
    CMD="reposync --tempcache --norepopath -l --config=${YUM_CONF_TMP} --repoid=$REPOID --download_path=${DOWNLOAD_PATH_NEW}"
    echo "$CMD"
    with_retries --delay 60 3 $CMD
    if [ $? -ne 0 ]; then
        echo "Error: $CMD"
        return 1
    fi

    CMD="pushd '${DOWNLOAD_PATH_NEW}'"
    echo "$CMD"
    eval $CMD
    if [ $? -ne 0 ]; then
        echo "Error: $CMD"
        return 1
    fi

    # Update the repodata
    OPTIONS="--workers $(number_of_cpus)"
    if [ -f comps.xml ]; then
        OPTIONS="$OPTIONS -g comps.xml"
    fi
    if [ -d repodata ]; then
        OPTIONS="$OPTIONS --update"
    fi

    CMD="$CREATEREPO $OPTIONS ."
    echo "$CMD"
    eval $CMD
    if [ $? -ne 0 ]; then
        echo "Error: $CMD"
        popd
        return 1
    fi

    popd

    # Swap out the old copy of our repo
    if [ -d "${DOWNLOAD_PATH}" ]; then
        CMD="\mv '${DOWNLOAD_PATH}' '${DOWNLOAD_PATH_OLD}'"
        echo "$CMD"
        eval $CMD
        if [ $? -ne 0 ]; then
            echo "Error: $CMD"
            \rm -rf "${DOWNLOAD_PATH_NEW}"
            return 1
        fi
    fi

    # Swap in the updated repo
    CMD="\mv '${DOWNLOAD_PATH_NEW}' '${DOWNLOAD_PATH}'"
    echo "$CMD"
    eval $CMD
    if [ $? -ne 0 ]; then
        echo "Error: $CMD"
        \mv "${DOWNLOAD_PATH_NEW}" "${DOWNLOAD_PATH}"
        return 1
    fi

    # Delete the old repo
    if [ -d "${DOWNLOAD_PATH_OLD}" ]; then
        CMD="\rm -rf '${DOWNLOAD_PATH_OLD}'"
        echo "$CMD"
        eval $CMD
        if [ $? -ne 0 ]; then
            echo "Error: $CMD"
        fi
    fi

    CMD="\rm '${YUM_CONF_TMP}'"
    echo "$CMD"
    eval $CMD
    if [ $? -ne 0 ]; then
        echo "Error: $CMD"
    fi

    CMD="\rm '${MUNGED_LIST}'"
    echo "$CMD"
    eval $CMD
    if [ $? -ne 0 ]; then
        echo "Error: $CMD"
    fi

    CMD="\rm -rf '${YUM_REPOS_DIR_TMP}'"
    echo "$CMD"
    eval $CMD
    if [ $? -ne 0 ]; then
        echo "Error: $CMD"
    fi

    return 0
}

#
# Loop over download sources... typically the STX mirror folowed by upstream
# ... until we have all the rpms.
#

RC=1
for dl_src in $dl_source; do
    url_root_to_use="${url_root}"
    case $dl_src in
        $dl_from_stx_mirror)
            url_root_to_use="$(url_to_stx_mirror_url "${url_root}" ${distro})"
            ;;
        $dl_from_upstream)
            url_root_to_use="${url_root}"
            ;;
        *)
            echo "Error: Unknown dl_source '$dl_src'"
            continue
            ;;
    esac

    dl_repo "${url_root_to_use}"  "${dl_dir}"  "${rpms_list}"
    if [ $? -eq 0 ]; then
        RC=0
        break
    fi
done

for rpm_name in $(grep -v '^$' "${rpms_list}" | grep -v '^#' ); do
    if [ ! -f "${dl_dir}/${rpm_name}" ]; then
        echo "${rpm_name}" >> $MISSING_RPMS
        echo "Failed to download: ${rpm_name}"
        RC=1
    fi
done


exit $RC
