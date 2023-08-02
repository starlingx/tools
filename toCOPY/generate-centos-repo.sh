#!/bin/bash
#
# SPDX-License-Identifier: Apache-2.0
#
# Copyright (C) 2019 Intel Corporation
#

GENERATE_CENTOS_REPO_DIR="$(dirname "$(readlink -f "${BASH_SOURCE[0]}" )" )"

source $GENERATE_CENTOS_REPO_DIR/lst_utils.sh

mirror_dir=""
layer_dirs=""

CREATEREPO=$(which createrepo_c)
if [ $? -ne 0 ]; then
    CREATEREPO="createrepo"
fi

usage () {
    echo
    echo "Create a virtual rpm repo containing only rpms listed in various lst files."
    echo "The virtual repo contains only symlinks to to previously downloaded or built rpms."
    echo
    echo "Usage"
    echo
    echo "$0 [Options] [ --mirror-dir=<mirror-path> | <mirror-path> ]"
    echo
    echo "Commin Options:"
    echo "  --distro=<distro>:  Create repo for the designated distro."
    echo "                      Default 'centos'"
    echo "  --layer=<layer>:    Create a smaller repo, sufficient to build"
    echo "                      only the given layer."
    echo "                      Default: use the LAYER environmnet valiable, or 'all'."
    echo "  --mirror-dir=<dir>: Set the mirror directory.  This is where"
    echo "                      the previously downloaded rpms are located."
    echo
    echo "Override options: For use when working on a multi-layer change"
    echo "  --config-dir=<dir>: Use an alternate config directory rather than the"
    echo "                      system defined one"
    echo "  --layer-inc-url=<lower_layer>,<build_type>,<url>:"
    echo "                      Override the url for the image include file of a lower"
    echo "                      layer's build type.  Normally the url(s) is read from"
    echo "                      <config_dir>/<distro>/<layer>/required_layer_iso_inc.cfg"
    echo "                      This option can be used more than once."
    echo "  --layer-pkg-url=<lower_layer>,<build_type>,<url>:"
    echo "                      Override the url for the package list of a lower"
    echo "                      layer's build type.  Normally the url(s) is read from"
    echo "                      <config_dir>/<distro>/<layer>/required_layer_pkgs.cfg."
    echo "                      This option can be used more than once."
    echo "  --layer-wheels-inc-url=<lower_layer>,<stream>,<url>:"
    echo "                      Override the url for the image include file of a lower"
    echo "                      layer's build type.  Normally the url(s) is read from"
    echo "                      <config_dir>/<distro>/<layer>/required_layer_wheel_inc.cfg"
    echo "                      This option can be used more than once."
    echo "  --layer-dir=<dir>:  Look in provided dir for packages to link to."
    echo "                      This option can be used more than once."
    echo
}

cleanup () {
    if [ -e "${mirror_content}" ]; then
        \rm -f ${mirror_content}
    fi
    if [ -e "${TMP_LST_DIR}" ]; then
        \rm -rf ${TMP_LST_DIR}
    fi
}

trap "cleanup ; exit 1" INT HUP TERM QUIT
trap "cleanup" EXIT

if [ -z "$MY_REPO" ]; then
    echo "\$MY_REPO is not set. Ensure you are running this script"
    echo "from the container and \$MY_REPO points to the root of"
    echo "your folder tree."
    exit -1
fi

TEMP=$(getopt -o h --long help,config-dir:,distro:,layer:,layer-dir:,layer-inc-url:,layer-pkg-url:,layer-wheels-inc-url:,mirror-dir: -n 'generate-centos-repo' -- "$@")
if [ $? -ne 0 ]; then
    echo "getopt error"
    usage
    exit 1
fi
eval set -- "$TEMP"


