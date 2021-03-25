#!/bin/bash
#
# SPDX-License-Identifier: Apache-2.0
#

DOWNLOAD_MIRROR_DIR="$(dirname "$(readlink -f "${BASH_SOURCE[0]}" )" )"

source $DOWNLOAD_MIRROR_DIR/../toCOPY/lst_utils.sh

export DL_MIRROR_LOG_DIR="${DL_MIRROR_LOG_DIR:-./logs}"
export DL_MIRROR_OUTPUT_DIR="${DL_MIRROR_OUTPUT_DIR:-./output/stx/CentOS}"

cleanup () {
    if [ -e "${TMP_LST_DIR}" ]; then
        \rm -rf ${TMP_LST_DIR}
    fi
}

trap "cleanup ; exit 1" INT HUP TERM QUIT
trap "cleanup" EXIT

# Clear the error log before we begin
if [ -f $DL_MIRROR_LOG_DIR/errors ]; then
    rm -f $DL_MIRROR_LOG_DIR/errors
fi

# A temporary compatability step to save download time
# during the shift to the new DL_MIRROR_OUTPUT_DIR location.
#
# Relocate downloaded rpms from the old location to the new.
pike_dir="./output/stx-r1/CentOS/pike"
if [ -d $pike_dir ] && [ ! -d $DL_MIRROR_OUTPUT_DIR ]; then
    mkdir -p $(dirname $DL_MIRROR_OUTPUT_DIR)
    mv $pike_dir $DL_MIRROR_OUTPUT_DIR
    \rm -rf ./output/stx-r1
fi

usage() {
    echo "$0 [options]"
    echo
    echo "Common Options:"
    echo "  -c <yum.conf>: Use an alternate yum.conf rather than the system file"
    echo "                 Suggested valur is 'yum.conf.sample' in this directory."
    echo "                 (option passed on to subscripts when appropriate)"
    echo "  -d <distro>:   Download package to build designated distro. Default 'centos'"
    echo "  -g:            Do not change group IDs of downloaded artifacts"
    echo "  -l <layer>:    Download only packages required to build a given layer."
    echo "                 Default: use the LAYER environmnet variable, or 'all'."
    echo "  -n:            Do not use sudo when performing operations."
    echo "                 (option passed on to subscripts when appropriate)"
    echo
    echo "Download Source Options:  Only select one of these."
    echo "  -s: Download from StarlingX mirror only"
    echo "  -S: Download from StarlingX mirror, upstream as backup (default)"
    echo "  -u: Download from original upstream sources only"
    echo "  -U: Download from original upstream sources, StarlingX mirror as backup"
    echo
    echo "Layered Build Options:   For use when building multiple layers locally."
    echo "  -C <config_dir>: Use an alternate config directory rather than the system"
    echo "                   defined one"
    echo "  -I <lower_layer>,<build_type>,<url>:"
    echo "                   Override the url for the image include file of a lower"
    echo "                   layer's build type.  Normally the url(s) is read from"
    echo "                   <config_dir>/<distro>/<layer>/required_layer_iso_inc.cfg"
    echo "                   This option can be used more than once."
    echo "  -L <lower_layer>,<build_type>,<url>:"
    echo "                   Override the url for the package list of a lower"
    echo "                   layer's build type.  Normally the url(s) is read from"
    echo "                   <config_dir>/<distro>/<layer>/required_layer_pkgs.cfg."
    echo "                   This option can be used more than once."
    echo "  -W <lower_layer>,<stream>,<url>:"
    echo "                   Override the url for the wheels.inc list of a lower"
    echo "                   layer's build type.  Normally the url(s) is read from"
    echo "                   <config_dir>/<distro>/<layer>/required_layer_wheel_inc.cfg."
    echo "                   This option can be used more than once."
    echo
}

generate_log_name() {
    filename=$1
    level=$2
    base=$(basename $filename .lst)
    echo $LOGSDIR"/"$base"_download_"$level".log"
}

need_file(){
    for f in $*; do
        if [ ! -f $f ]; then
            echo "ERROR: File $f does not exist."
            exit 1
        fi
    done
}

make_if_needed_file(){
    for f in $*; do
        if [ ! -f $f ]; then
            echo "Creating empty file '$f'"
            touch $f
        fi
    done
}

