#
# SPDX-License-Identifier: Apache-2.0
#
# Copyright (C) 2019 Intel Corporation
#

UTILS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE[0]}" )" )"

: ${_CURL_OPTS="--fail --location --connect-timeout 15 --speed-time 15 --speed-limit 1 --retry 5"}

source $UTILS_DIR/url_utils.sh || exit 1

get_yum_command() {
    local _file=$1
    local _level=$2
    local rpm_name=""
    local arr=( $(split_filename $_file) )
    local arch=${arr[3]}
    local yumdownloader_extra_opts=""
    rpm_name="$(get_rpm_level_name $_file $_level)"

    if [ "$arch" == "src" ]; then
        yumdownloader_extra_opts="--source"
    else
        yumdownloader_extra_opts="--exclude='*.i686' --archlist=noarch,x86_64"
    fi

    echo "${SUDO} yumdownloader -q -C ${YUMCONFOPT} ${RELEASEVER} $yumdownloader_extra_opts $rpm_name"
}

# Usage: get_download_file_command [--quiet] [--timestamps] URL [OUTPUT_FILE]
get_download_file_command() {
    local _opts="$_CURL_OPTS"
    while true ; do
        case "$1" in
            --quiet)      _opts+=" --silent --show-error" ;;
            --timestamps) _opts+=" --remote-time" ;;
            -*)
                echo >&2 "Unknown option $1"
                return 1
                ;;
            *)
                break
        esac
        shift
    done

    local _name="$1"
    local _ret=""
    if [[ $# -gt 1 ]]; then
        _opts+=" -o $2"
    else
        _opts+=" -O"
    fi
    if [[ "$_name" == http?(s)://* ]]; then
        _ret="curl -L $_opts $_name"
    else
        _ret="curl -L $_opts $(koji_url $_name)"
    fi
    echo "$_ret"
}

# Usage: download_file [--quiet] [--timestamps] URL [OUTPUT_FILE]
download_file() {
    local _opts="$_CURL_OPTS"
    local _dest_file=""
    while true ; do
        case "$1" in
            --quiet)      _opts+=" --silent --show-error" ;;
            --timestamps) _opts+=" --remote-time" ;;
            -*)
                echo >&2 "Unknown option $1"
                return 1
                ;;
            *)
                break
        esac
        shift
    done
    if [[ "$#" -gt 1 ]] ; then
        _dest_file="$2"
    else
        _dest_file="$(basename "$1")"
    fi
    if curl -L $_opts -o "${_dest_file}.dl_part" "$1" ; then
        \mv -fT "${_dest_file}.dl_part" "${_dest_file}"
        return 0
    fi
    \rm -f "${_dest_file}.dl_part"
    return 1
}

# Usage: url_exists [--quiet] URL
url_exists() {
    local _opts
    if [[ "$1" == "--quiet" ]] ; then
        _opts+=" --quiet"
        shift
    fi
    wget $_opts --spider "$1"
}

get_rpm_level_name() {
    local _rpm_name=$1
    local _level=$2
    if [ $_level == "L1" ]; then
        SFILE=`echo $_rpm_name | rev | cut -d'.' -f3- | rev`
    elif [ $_level == "$dl_from_stx_mirror" ];then
        # stx mirror uses L1 matches
        SFILE=`echo $_rpm_name | rev | cut -d'.' -f3- | rev`
    elif [ $_level == "L2" ];then
        SFILE=`echo $_rpm_name | rev | cut -d'-' -f2- | rev`
    else
        SFILE=`echo $_rpm_name | rev | cut -d'-' -f3- | rev`
    fi
    echo "$SFILE"
}

get_url() {
    local _name="$1"
    local _level="$2"
    local _ret=""

    if [ "$_level" == "K1" ]; then
        _ret="$(koji_url $_name)"
    elif [[ "$_name" == *"#"* ]]; then
        _ret="$(echo $_name | cut -d'#' -f2-2)"
        if [ $_level == "stx_mirror" ]; then
            _ret="$(url_to_stx_mirror_url $_ret $distro)"
        fi
    else
        _url_cmd="$(get_yum_command $_name $_level) --url"

        # When we add --url to the yum download command,
        # --archlist is no longer enforced.  Multiple
        # url's might be returned.  So use grep to
        # filter urls for the desitered arch.
        local arr=( $(split_filename $_name) )
        local arch=${arr[3]}
        _ret="$(${SUDO} $_url_cmd | grep "[.]$arch[.]rpm$" | head -n 1)"
    fi
    echo "$_ret"
}