while true ; do
    case "$1" in
        --mirror-dir)     mirror_dir=$2 ; shift 2 ;;
        --layer-dir)      layer_dirs+=" ${2/,/ }" ; shift 2 ;;
        --layer-inc-url)  set_layer_image_inc_urls "${2}" ; shift 2 ;;
        --layer-wheels-inc-url)  set_layer_wheels_inc_urls "${2}" ; shift 2 ;;
        --layer-pkg-url)  set_layer_pkg_urls "${2}" ; shift 2 ;;
        --config-dir)     set_and_validate_config_dir "${2}"; shift 2 ;;
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
echo
echo "layer_pkg_urls=${layer_pkg_urls[@]}"
echo
echo "layer_image_inc_urls=${layer_image_inc_urls[@]}"
echo
echo "layer_wheels_inc_urls=${layer_wheels_inc_urls[@]}"
echo

dest_dir=$MY_REPO/centos-repo
timestamp="$(date +%F_%H%M)"

mock_cfg_prefix="mock.cfg"
mock_cfg_default_suffix="proto"
mock_cfg_suffix="${mock_cfg_default_suffix}"
mock_cfg_distro=""
mock_cfg_release_prefix=${mock_cfg_prefix}
mock_cfg_dir=$MY_REPO/build-tools/repo_files
mock_cfg_dest_dir=$MY_REPO/centos-repo
if [ -f /etc/os-release ]; then
    mock_cfg_distro="$(source /etc/os-release; echo ${ID}${VERSION_ID})"
    if [ ! -z "${mock_cfg_distro}" ]; then
        mock_cfg_release_prefix=${mock_cfg_prefix}.${mock_cfg_distro}
    fi
fi
comps_xml_file=$MY_REPO/build-tools/repo_files/comps.xml
comps_xml_dest_dir=$MY_REPO/centos-repo/Binary

TMP_LST_DIR=$(mktemp -d /tmp/tmp_lst_dir_XXXXXX)
mkdir -p $TMP_LST_DIR
lst_file_dir="$TMP_LST_DIR"
inc_file_dir="${dest_dir}/layer_image_inc"
wheels_file_dir="${dest_dir}/layer_wheels_inc"
build_info_file_dir="${dest_dir}/layer_build_info"

rpm_lst_files="rpms_3rdparties.lst rpms_centos3rdparties.lst rpms_centos.lst"
rpm_lst_files_rt=""
other_lst_file="other_downloads.lst"

for template in $rpm_lst_files $other_lst_file; do
    lst="$lst_file_dir/${template}"
    merge_lst ${config_dir} ${distro} ${template} > ${lst}
done

missing_rpms_file=missing.txt

\rm -f ${missing_rpms_file}

# Strip trailing / from mirror_dir if it was specified...
mirror_dir=$(readlink -f ${mirror_dir} | sed "s%/$%%")

if [[ ( ! -d ${mirror_dir}/Binary ) || ( ! -d ${mirror_dir}/Source ) ]]; then
    echo "The mirror ${mirror_dir} doesn't has the Binary and Source"
    echo "folders. Please provide a valid mirror"
    exit -1
fi

for layer_dir in ${layer_dirs}; do
    if [ ! -d ${layer_dir} ]; then
        echo "The layer-dir ${layer_dir} doesn't exist"
        exit -1
    fi
done

if [ ! -d "${dest_dir}" ]; then
    mkdir -p "${dest_dir}"
fi

for t in "Binary" "Source" ; do
    target_dir=${dest_dir}/${t}

    if [ -d "${target_dir}" ]; then
        mv -f "${target_dir}" "${target_dir}-backup-${timestamp}"
    fi

    mkdir -p "${target_dir}"
done

#
# Dowload image inc files from layer_image_inc_urls
#
\rm -rf ${inc_file_dir}
mkdir -p ${inc_file_dir}
for key in "${!layer_image_inc_urls[@]}"; do
    lower_layer="${key%,*}"
    inc_type="${key#*,}"
    url="${layer_image_inc_urls[${key}]}"
    name_from_url=$(url_to_file_name "${url}")

    if [ "${inc_type}" == "std" ]; then
        ideal_name="${lower_layer}_${image_inc_from_layer_build_template}"
    elif [ "${inc_type}" == "dev" ]; then
        ideal_name="${lower_layer}_${dev_image_inc_from_layer_build_template}"
    else
        ideal_name="${lower_layer}_${inc_type}_${image_inc_from_layer_build_template}"
    fi

    list="${ideal_name}"

    for f in $(find -L ${layer_dirs} ${mirror_dir} -type f -name "${name_from_url}"); do
        cp $f ${inc_file_dir}/${list}
        if [ $? -ne 0 ]; then
            echo "WARNING: Failed to copy from cached file '$f' to satisfy url '${url}'"
        fi
    done

    if [ ! -f ${inc_file_dir}/${list} ]; then
        curl -L --silent --fail ${url} > ${inc_file_dir}/${list}
        if [ $? -ne 0 ]; then
            echo "ERROR: Failed to download from url '${url}'"
            exit 1
        fi
    fi