need_dir(){
    for d in $*; do
        if [ ! -d $d ]; then
            echo "ERROR: Directory $d does not exist."
            exit 1
        fi
    done
}

# Downloader scripts
rpm_downloader="${DOWNLOAD_MIRROR_DIR}/dl_rpms.sh"
lower_layer_rpm_downloader="${DOWNLOAD_MIRROR_DIR}/dl_lower_layer_rpms.sh"
rpm_from_url_downloader="${DOWNLOAD_MIRROR_DIR}/dl_rpms_from_url.sh"
tarball_downloader="${DOWNLOAD_MIRROR_DIR}/dl_tarball.sh"
other_downloader="${DOWNLOAD_MIRROR_DIR}/dl_other_from_centos_repo.sh"
make_stx_mirror_yum_conf="${DOWNLOAD_MIRROR_DIR}/make_stx_mirror_yum_conf.sh"

# track optional arguments
change_group_ids=1
use_system_yum_conf=0
alternate_yum_conf="${DOWNLOAD_MIRROR_DIR}/yum.conf.sample"
alternate_repo_dir=""
rpm_downloader_extra_args=""
tarball_downloader_extra_args=""
make_stx_mirror_yum_conf_extra_args=""


# lst files to use as input
rpms_from_3rd_parties_template="rpms_3rdparties.lst"
rpms_from_centos_repo_template="rpms_centos.lst"
rpms_from_centos_3rd_parties_template="rpms_centos3rdparties.lst"
rpms_from_layer_build_dir=${DL_MIRROR_OUTPUT_DIR}/layer_pkg_lists
rpms_from_layer_repos_dir=${DL_MIRROR_OUTPUT_DIR}/layer_repos
image_inc_from_layer_build_dir=${DL_MIRROR_OUTPUT_DIR}/layer_image_inc
wheels_inc_from_layer_build_dir=${DL_MIRROR_OUTPUT_DIR}/layer_wheels_inc
build_info_from_layer_build_dir=${DL_MIRROR_OUTPUT_DIR}/layer_build_info
tarball_downloads_template="tarball-dl.lst"
other_downloads_template="other_downloads.lst"

# Overall success
success=1

SUDO=sudo

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

dl_from_stx () {
    local re="\\b$dl_from_stx_mirror\\b"
    [[ "$dl_source" =~ $re ]]
}

dl_from_upstream () {
    local re="\\b$dl_from_upstream\\b"
    [[ "$dl_source" =~ $re ]]
}


MULTIPLE_DL_FLAG_ERROR_MSG="Error: Please use only one of: -s,-S,-u,-U"
TEMP_DIR=""
TEMP_DIR_CLEANUP=""

multiple_dl_flag_check () {
    if [ "$dl_flag" != "" ]; then
        echo "$MULTIPLE_DL_FLAG_ERROR_MSG"
        usage
        exit 1
    fi
}


# Parse out optional arguments
while getopts "c:Cd:ghI:sl:L:nt:ySuUW:" o; do
    case "${o}" in
        c)
            # Pass -c ("use alternate yum.conf") to rpm downloader
            use_system_yum_conf=0
            alternate_yum_conf="${OPTARG}"
            ;;
        C)
            # Alternate config directory
            set_and_validate_config_dir "${OPTARG}"
            ;;
        d)
            # Alternate distro
            set_and_validate_distro "${OPTARG}"
            ;;
        g)
            # Do not attempt to change group IDs on downloaded packages
            change_group_ids=0
            ;;
        I)
            set_layer_image_inc_urls "${OPTARG}"
            ;;
        W)
            set_layer_wheels_inc_urls "${OPTARG}"
            ;;
        l)
            # layer
            set_and_validate_layer "${OPTARG}"
            ;;
        L)
            set_layer_pkg_urls "${OPTARG}"
            ;;
        n)
            # Pass -n ("no-sudo") to rpm downloader
            rpm_downloader_extra_args="${rpm_downloader_extra_args} -n"
            SUDO=""
            ;;
        t)
            # Set TEMP_DIR
            TEMP_DIR="${OPTARG}"
            ;;
        y)
            # Use hosts /etc/yum.conf
            use_system_yum_conf=1
            alternate_yum_conf=""
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
        h)
            # Help
            usage
            exit 0
            ;;
        *)
            usage
            exit 1
            ;;
    esac
