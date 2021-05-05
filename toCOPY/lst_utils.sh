#
# Copyright (c) 2020 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

rpms_from_layer_build_template="rpm.lst"
image_inc_from_layer_build_template="image.inc"
dev_image_inc_from_layer_build_template="image-dev.inc"
wheels_inc_from_layer_build_template="wheels.inc"

config_dir=${MY_REPO}/../stx-tools/centos-mirror-tools/config
distro="centos"
layer="all"

# Store urls for package list files of the various layers in an associative array
declare -A layer_pkg_urls

# Store urls for image include files of the various layers in an associative array
declare -A layer_image_inc_urls

# Store urls for wheel include files of the various layers in an associative array
declare -A layer_wheels_inc_urls

url_to_file_name () {
    echo "${1}" | sed 's#[:/ ]#-#g'
}

merge_lst () {
    local cfg_dir=$1
    local distro=$2
    local template=$3

    local cfg_name="${distro}_build_layer.cfg"
    local layer_cfgs
    local layers
    local layer

    if [ "$cfg_dir" == "" ] || [ "$distro" == "" ] || [ "$template" == "" ]; then
        echo "ERROR: merge_lst: missing argument" >&2
        return 1
    fi

    if [ "$MY_REPO" == "" ]; then
        echo "ERROR: merge_lst: environment variable MY_REPO must be set" >&2
        return 1
    fi

    layer_cfgs=$(find ${MY_REPO} -maxdepth 3 -name ${cfg_name})
    if [ "$layer_cfgs" == "" ]; then
        echo "ERROR: merge_lst: Could not find any '${cfg_name}' files" >&2
        return 1
    fi

    # Grep to ignore empty lines or whole line comments.
    # Sed to drop any trailing comments.
    # Side effect of grep over cat is adding any missing EOL.
    layers=$(grep -h -v -e '^$' -e '^[ \t]*#' ${layer_cfgs} | sed -e 's/[ \t]*#.*$//' | sort --unique)
    layers+=" mock"

    (
    for layer in ${layers}; do
        for f in $(find ${cfg_dir}/${distro}/${layer} -name ${template} ); do
            grep -v '^#' $f || true
        done
    done

    for f in $(find ${MY_REPO} -maxdepth 3 -name ${distro}_${template};  \
                find ${MY_REPO} -maxdepth 3 -name ${distro}_s${template}; \
                ); do
        grep -v '^#' $f || true
    done
    ) | sort --unique
}

set_layer_image_inc_urls () {
    local option="${1}"

    if [ "${option}" == "" ]; then
        return
    fi

    local layer_and_inc_type="${option%,*}"
    local layer="${layer_and_inc_type%,*}"
    local inc_type="${layer_and_inc_type#*,}"
    local layer_image_inc_url="${option##*,}"

    layer_image_inc_urls["${layer_and_inc_type}"]="${layer_image_inc_url}"
}

set_layer_wheels_inc_urls () {
    local option="${1}"

    if [ "${option}" == "" ]; then
        return
    fi

    local layer_and_stream="${option%,*}"
    local layer="${layer_and_stream%,*}"
    local stream="${layer_and_stream#*,}"
    local layer_wheels_inc_url="${option##*,}"

    layer_wheels_inc_urls["${layer_and_stream}"]="${layer_wheels_inc_url}"
}

set_layer_pkg_urls () {
    local option="${1}"

    if [ "${option}" == "" ]; then
        return
    fi

    local layer_and_build_type="${option%,*}"
    local layer="${layer_and_build_type%,*}"
    local build_type="${layer_and_build_type#*,}"
    local layer_pkg_url="${option##*,}"

    layer_pkg_urls["${layer_and_build_type}"]="${layer_pkg_url}"
}