done

#
# Dowload wheels inc files from layer_wheels_inc_urls
#
\rm -rf ${wheels_file_dir}
mkdir -p ${wheels_file_dir}
for key in "${!layer_wheels_inc_urls[@]}"; do
    lower_layer="${key%,*}"
    stream="${key#*,}"
    url="${layer_wheels_inc_urls[${key}]}"
    name_from_url=$(url_to_file_name "${url}")

    ideal_name="${lower_layer}_${distro}_${stream}_${wheels_inc_from_layer_build_template}"

    list="${ideal_name}"

    for f in $(find -L ${layer_dirs} ${mirror_dir} -type f -name "${name_from_url}"); do
        cp $f ${wheels_file_dir}/${list}
        if [ $? -ne 0 ]; then
            echo "WARNING: Failed to copy from cached file '$f' to satisfy url '${url}'"
        fi
    done

    if [ ! -f ${wheels_file_dir}/${list} ]; then
        curl -L --silent --fail ${url} > ${wheels_file_dir}/${list}
        if [ $? -ne 0 ]; then
            echo "ERROR: Failed to download from url '${url}'"
            exit 1
        fi
    fi
done

#
# Dowload build info files
#
build_info_from_layer_build_template="BUILD_INFO"
\rm -rf ${build_info_file_dir}
mkdir -p ${build_info_file_dir}
for key in "${!layer_image_inc_urls[@]}"; do
    lower_layer="${key%,*}"
    inc_type="${key#*,}"

    if [ "${inc_type}" != "std" ]; then
        continue
    fi

    if [ "$(basename ${layer_image_inc_urls[${key}]})" != "image.inc" ]; then
        continue
    fi

    url=$( echo ${layer_image_inc_urls[${key}]} | sed 's#image.inc$#BUILD_INFO#' )
    name_from_url=$(url_to_file_name "${url}")
    ideal_name="${lower_layer}_${build_info_from_layer_build_template}"

    list="${ideal_name}"

    for f in $(find -L ${layer_dirs} ${mirror_dir} -type f -name "${name_from_url}"); do
        cp $f ${build_info_file_dir}/${list}
        if [ $? -ne 0 ]; then
            echo "WARNING: Failed to copy from cached file '$f' to satisfy url '${url}'"
        fi
    done

    if [ ! -f ${build_info_file_dir}/${list} ]; then
        curl -L --silent --fail ${url} > ${build_info_file_dir}/${list}
        if [ $? -ne 0 ]; then
            echo "WARNING: Failed to download from url '${url}'"
        fi
    fi
done