done
shift $((OPTIND-1))


TMP_LST_DIR=$(mktemp -d /tmp/tmp_lst_dir_XXXXXX)
mkdir -p $TMP_LST_DIR
rpms_from_3rd_parties="$TMP_LST_DIR/${rpms_from_3rd_parties_template}"
rpms_from_centos_repo="$TMP_LST_DIR/${rpms_from_centos_repo_template}"
rpms_from_centos_3rd_parties="$TMP_LST_DIR/${rpms_from_centos_3rd_parties_template}"
tarball_downloads="$TMP_LST_DIR/${tarball_downloads_template}"
other_downloads="$TMP_LST_DIR/${other_downloads_template}"

merge_lst ${config_dir} ${distro} ${rpms_from_3rd_parties_template} > ${rpms_from_3rd_parties}
merge_lst ${config_dir} ${distro} ${rpms_from_centos_repo_template} > ${rpms_from_centos_repo}
merge_lst ${config_dir} ${distro} ${rpms_from_centos_3rd_parties_template} > ${rpms_from_centos_3rd_parties}
merge_lst ${config_dir} ${distro} ${tarball_downloads_template} > ${tarball_downloads}
merge_lst ${config_dir} ${distro} ${other_downloads_template} > ${other_downloads}

echo "--------------------------------------------------------------"

echo "WARNING: this script HAS TO access internet (http/https/ftp),"
echo "so please make sure your network working properly!!"


LOGSDIR="logs"
mkdir -p $LOGSDIR


# Check extistence of prerequisites files
need_file ${rpm_downloader} ${other_downloader} ${tarball_downloader}
make_if_needed_file ${rpms_from_3rd_parties}
make_if_needed_file ${rpms_from_centos_3rd_parties}
make_if_needed_file ${rpms_from_centos_repo}
make_if_needed_file ${other_downloads}
make_if_needed_file ${tarball_downloads}

#
# Dowlnoad package lst files, image inc files and build info files for lower layers.
#
# Also it may set up extra arguements for make_stx_mirror_yum_conf that
# will exploy yum repos co-resident with the lst file.
#
\rm -rf ${rpms_from_layer_build_dir}
mkdir -p ${rpms_from_layer_build_dir}

for key in "${!layer_pkg_urls[@]}"; do
    lower_layer="${key%,*}"
    build_type="${key#*,}"
    url="${layer_pkg_urls[${key}]}"
    name_from_url=$(url_to_file_name $url)
    list="${rpms_from_layer_build_dir}/${name_from_url}"
    curl --silent --fail ${url} > ${list} ||
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to download from url: ${url}"
        exit 1
    fi

    #
    # If the lst file is co-resident with a yum repodata directory,
    # then add arguements for our call to make_stx_mirror_yum_conf
    # so that we'll use that repo.
    #
    url_type=${url%%:*}
    if [ "${url_type}" == "file" ]; then
        base_url=$(dirname $url)
        repomod_url=${base_url}/repodata/repomd.xml
        curl --silent --fail --output /dev/null ${repomod_url} ||
        if [ $? -ne 0 ]; then
            echo "ERROR: Failed to download from url: ${url}"
            exit 1
        fi
        make_stx_mirror_yum_conf_extra_args+=" -u ${lower_layer},${build_type},${base_url}"
    fi
done

\rm -rf ${image_inc_from_layer_build_dir}
mkdir -p ${image_inc_from_layer_build_dir}

for key in "${!layer_image_inc_urls[@]}"; do
    lower_layer="${key%,*}"
    inc_type="${key#*,}"
    url="${layer_image_inc_urls[${key}]}"
    name_from_url=$(url_to_file_name $url)
    list="${image_inc_from_layer_build_dir}/${name_from_url}"
    curl --silent --fail ${url} > ${list} ||
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to download from url: ${url}"
        exit 1
    fi
done

\rm -rf ${wheels_inc_from_layer_build_dir}
mkdir -p ${wheels_inc_from_layer_build_dir}