# Function to split an rpm filename into parts.
#
# Returns a space seperated list containing:
#    <NAME> <VERSION> <RELEASE> <ARCH> <EPOCH>
#
split_filename () {
    local rpm_filename=$1

    local RPM=""
    local SFILE=""
    local ARCH=""
    local RELEASE=""
    local VERSION=""
    local NAME=""
    local EPOCH=""

    RPM=$(echo $rpm_filename | rev | cut -d'.' -f-1 | rev)
    SFILE=$(echo $rpm_filename | rev | cut -d'.' -f2- | rev)
    ARCH=$(echo $SFILE | rev | cut -d'.' -f-1 | rev)
    SFILE=$(echo $SFILE | rev | cut -d'.' -f2- | rev)
    RELEASE=$(echo $SFILE | rev | cut -d'-' -f-1 | rev)
    SFILE=$(echo $SFILE | rev | cut -d'-' -f2- | rev)
    VERSION=$(echo $SFILE | rev | cut -d'-' -f-1 | rev)
    NAME=$(echo $SFILE | rev | cut -d'-' -f2- | rev)

    if [[ $NAME = *":"* ]]; then
        EPOCH=$(echo $NAME | cut -d':' -f-1)
        NAME=$(echo $NAME | cut -d':' -f2-)
    fi

    echo "$NAME" "$VERSION" "$RELEASE" "$ARCH" "$EPOCH"
}

# Function to predict the URL where a rpm might be found.
# Assumes the rpm was compile for EPEL by fedora's koji.
koji_url () {
    local rpm_filename=$1

    local arr=( $(split_filename $rpm_filename) )

    local n=${arr[0]}
    local v=${arr[1]}
    local r=${arr[2]}
    local a=${arr[3]}

    echo "https://kojipkgs.fedoraproject.org/packages/$n/$v/$r/$a/$n-$v-$r.$a.rpm"
}

get_dest_directory() {
    local _type=$1
    local _dest=""
    if [ "$_type" == "src" ]; then
        _dest="$MDIR_SRC"
    else
        _dest="$MDIR_BIN/$_type"
    fi
    echo "$_dest"
}

process_result() {
    local _type="$1"
    local dest_dir="$2"
    local url="$3"
    local sfile="$4"

    if [ "$_type" != "src" ] && [ ! -d $dest_dir ]; then
        mkdir -p $dest_dir
    fi

    echo "url_srpm:$url"

    if ! mv -f $sfile* $dest_dir ; then
        echo "FAILED to move $rpm_name"
        echo "fail_move_srpm:$rpm_name" >> $LOG
        return 1
    fi

    echo "found_srpm:$rpm_name"
    echo $rpm_name >> $FOUND_SRPMS
    return 0
}


get_download_cmd() {
    local ff="$1"
    local _level="$2"

    # Decide if the list will be downloaded using yumdownloader or curl
    if [[ $ff != *"#"* ]]; then
        rpm_name=$ff
        if [ $_level == "K1" ]; then
            download_cmd="$(get_download_file_command --quiet $rpm_name)"
        else
            # yumdownloader with the appropriate flag for src, noarch or x86_64
            # download_cmd="${SUDOCMD} $(get_yum_command $rpm_name $_level)"
            download_cmd="$(get_yum_command $rpm_name $_level)"
        fi
    else
        # Build the download command
        rpm_url=$(get_url "$ff" "$_level")
        download_cmd="$(get_download_file_command --quiet $rpm_url)"
    fi

    echo "$download_cmd"
}

get_rpm_name() {
    local ret=""

    if [[ "$1" != *"#"* ]]; then
        ret="$1"
    else
        ret="$(echo $1 | cut -d"#" -f1-1)"
    fi
    echo "$ret"
}

get_arch_from_rpm() {
    local _file=$1
    local _split=()
    local _arch=""
    if [[ "$1" == *"#"* ]]; then
        _file=$(echo $_file | cut -d"#" -f1-1)
    fi

    _split=( $(split_filename $_file) )
    _arch=${_split[3]}

    echo "$_arch"
}

get_from() {
    list=$1
    base=$(basename $list .lst) # removing lst extension
    base=$(basename $base .log) # removing log extension
    from=$(echo $base | rev | cut -d'_' -f1-1 | rev)
    echo $from
}