#
# Dowload lst files from layer_pkg_urls
#
for key in "${!layer_pkg_urls[@]}"; do
    lower_layer="${key%,*}"
    build_type="${key#*,}"
    url="${layer_pkg_urls[${key}]}"
    name_from_url=$(url_to_file_name "${url}")
    ideal_name="${lower_layer}_${build_type}_${rpms_from_layer_build_template}"
    list="${ideal_name}"

    for f in $(find -L ${layer_dirs} ${mirror_dir} -type f -name "${name_from_url}"); do
        cp $f ${lst_file_dir}/${list}
        if [ $? -ne 0 ]; then
            echo "WARNING: Failed to copy from cached file '$f' to satisfy url '${url}'"
        fi
    done

    if [ ! -f ${lst_file_dir}/${list} ]; then
        curl -L --silent --fail ${url} > ${lst_file_dir}/${list}
        if [ $? -ne 0 ]; then
            echo "ERROR: Failed to download from url '${url}'"
            exit 1
        fi
    fi

    if [ "${build_type}" == "rt" ]; then
        rpm_lst_files_rt+=" ${list}"
    else
        rpm_lst_files+=" ${list}"
    fi

    url_type=${url%%:*}
    if [ "${url_type}" == "file" ]; then
        url_dir=$(dirname ${url#file://})
        if [ ! -d ${url_dir} ]; then
            echo "ERROR: No such directory '${url_dir}' derived from url: ${url}"
            exit 1
        fi
        layer_dirs+=" ${url_dir}"
    fi
done

echo "rpm_lst_files=${rpm_lst_files}"
echo "rpm_lst_files_rt=${rpm_lst_files_rt}"
echo "layer_dirs=${layer_dirs}"

mirror_content=$(mktemp -t centos-repo-XXXXXX)
find -L ${layer_dirs} ${mirror_dir} -type f -name '*.rpm' > ${mirror_content}

sed_expression=""
for d in ${mirror_dir} ${layer_dirs}; do
    sed_expression+=" -e s%^${d}/%%"
done


process_lst_file () {
    local lst_file="${1}"
    local dest_dir="${2}"

    echo "process_lst_file: ${1} ${2}"
    grep -v "^#" ${lst_file_dir}/${lst_file} | while IFS="#" read rpmname extrafields; do
        if [ -z "${rpmname}" ]; then
            continue
        fi

        mirror_file=$(grep "/${rpmname}$" ${mirror_content} | head -n 1)
        if [ -z "${mirror_file}" ]; then
            echo "Error -- could not find requested ${rpmname} in ${mirror_dir}"
            echo ${rpmname} >> ${missing_rpms_file}
            continue
        fi

        # Great, we found the file!  Let's strip the mirror_dir prefix from it...
        ff=$(echo ${mirror_file} | sed ${sed_expression})
        f_name=$(basename "$ff")
        arch=$(echo ${f_name} | rev | cut -d '.' -f 2 | rev)
        if [ "${arch}" == "src" ]; then
            sub_dir="Source"
        else
            sub_dir="Binary/${arch}"
        fi

        # Make sure we have a subdir (so we don't symlink the first file as
        # the subdir name)
        mkdir -p ${dest_dir}/${sub_dir}

        # Link it!
        echo "Creating symlink for ${dest_dir}/${sub_dir}/${f_name}"
        ln -sf "${mirror_file}" "${dest_dir}/${sub_dir}/${f_name}"
        if [ $? -ne 0 ]; then
            echo "Failed ${mirror_file}: ln -sf \"${mirror_file}\" \"${dest_dir}/${sub_dir}\""
        fi
    done
}

#
# copy_with_backup: Copy a file to a directory or file.
#                   If the file already exists at the destination,
#                   a timestamped backup is created of the
#                   prior file content by adding a
#                   -backup-<timestamp> suffic to the file name.
#
# Usage:
#    copy_with_backup <src-file> <dest-dir>
#    copy_with_backup <src-file> <dest-file>
#
copy_with_backup () {
    local src_file="$1"
    local dest_dir="$2"
    local dest_file=${dest_dir}/$(basename ${src_file})

    if [ ! -f "${src_file}" ]; then
        echo "source file '${src_file}' does not exist!"
        exit 1
    fi

    if [ ! -d ${dest_dir} ]; then
        dest_file="$2"
        dest_dir=$(dirname ${dest_file})
        if [ ! -d ${dest_dir} ]; then
            echo "destination directory '${dest_dir}' does not exist!"
            exit 1
        fi
    fi

    if [ -f "${dest_file}" ]; then
        \mv -f -v "${dest_file}" "${dest_file}-backup-${timestamp}"
    fi

    \cp -v "${src_file}" "${dest_file}"
    if [ $? -ne 0 ]; then
        echo "failed to copy '${src_file} into directory '${dest_dir}'"
        exit 1
    fi
}

for lst_file in ${rpm_lst_files} ; do
    process_lst_file "${lst_file}" "${dest_dir}" || exit 1
done

for lst_file in ${rpm_lst_files_rt} ; do
    process_lst_file "${lst_file}" "${dest_dir}/rt" || exit 1
done


echo "Copying comps.xml file."

copy_with_backup ${comps_xml_file} ${comps_xml_dest_dir}


echo "Createing yum repodata."

for subdir in Source Binary; do
    repo_dir="${dest_dir}/${subdir}"
    mkdir -p "${repo_dir}"
    if [ -f "${repo_dir}/comps.xml" ]; then
        ${CREATEREPO} -g "${repo_dir}/comps.xml" -d "${repo_dir}"
    else
        ${CREATEREPO} -d "${repo_dir}"
    fi

    repo_dir="${dest_dir}/rt/${subdir}"
    mkdir -p "${repo_dir}"
    if [ -f "${repo_dir}/comps.xml" ]; then
        ${CREATEREPO} -g "${repo_dir}/comps.xml" -d "${repo_dir}"
    else
        ${CREATEREPO} -d "${repo_dir}"
    fi
done


echo "Copying mock.cfg.proto file."

#
# There are several mock.cfg.proto to choose from.
# They may be specific to release (e.g. centos7/8),
# specific to layer (e.g. distro), or both.
#

# First look for release specific, layer specific file to copy.
mock_cfg_file="${mock_cfg_dir}/${mock_cfg_release_prefix}.${layer}.${mock_cfg_suffix}"
if [ ! -f "${mock_cfg_file}" ]; then
    # Substitute release default, layer specific file to copy.
    mock_cfg_file="${mock_cfg_dir}/${mock_cfg_prefix}.${layer}.${mock_cfg_suffix}"
fi
if [ -f "${mock_cfg_file}" ]; then
    echo "copy_with_backup '${mock_cfg_file}' '${mock_cfg_dest_dir}/${mock_cfg_prefix}.${layer}.${mock_cfg_default_suffix}'"
    copy_with_backup "${mock_cfg_file}" "${mock_cfg_dest_dir}/${mock_cfg_prefix}.${layer}.${mock_cfg_default_suffix}"
fi

# Always copy the default (with respect to layer)
# First look for release specific, layer default file to copy.
mock_cfg_file="${mock_cfg_dir}/${mock_cfg_release_prefix}.${mock_cfg_suffix}"
if [ ! -f "${mock_cfg_file}" ]; then
    # Substitute release default, layer default file to copy.
    mock_cfg_file="${mock_cfg_dir}/${mock_cfg_prefix}.${mock_cfg_suffix}"
fi
echo "copy_with_backup '${mock_cfg_file}' '${mock_cfg_dest_dir}/${mock_cfg_prefix}.${mock_cfg_default_suffix}'"
copy_with_backup "${mock_cfg_file}" "${mock_cfg_dest_dir}/${mock_cfg_prefix}.${mock_cfg_default_suffix}"


echo "Copying contents from other list files."

# Populate the contents from other list files
cat ${lst_file_dir}/${other_lst_file} | grep -v "#" | while IFS=":" read targettype item extrafields; do
    if [ "${targettype}" == "folder" ]; then
        echo "Creating folder ${item}"
        mkdir -p $MY_REPO/centos-repo/Binary/${item}
    fi

    if [ "${targettype}" == "file" ]; then
        mkdir -p $MY_REPO/centos-repo/Binary/$(dirname ${item})
        echo "Creating symlink for $MY_REPO/centos-repo/Binary/${item}"
        ln -sf ${mirror_dir}/Binary/${item} $MY_REPO/centos-repo/Binary/${item}
    fi
done

echo "Done creating repo directory"
declare -i missing_rpms_file_count=$(wc -l ${missing_rpms_file} 2>/dev/null | awk '{print $1}')
if [ ${missing_rpms_file_count} -gt 0 ]; then
    echo "WARNING: Some targets could not be found.  Your repo may be incomplete."
    echo "Missing targets:"
    cat ${missing_rpms_file}
    exit 1
fi
