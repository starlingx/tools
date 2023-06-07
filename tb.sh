#!/bin/bash
# tb.sh - tbuilder commands
#
# Subcommands:
# env - Display a selection of configuration values
# create - Create a docker image customized for the current localrc settings
# create_no_cache - Create a docker image customized for the current localrc settings, but do NOT us the docker cache
# run - Starts a build container
# exec - Starts a shell inside a running build container
# status - Check if the build container is running
# stop - Stops a build container
# kill - Kill the build container
# clean - 
#
# Configuration
# tb.sh expects to find its configuration file buildrc in the current
# directory, like Vagrant looks for Vagrantfile.

SCRIPT_DIR=$(cd $(dirname "$0") && pwd)
WORK_DIR=$(pwd)

# Load tbuilder configuration
if [[ -r ${WORK_DIR}/buildrc ]]; then
    source ${WORK_DIR}/buildrc
fi

CMD=$1

ROOT_NAME=${MYUNAME}
if [[ -n "${PROJECT}" ]]; then
    ROOT_NAME+="-${PROJECT,,}"
fi
if [[ -n "${LAYER}" ]]; then
    ROOT_NAME+="-${LAYER,,}"
fi
if [[ -n "${TIMESTAMP}" ]]; then
    ROOT_NAME+="-${TIMESTAMP,,}"
fi
TC_CONTAINER_NAME="${ROOT_NAME}-centos-builder"
TC_IMAGE_NAME=local/${ROOT_NAME}-stx-builder:7.8
TC_DOCKERFILE=Dockerfile
NO_CACHE=0

function create_container {
    local EXTRA_ARGS=""

    if [ ! -z ${MY_EMAIL} ]; then
        EXTRA_ARGS+="--build-arg MY_EMAIL=${MY_EMAIL}"
    fi

    if [ $NO_CACHE -eq 1 ]; then
        EXTRA_ARGS+=" --no-cache"
    fi

    docker build \
        --build-arg MYUID=$(id -u) \
        --build-arg MYUNAME=${USER} \
        ${EXTRA_ARGS} \
        --ulimit core=0 \
        --network host \
        -t ${TC_IMAGE_NAME} \
        -f ${TC_DOCKERFILE} \
        .
}

function exec_container {
    echo "docker cp ${WORK_DIR}/buildrc ${TC_CONTAINER_NAME}:/home/${MYUNAME}"
    docker cp ${WORK_DIR}/buildrc ${TC_CONTAINER_NAME}:/home/${MYUNAME}
    docker cp ${WORK_DIR}/localrc ${TC_CONTAINER_NAME}:/home/${MYUNAME}
    docker exec -it --user=${MYUNAME} -e MYUNAME=${MYUNAME} ${TC_CONTAINER_NAME} script -q -c "/bin/bash" /dev/null
}

function run_container {
    # create localdisk
    echo "Creating ${MY_WORKSPACE_ROOT_DIR}, ${MY_REPO_ROOT_DIR}, ${HOST_MIRROR_DIR}/CentOS"
    mkdir -p ${MY_WORKSPACE_ROOT_DIR}
    mkdir -p ${MY_REPO_ROOT_DIR}
    #create centOS mirror
    mkdir -p ${HOST_MIRROR_DIR}/CentOS

    local extra_mounts=""

    if [[ -d "${MY_WORKSPACE_ROOT_DIR}" ]] && \
       [[ -d "${MY_REPO_ROOT_DIR}" ]] && \
       [[ -n "${MOCK_DIR}" ]] && [[ -n "${MOCK_CACHE_DIR}" ]]; then
        if [[ ! -d "${MOCK_DIR}" ]]; then
            mkdir -p "${MOCK_DIR}"
            chmod 775 "${MOCK_DIR}"
        fi
        if [[ ! -d "${MOCK_CACHE_DIR}" ]]; then
            mkdir -p "${MOCK_CACHE_DIR}"
            chmod 775 "${MOCK_CACHE_DIR}"
        fi
        extra_mounts+="-v $(readlink -f ${MY_WORKSPACE_ROOT_DIR}):/${GUEST_MY_WORKSPACE_ROOT_DIR} "
        extra_mounts+="-v $(readlink -f ${MY_REPO_ROOT_DIR}):/${GUEST_MY_REPO_ROOT_DIR} "
        extra_mounts+="-v $(readlink -f ${MOCK_DIR}):/localdisk/loadbuild/mock "
        extra_mounts+="-v $(readlink -f ${MOCK_CACHE_DIR}):/localdisk/loadbuild/mock-cache "
    elif [ -d "${LOCALDISK}" ]; then
        extra_mounts+="-v $(readlink -f ${LOCALDISK}):/${GUEST_LOCALDISK} "
    else
        echo "Can't find '${LOCALDISK}' "
        exit 1
    fi

    docker run -it --rm \
        --name ${TC_CONTAINER_NAME} \
        --detach \
        $extra_mounts \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v ${HOST_MIRROR_DIR}:/import/mirrors:ro \
        -v /sys/fs/cgroup:/sys/fs/cgroup:ro \
        -v ~/.ssh:/mySSH:ro \
        --tmpfs /tmp \
        --tmpfs /run \
        -e "container=docker" \
        -e MYUNAME=${MYUNAME} \
        --privileged=true \
        --security-opt seccomp=unconfined \
        ${TC_IMAGE_NAME}
}

