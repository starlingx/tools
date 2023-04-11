#!/bin/bash

## This file makes the necessary configuration for the unlock of the Controller-0

GROUPNO=0
DATE_FORMAT="%Y-%m-%d %T"
LOG_FILE=${LOG_FILE:-"${HOME}/lab_setup_1.group${GROUPNO}.log"}
VERBOSE_LEVEL=0

OPENRC=/etc/platform/openrc
source ${OPENRC}


function info {
    local MSG="$1"

    echo ${MSG}
    echo $(date +"${DATE_FORMAT}") ${MSG} >> ${LOG_FILE}
}


function log_command {
    local CMD=$1
    local MSG="[${OS_USERNAME}@${OS_PROJECT_NAME}]> RUNNING: ${CMD}"

    set +e
    if [ ${VERBOSE_LEVEL} -gt 0 ]; then
        echo ${MSG}
    fi
    echo $(date +"${DATE_FORMAT}") ${MSG} >> ${LOG_FILE}

    if [ ${VERBOSE_LEVEL} -gt 1 ]; then
        eval ${CMD} 2>&1 | tee -a ${LOG_FILE}
        RET=${PIPESTATUS[0]}
    else
        eval ${CMD} &>> ${LOG_FILE}
        RET=$?
    fi

    if [ ${RET} -ne 0 ]; then
        info "COMMAND FAILED (rc=${RET}): ${CMD}"
        info "==========================="
        info "Check \"${LOG_FILE}\" for more details, fix the issues and"
        info "re-run the failed command manually."
        exit 1
    fi
    set -e

    return ${RET}
}


## Set OAM interface
function configure_OAM_interface {
    #Set OAM_IF variable
    log_command "OAM_IF=enp0s3"
    #Associate OAM_IF with Controller-0
    log_command "system host-if-modify controller-0 $OAM_IF -c platform"
    log_command "system interface-network-assign controller-0 $OAM_IF oam"

    return 0
}


configure_OAM_interface
