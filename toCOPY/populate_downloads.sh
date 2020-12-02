#!/bin/bash
#
# SPDX-License-Identifier: Apache-2.0
#

POPULATE_DOWNLOADS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE[0]}" )" )"

source $POPULATE_DOWNLOADS_DIR/lst_utils.sh

usage () {
    echo
    echo "Create a virtual downloads directory containing only files (likely tarballs) listed in various lst files."
    echo "The virtual directory contains only symlinks to to previously downloaded tarballs/files."
    echo
    echo "$0 [--config-dir=<dir>] [--distro=<distro>] [--layer=<layer>] [ --mirror-dir=<mirror-path> | <mirror-path> ]"
    echo
    echo "  --config-dir=<dir>: Use an alternate config directory rather than the system defined one"
    echo "  --distro=<distro>: Set distro we intend to build.  Default 'centos'"
    echo "  --layer=<layer>: Set layer we intend to build.  Default: use the LAYER environmnet valiable, or 'all'."
    echo "  --mirror-dir=<dir>: Set the mirror directory.  This is where the previously download tarballs are located."
}

cleanup () {
    if [ -e "${TMP_LST_DIR}" ]; then
        \rm -rf ${TMP_LST_DIR}
    fi
}

trap "cleanup ; exit 1" INT HUP TERM QUIT
trap "cleanup" EXIT

mirror_dir=""

if [ -z "$MY_REPO" ]; then
    echo "\$MY_REPO is not set. Ensure you are running this script"
    echo "from the container and \$MY_REPO points to the root of"
    echo "your folder tree."
    exit -1
fi

TEMP=$(getopt -o h --long help,config-dir:,distro:,layer:,mirror-dir: -n 'populate_downloads' -- "$@")
if [ $? -ne 0 ]; then
    echo "getopt error"
    usage
    exit 1
fi
eval set -- "$TEMP"

while true ; do
    case "$1" in
        --mirror-dir)     mirror_dir=$2 ; shift 2 ;;
        --config-dir)     config_dir="${2}"; shift 2 ;;
        --distro)         set_and_validate_distro "${2}"; shift 2 ;;
        --layer)          set_and_validate_layer "${2}"; shift 2 ;;
        -h|--help)        echo "help"; usage; exit 0 ;;
        --)               shift ; break ;;
        *)                usage; exit 1 ;;
    esac
done

if [ "$mirror_dir" == "" ]; then
    if [ $# -ne 1 ]; then
        usage
        exit -1
    fi

    mirror_dir=$1
fi

echo "mirror_dir=${mirror_dir}"
echo "config_dir=${config_dir}"
echo "distro=${distro}"
echo "layer=${layer}"

tarball_downloads_template="tarball-dl.lst"
extra_downloads_template="extra_downloads.lst"

TMP_LST_DIR=$(mktemp -d /tmp/tmp_lst_dir_XXXXXX)
mkdir -p $TMP_LST_DIR

tarball_lst="$TMP_LST_DIR/${tarball_downloads_template}"
extra_downloads_lst="$TMP_LST_DIR/${extra_downloads_template}"
merge_lst ${config_dir} ${distro} ${tarball_downloads_template} > ${tarball_lst}
merge_lst ${config_dir} ${distro} ${extra_downloads_template} > ${extra_downloads_lst}

downloads_dir=${MY_REPO}/stx/downloads

extra_downloads=""
if [ -f  ${extra_downloads_lst} ]; then
    extra_downloads="$(grep -v '^#' ${extra_downloads_lst})"
fi


mkdir -p ${MY_REPO}/stx/downloads

grep -v "^#" ${tarball_lst} | while read x; do
    if [ -z "$x" ]; then
        continue
    fi

    # Get first element of item & strip leading ! if appropriate
    tarball_file=$(echo $x | sed "s/#.*//" | sed "s/^!//")

    # put the file in downloads
    source_file=$(find ${mirror_dir}/downloads -name "${tarball_file}")
    if [ -z ${source_file} ]; then
        echo "Could not find ${tarball_file}"
    else
        rel_path=$(echo ${source_file} | sed "s%^${mirror_dir}/downloads/%%")
        rel_dir_name=$(dirname ${rel_path})
        if [ ! -e ${downloads_dir}/${rel_dir_name}/${tarball_file} ]; then
            mkdir -p ${downloads_dir}/${rel_dir_name}
            echo "Creating symlink for $(basename ${source_file})"
            ln -sf ${source_file} ${downloads_dir}/${rel_dir_name}/
        else
            echo "Already have symlink for $(basename ${source_file})"
        fi
    fi
done

for x in ${extra_downloads}; do
    ln -sf ${mirror_dir}/downloads/$x ${downloads_dir}
done