function status_container {
    docker container ls -f name=${TC_CONTAINER_NAME}
}

function inspect_container {
    echo docker container inspect ${TC_CONTAINER_NAME}
    docker container inspect ${TC_CONTAINER_NAME}
}

function stop_container {
    docker stop ${TC_CONTAINER_NAME}
}

function kill_container {
    docker kill ${TC_CONTAINER_NAME}
}

function clean_container {
    docker rm ${TC_CONTAINER_NAME} || true
    docker image rm ${TC_IMAGE_NAME}
}

function usage {
    echo "$0 [create|create_no_cache|run|exec|env|status|stop|kill|clean]"
}

case $CMD in
    env)
        echo "LOCALDISK=${LOCALDISK}"
        echo "GUEST_LOCALDISK=${GUEST_LOCALDISK}"
        echo "MY_REPO_ROOT_DIR=${MY_REPO_ROOT_DIR}"
        echo "GUEST_MY_REPO_ROOT_DIR=${GUEST_MY_REPO_ROOT_DIR}"
        echo "MY_REPO=${MY_REPO}"
        echo "GUEST_MY_REPO=${GUEST_MY_REPO}"
        echo "MY_WORKSPACE_ROOT_DIR=${MY_WORKSPACE_ROOT_DIR}"
        echo "GUEST_MY_WORKSPACE_ROOT_DIR=${GUEST_MY_WORKSPACE_ROOT_DIR}"
        echo "MY_WORKSPACE=${MY_WORKSPACE}"
        echo "GUEST_MY_WORKSPACE=${GUEST_MY_WORKSPACE}"
        echo "TC_DOCKERFILE=${TC_DOCKERFILE}"
        echo "TC_CONTAINER_NAME=${TC_CONTAINER_NAME}"
        echo "TC_IMAGE_NAME=${TC_IMAGE_NAME}"
        echo "SOURCE_REMOTE_NAME=${SOURCE_REMOTE_NAME}"
        echo "SOURCE_REMOTE_URI=${SOURCE_REMOTE_URI}"
        echo "HOST_MIRROR_DIR=${HOST_MIRROR_DIR}"
        echo "MY_RELEASE=${MY_RELEASE}"
        echo "MY_REPO_ROOT_DIR=${MY_REPO_ROOT_DIR}"
        echo "TIMESTAMP=${TIMESTAMP}"
        echo "LAYER=${LAYER}"
        echo "PROJECT=${PROJECT}"
        echo "MYUNAME=${MYUNAME}"
        echo "MY_EMAIL=${MY_EMAIL}"
        ;;
    create)
        create_container
        ;;
    create_no_cache)
        NO_CACHE=1
        create_container
        ;;
    exec)
        exec_container
        ;;
    run)
        run_container
        ;;
    status)
        status_container
        ;;
    inspect)
        inspect_container
        ;;
    stop)
        stop_container
        ;;
    kill)
        kill_container
        ;;
    clean)
        clean_container
        ;;
    *)
        echo "Unknown command: $CMD"
        usage
        exit 1
        ;;
esac