for key in "${!layer_wheels_inc_urls[@]}"; do
    lower_layer="${key%,*}"
    stream="${key#*,}"
    url="${layer_wheels_inc_urls[${key}]}"
    name_from_url=$(url_to_file_name $url)
    list="${wheels_inc_from_layer_build_dir}/${name_from_url}"
    curl --silent --fail ${url} > ${list} ||
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to download from url: ${url}"
        exit 1
    fi
done

\rm -rf ${build_info_from_layer_build_dir}
mkdir -p ${build_info_from_layer_build_dir}

# Borrow std image.inc url as a proxy for the BUILD_INFO with a simple substitution
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
    name_from_url=$(url_to_file_name $url)
    dest="${build_info_from_layer_build_dir}/${name_from_url}"
    curl --silent --fail ${url} > ${dest} ||
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to download from url: ${url}"
        exit 1
    fi
done


echo "step #0: Configuring yum repos ..."

if [ ${use_system_yum_conf} -ne 0 ]; then
    # Restore StarlingX_3rd repos from backup
    REPO_DIR=/etc/yum.repos.d

    if [ $layer != "all" ]; then
        if [ -d ${config_dir}/${distro}/${layer}/yum.repos.d ]; then
            ${SUDO} \cp -f -v ${config_dir}/${distro}/${layer}/yum.repos.d/*.repo $REPO_DIR/
        fi
    else
        # copy all layers
        ${SUDO} \cp -f -v ${config_dir}/${distro}/*/yum.repos.d/*.repo $REPO_DIR/
    fi
fi

if [ $use_system_yum_conf -eq 0 ]; then
    need_file "${alternate_yum_conf}"
    if [ "$alternate_repo_dir" == "" ]; then
        alternate_repo_dir=$(grep '^reposdir=' "${alternate_yum_conf}" | cut -d '=' -f 2)
        if [ "$alternate_repo_dir" == "" ]; then
            alternate_repo_dir="$(dirname "${alternate_yum_conf}"/yum.repos.d)"
        fi
        if [[ $alternate_repo_dir != /* ]]; then
            # Path is relative, so prefix with directory where yum.conf lives
            alternate_repo_dir=$(dirname ${alternate_yum_conf})/${alternate_repo_dir}
        fi
        need_dir "${alternate_repo_dir}"
    fi
fi

rpm_downloader_extra_args="${rpm_downloader_extra_args} -D $distro"

if [ "$dl_flag" != "" ]; then
    # Pass dl_flag on to the rpm_downloader script
    rpm_downloader_extra_args="${rpm_downloader_extra_args} $dl_flag"
fi

if ! dl_from_stx; then
    # Not using stx mirror
    if [ $use_system_yum_conf -eq 0 ]; then
        # Use provided yum.conf unaltered.
        rpm_downloader_extra_args="${rpm_downloader_extra_args} -c ${alternate_yum_conf}"
    fi
else
    # We want to use stx mirror, so we need to create a new, modified yum.conf and yum.repos.d.
    # The modifications will add or substitute repos pointing to the StralingX mirror.
    if [ "$TEMP_DIR" == "" ]; then
        if [ "$MY_WORKSPACE" != "" ]; then
            TEMP_DIR="$MY_WORKSPACE/tmp/yum"
        else
            TEMP_DIR=$(mktemp -d /tmp/stx_mirror_XXXXXX)
            TEMP_DIR_CLEANUP="y"
        fi
    fi

    if [ ! -d $TEMP_DIR ]; then
        mkdir -p ${TEMP_DIR}
    fi

    TEMP_CONF="$TEMP_DIR/yum.conf"
    need_file ${make_stx_mirror_yum_conf}
    need_dir ${TEMP_DIR}

    if [ $use_system_yum_conf -eq 0 ]; then
        # Modify user provided yum.conf.  We expect ir to have a 'reposdir=' entry to
        # point to the repos that need to be modified as well.
        if dl_from_upstream; then
            # add
            echo "${make_stx_mirror_yum_conf} -R -d $TEMP_DIR -y $alternate_yum_conf -r $alternate_repo_dir -D $distro -l $layer ${make_stx_mirror_yum_conf_extra_args}"
            ${make_stx_mirror_yum_conf} -R -d $TEMP_DIR -y $alternate_yum_conf -r $alternate_repo_dir -D $distro -l $layer ${make_stx_mirror_yum_conf_extra_args}
        else
            # substitute
            echo "${make_stx_mirror_yum_conf} -d $TEMP_DIR -y $alternate_yum_conf -r $alternate_repo_dir -D $distro -l $layer ${make_stx_mirror_yum_conf_extra_args}"
            ${make_stx_mirror_yum_conf} -d $TEMP_DIR -y $alternate_yum_conf -r $alternate_repo_dir -D $distro -l $layer ${make_stx_mirror_yum_conf_extra_args}
        fi
    else
        # Modify system yum.conf and yum.repos.d.  Remember that we expect to run this
        # inside a container, and the system yum.conf has like been modified else where
        # in these scripts.
        if dl_from_upstream; then
            # add
            echo "${make_stx_mirror_yum_conf} -R -d $TEMP_DIR -y /etc/yum.conf -r /etc/yum.repos.d -D $distro -l $layer ${make_stx_mirror_yum_conf_extra_args}"
            ${make_stx_mirror_yum_conf} -R -d $TEMP_DIR -y /etc/yum.conf -r /etc/yum.repos.d -D $distro -l $layer ${make_stx_mirror_yum_conf_extra_args}
        else
            # substitute
            echo "${make_stx_mirror_yum_conf} -d $TEMP_DIR -y /etc/yum.conf -r /etc/yum.repos.d -D $distro -l $layer ${make_stx_mirror_yum_conf_extra_args}"
            ${make_stx_mirror_yum_conf} -d $TEMP_DIR -y /etc/yum.conf -r /etc/yum.repos.d -D $distro -l $layer ${make_stx_mirror_yum_conf_extra_args}
        fi
    fi

    rpm_downloader_extra_args="${rpm_downloader_extra_args} -c $TEMP_CONF"
fi

#download RPMs/SRPMs from lower layer builds
echo "step #1: start downloading RPMs/SRPMs from lower layer builds..."
retcode=0
for key in "${!layer_pkg_urls[@]}"; do
    lower_layer="${key%,*}"
    build_type="${key#*,}"
    url="${layer_pkg_urls[${key}]}"
    name_from_url=$(url_to_file_name $url)
    list="${rpms_from_layer_build_dir}/${name_from_url}"

    url_type=${url%%:*}
    if [ "${url_type}" == "file" ]; then
        level=L1
        logfile=$(generate_log_name $list level)
        $rpm_from_url_downloader -u $(dirname $url) $list |& tee $logfile
        local_retcode=${PIPESTATUS[0]}
    else
        #download RPMs/SRPMs from CentOS repos by "yumdownloader"
        level=L1
        logfile=$(generate_log_name $list $level)
        if ! dl_from_stx; then
            # Not using stx mirror
            if [ $use_system_yum_conf -eq 0 ]; then
                # Use provided yum.conf unaltered.
                llrd_extra_args="-c ${alternate_yum_conf}"
            fi
        else
            llrd_extra_args="-c ${TEMP_DIR}/yum.conf"
        fi
        echo "$lower_layer_rpm_downloader -l ${lower_layer} -b ${build_type} -r $(dirname $url) ${llrd_extra_args} ${list} ${level}"
        $lower_layer_rpm_downloader -l ${lower_layer} -b ${build_type} -r $(dirname $url) ${llrd_extra_args} ${list} ${level} |& tee $logfile
        local_retcode=${PIPESTATUS[0]}
    fi

    if [ $local_retcode -ne 0 ]; then
        echo "ERROR: Something wrong with downloading files listed in $list."
        echo "   Please check the log at $(pwd)/$logfile !"
        echo ""
        success=0
        retcode=$local_retcode
    fi
done

if [ $retcode -eq 0 ];then
    echo "step #1: done successfully"
else
    echo "step #1: finished with errors"
fi


#download RPMs/SRPMs from 3rd_party websites (not CentOS repos) by "wget"
echo "step #2: start downloading RPMs/SRPMs from 3rd-party websites..."
list=${rpms_from_3rd_parties}
level=L1
logfile=$(generate_log_name $list $level)
$rpm_downloader ${rpm_downloader_extra_args} $list $level |& tee $logfile
retcode=${PIPESTATUS[0]}
if [ $retcode -ne 0 ];then
    echo "ERROR: Something wrong with downloading files listed in $list."
    echo "   Please check the log at $(pwd)/$logfile !"
    echo ""
    success=0
fi

# download RPMs/SRPMs from 3rd_party repos by "yumdownloader"
list=${rpms_from_centos_3rd_parties}
level=L1
logfile=$(generate_log_name $list $level)
$rpm_downloader ${rpm_downloader_extra_args} $list $level |& tee $logfile
retcode=${PIPESTATUS[0]}
if [ $retcode -eq 0 ];then
    echo "step #2: done successfully"
else
    echo "step #2: finished with errors"
    echo "ERROR: Something wrong with downloading files listed in $list."
    echo "   Please check the log at $(pwd)/$logfile !"
    echo ""
    echo "step #2: finished with errors"
    success=0
fi

if [ ${use_system_yum_conf} -eq 1 ]; then
    # deleting the StarlingX_3rd to avoid pull centos packages from the 3rd Repo.
    ${SUDO} \rm -f $REPO_DIR/StarlingX_3rd*.repo
    ${SUDO} \rm -f $REPO_DIR/StarlingX_cengn*.repo
    if [ "$TEMP_DIR" != "" ]; then
        ${SUDO} \rm -f $TEMP_DIR/yum.repos.d/StarlingX_3rd*.repo
        ${SUDO} \rm -f $TEMP_DIR/yum.repos.d/StarlingX_cengn*.repo
    fi
fi

echo "step #3: start 1st round of downloading RPMs and SRPMs with L1 match criteria..."
#download RPMs/SRPMs from CentOS repos by "yumdownloader"
list=${rpms_from_centos_repo}
level=L1
logfile=$(generate_log_name $list $level)
$rpm_downloader ${rpm_downloader_extra_args} $list $level |& tee $logfile
retcode=${PIPESTATUS[0]}


K1_logfile=$(generate_log_name ${rpms_from_centos_repo} K1)
if [ $retcode -ne 1 ]; then
    # K1 step not needed. Clear any K1 logs from previous download attempts.
    $rpm_downloader -x $LOGSDIR/L1_rpms_missing_centos.log K1 |& tee $K1_logfile
fi

if [ $retcode -eq 0 ]; then
    echo "finish 1st round of RPM downloading successfully!"
elif [ $retcode -eq 1 ]; then
    echo "finish 1st round of RPM downloading with missing files!"
    if [ -e "$LOGSDIR/L1_rpms_missing_centos.log" ]; then

        echo "start 2nd round of downloading Binary RPMs with K1 match criteria..."
        $rpm_downloader ${rpm_downloader_extra_args} $LOGSDIR/L1_rpms_missing_centos.log K1 centos |& tee $K1_logfile
        retcode=${PIPESTATUS[0]}
        if [ $retcode -eq 0 ]; then
            echo "finish 2nd round of RPM downloading successfully!"
        elif [ $retcode -eq 1 ]; then
            echo "finish 2nd round of RPM downloading with missing files!"
            if [ -e "$LOGSDIR/rpms_missing_K1.log" ]; then
                echo "WARNING: missing RPMs listed in $LOGSDIR/centos_rpms_missing_K1.log !"
            fi
        fi

        # Remove files found by K1 download from L1_rpms_missing_centos.txt to prevent
        # false reporting of missing files.
        grep -v -x -F -f $LOGSDIR/K1_rpms_found_centos.log $LOGSDIR/L1_rpms_missing_centos.log  > $LOGSDIR/L1_rpms_missing_centos.tmp || true
        mv -f $LOGSDIR/L1_rpms_missing_centos.tmp $LOGSDIR/L1_rpms_missing_centos.log


        missing_num=`wc -l $LOGSDIR/K1_rpms_missing_centos.log | cut -d " " -f1-1`
        if [ "$missing_num" != "0" ];then
            echo "ERROR:  -------RPMs missing: $missing_num ---------------"
            retcode=1
        fi
    fi

    if [ -e "$LOGSDIR/L1_srpms_missing_centos.log" ]; then
        missing_num=`wc -l $LOGSDIR/L1_srpms_missing_centos.log | cut -d " " -f1-1`
        if [ "$missing_num" != "0" ];then
            echo "ERROR: --------- SRPMs missing: $missing_num ---------------"
            retcode=1
        fi
    fi
fi

if [ $retcode -eq 0 ];then
    echo "step #3: done successfully"
else
    echo "ERROR: Something wrong with downloading files listed in ${rpms_from_centos_repo}."
    echo "   Please check the logs at $(pwd)/$logfile"
    echo "   and $(pwd)/logs/$K1_logfile !"
    echo ""
    echo "step #3: finished with errors"
    success=0
fi

## verify all RPMs SRPMs we download for the GPG keys
find ./output -type f -name "*.rpm" | xargs rpm -K | grep -i "MISSING KEYS" > $LOGSDIR/rpm-gpg-key-missing.txt || true

# remove all i686.rpms to avoid pollute the chroot dep chain
find ./output -name "*.i686.rpm" | tee $LOGSDIR/all_i686.txt
find ./output -name "*.i686.rpm" | xargs rm -f

# Count unique rpms.  Strip extra fields from 'rpms_from_3rd_partiesIgnore',
# commented out entries, and blank lines.
total_line=$(sed 's/#.*//'  ${rpms_from_3rd_parties} \
                            ${rpms_from_centos_repo} \
                            ${rpms_from_centos_3rd_parties} \
                | grep -v '^$' \
                | sort --unique \
                | wc -l)