read_layer_image_inc_urls () {
    local layer="${1}"
    local cfg="${config_dir}/${distro}/${layer}/required_layer_iso_inc.cfg"
    local line=""
    local key

    if [ ! -f "${cfg}" ]; then
        return 0;
    fi

    # Clear all pre-existing entries
    for key in "${!layer_image_inc_urls[@]}"; do
        unset layer_image_inc_urls[${key}]
    done

    while read line; do
        line=$(echo "${line}" | sed 's/^[ \t]*//;s/[ \t]*$//' | grep '^[^#]')
        if [ "${line}" == "" ]; then
            continue
        fi
        set_layer_image_inc_urls "${line}"
    done < "${cfg}"
}

read_layer_wheels_inc_urls () {
    local layer="${1}"
    local cfg="${config_dir}/${distro}/${layer}/required_layer_wheel_inc.cfg"
    local line=""
    local key

    if [ ! -f "${cfg}" ]; then
        return 0;
    fi

    # Clear all pre-existing entries
    for key in "${!layer_wheels_inc_urls[@]}"; do
        unset layer_wheels_inc_urls[${key}]
    done

    while read line; do
        line=$(echo "${line}" | sed 's/^[ \t]*//;s/[ \t]*$//' | grep '^[^#]')
        if [ "${line}" == "" ]; then
            continue
        fi
        set_layer_wheels_inc_urls "${line}"
    done < "${cfg}"
}

read_layer_pkg_urls () {
    local layer="${1}"
    local cfg="${config_dir}/${distro}/${layer}/required_layer_pkgs.cfg"
    local line=""
    local key

    if [ ! -f "${cfg}" ]; then
        return 0;
    fi

    # Clear all pre-existing entries
    for key in "${!layer_pkg_urls[@]}"; do
        unset layer_pkg_urls[${key}]
    done

    while read line; do
        line=$(echo "${line}" | sed 's/^[ \t]*//;s/[ \t]*$//' | grep '^[^#]')
        if [ "${line}" == "" ]; then
            continue
        fi
        set_layer_pkg_urls "${line}"
    done < "${cfg}"
}

set_and_validate_config_dir () {
    # Note: Setting the global 'config_dir' here.  Not local!
    config_dir=${1}

    if [ ! -d ${config_dir} ]; then
        echo "Error: Invalid config_dir '$config_dir'"
        echo "    Please select one of: $(find ${config_dir} -maxdepth 1 ! -path ${config_dir} -type d -exec basename {} \;)"
        echo
        usage
        exit 1
    fi
}

set_and_validate_distro () {
    # Note: Setting the global 'distro' here.  Not local!
    distro=${1}

    if [ ! -d ${config_dir}/${distro} ]; then
        echo "Error: Invalid distro '$distro'"
        echo "    Please select one of: $(find ${config_dir} -maxdepth 1 ! -path ${config_dir} -type d -exec basename {} \;)"
        echo
        usage
        exit 1
    fi

    if [ -d ${config_dir}/${distro}/${layer} ]; then
        read_layer_pkg_urls ${layer}
        read_layer_image_inc_urls ${layer}
        read_layer_wheels_inc_urls ${layer}
    else
        echo "Warning: layer ${layer} not defined for distro '${distro}', please provide a valid layer via '-l <layer>'"
    fi
}

set_and_validate_layer () {
    # Note: Setting the global 'layer' here.  Not local!
    layer=${1}

    if [ ${layer} != "all" ] && [ ! -d ${config_dir}/${distro}/${layer} ]; then
        echo "Error: Invalid layer '$layer'"
        echo "    Please select one of: all $(find ${config_dir}/${distro} -maxdepth 1 ! -path ${config_dir}/${distro} -type d -exec basename {} \;)"
        echo
        usage
        exit 1
    fi

    read_layer_pkg_urls ${layer}
    read_layer_image_inc_urls ${layer}
    read_layer_wheels_inc_urls ${layer}
}

# Pick up value of the config_dir from environment if set
if [ "$STX_CONFIG_DIR" != "" ]; then
    set_and_validate_config_dir "$STX_CONFIG_DIR"
fi

# Pick up value of layer from environment if set
if [ "$LAYER" != "" ]; then
    set_and_validate_layer "$LAYER"
fi

read_layer_pkg_urls ${layer}
read_layer_image_inc_urls ${layer}
read_layer_wheels_inc_urls ${layer}
