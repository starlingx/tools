#!/bin/bash -e
#
# SPDX-License-Identifier: Apache-2.0
#
# download RPMs/SRPMs from a base url.
# this script was originated by Scott Little

set -o errexit
set -o nounset

# By default, we use "sudo" and we don't use a local dnf.conf. These can
# be overridden via flags.

DL_RPMS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE[0]}" )" )"

source $DL_RPMS_DIR/utils.sh

BASE_URL=""

usage() {
    echo "$0 -u <base url> <rpms_list> "
    echo ""
    echo "Options:"
    echo "  -u: Use provided base url"
    echo ""
    echo "Returns: 0 = All files downloaded successfully"
    echo "         1 = Some files could not be downloaded"
    echo "         2 = Bad arguements or other error"
    echo ""
}


CLEAN_LOGS_ONLY=0
dl_rc=0


distro="centos"

# Parse option flags
while getopts "u:h" o; do
    case "${o}" in
        u)
            # Use an alternate dnf.conf
            BASE_URL="$OPTARG"
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

if [ $# -lt 1 ]; then
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

if [ ! -f "${rpms_list}" ]; then
    echo "Error: File not found: ${rpms_list}"
    usage
    exit 2
fi

timestamp=$(date +%F_%H%M)
echo $timestamp

export DL_MIRROR_LOG_DIR="${DL_MIRROR_LOG_DIR:-./logs}"
export DL_MIRROR_OUTPUT_DIR="${DL_MIRROR_OUTPUT_DIR:-./output/stx/CentOS}"

MDIR_SRC="${DL_MIRROR_OUTPUT_DIR}/Source"
mkdir -p "$MDIR_SRC"
MDIR_BIN="${DL_MIRROR_OUTPUT_DIR}/Binary"
mkdir -p "$MDIR_BIN"

LOGSDIR="${DL_MIRROR_LOG_DIR}"
from=$(get_from $rpms_list)
LOG="$LOGSDIR/L1_failmoved_url_${from}.log"
MISSING_SRPMS="$LOGSDIR/srpms_missing_${from}.log"
MISSING_RPMS="$LOGSDIR/rpms_missing_${from}.log"
FOUND_SRPMS="$LOGSDIR/srpms_found_${from}.log"
FOUND_RPMS="$LOGSDIR/rpms_found_${from}.log"
cat /dev/null > $LOG
cat /dev/null > $MISSING_SRPMS
cat /dev/null > $MISSING_RPMS
cat /dev/null > $FOUND_SRPMS
cat /dev/null > $FOUND_RPMS


if [ $CLEAN_LOGS_ONLY -eq 1 ];then
    exit 0
fi

if [ "$BASE_URL" == "" ]; then
    BASE_URL=file://$(readlink -f $(dirname ${rpms_list}))
fi

# Function to download different types of RPMs in different ways
download () {
    local _file=$1
    local _url=$2
    local _list=""
    local _from=""

    local _arch=""

    local rc=0
    local download_cmd=""
    local download_url=""
    local rpm_name=""
    local SFILE=""
    local lvl
    local dl_result

    _list=$(cat $_file)
    _from=$(get_from $_file)

    echo "now the rpm will come from: $_from"
    for ff in $_list; do
        _arch=$(get_arch_from_rpm $ff)
        rpm_name="$(get_rpm_name $ff)"
        dest_dir="$(get_dest_directory $_arch)"

        if [ ! -e $dest_dir/$rpm_name ]; then
            dl_result=1

            download_url="$_url/$rpm_name"
            download_cmd="curl --silent --output $rpm_name ${download_url}"

            echo "Looking for $rpm_name"
            echo "--> run: $download_cmd"
            if $download_cmd ; then
                SFILE="$(get_rpm_level_name $rpm_name L1)"
                process_result "$_arch" "$dest_dir" "$download_url" "$SFILE"
                dl_result=0
            else
                echo "Warning: $rpm_name not found"
            fi

            if [ $dl_result -eq 1 ]; then
                echo "Error: $rpm_name not found"
                echo "missing_srpm:$rpm_name" >> $LOG
                echo $rpm_name >> $MISSING_SRPMS
                rc=1
            fi
        else
            echo "Already have $dest_dir/$rpm_name"
        fi
        echo
    done

    return $rc
}

# Download files
if [ -s "$rpms_list" ];then
    echo "--> start searching $rpms_list"
    download $rpms_list $BASE_URL
    if [ $? -ne 0 ]; then
        dl_rc=1
    fi
fi

echo "Done!"

exit $dl_rc