echo "We expected to download $total_line RPMs."
num_of_downloaded_rpms=$(find ./output -type f -name "*.rpm" | wc -l | cut -d" " -f1-1)
echo "There are $num_of_downloaded_rpms RPMs in output directory."
if [ "$total_line" != "$num_of_downloaded_rpms" ]; then
    echo "WARNING: Not the same number of RPMs in output as RPMs expected to be downloaded, need to check outputs and logs."
fi

if [ $change_group_ids -eq 1 ]; then
    # change "./output" and sub-folders to 751 (cgcs) group
    NEW_UID=$(id -u)
    NEW_GID=751
    ${SUDO} chown  ${NEW_UID}:${NEW_GID} -R ./output
fi

echo "step #4: start downloading other files ..."

logfile=$LOGSDIR"/otherfiles_centos_download.log"
${other_downloader} ${dl_flag} -D "$distro" ${other_downloads} ${DL_MIRROR_OUTPUT_DIR}/Binary/ |& tee $logfile
retcode=${PIPESTATUS[0]}
if [ $retcode -eq 0 ];then
    echo "step #4: done successfully"
else
    echo "step #4: finished with errors"
    echo "ERROR: Something wrong with downloading from ${other_downloads}."
    echo "   Please check the log at $(pwd)/$logfile!"
    echo ""
    success=0
fi


# StarlingX requires a group of source code pakages, in this section
# they will be downloaded.
echo "step #5: start downloading tarball compressed files"
logfile=$LOGSDIR"/tarballs_download.log"
${tarball_downloader} ${dl_flag} -D "$distro" ${tarball_downloader_extra_args} ${tarball_downloads} |& tee $logfile
retcode=${PIPESTATUS[0]}
if [ $retcode -eq 0 ];then
    echo "step #5: done successfully"
else
    echo "step #5: finished with errors"
    echo "ERROR: Something wrong with downloading tarballs."
    echo "   Please check the log at $(pwd)/$logfile !"
    echo ""
    success=0
fi


#
# Clean up the mktemp directory, if required.
#
if [ "$TEMP_DIR" != "" ] && [ "$TEMP_DIR_CLEANUP" == "y" ]; then
    echo "${SUDO} rm -rf $TEMP_DIR"
    ${SUDO} \rm -rf "$TEMP_DIR"
fi

echo "IMPORTANT: The following 3 files are just bootstrap versions. Based"
echo "on them, the workable images for StarlingX could be generated by"
echo "running \"update-pxe-network-installer\" command after \"build-iso\""
echo "    - ${DL_MIRROR_OUTPUT_DIR}/Binary/LiveOS/squashfs.img"
echo "    - ${DL_MIRROR_OUTPUT_DIR}/Binary/images/pxeboot/initrd.img"
echo "    - ${DL_MIRROR_OUTPUT_DIR}/Binary/images/pxeboot/vmlinuz"

echo ""
if [ $success -ne 1 ]; then
    echo "Warning: Not all download steps succeeded.  You are likely missing files."
    exit 1
fi

echo "Success"
exit 0
