#!/bin/bash
#
# SPDX-License-Identifier: Apache-2.0
#
# Copyright (c) 2020 Wind River Systems, Inc.
#

# This file included for backward compatibility, and
# should be removed after a reasonable time.


GENERATE_CGCS_CENTOS_REPO_DIR="$(dirname "$(readlink -f "${BASH_SOURCE[0]}" )" )"

echo "" 1>&2
echo "generate-cgcs-centos-repo.sh is deprecated. Please use generate-centos-repo.sh instead." 1>&2
echo "" 1>&2
echo "Forwarding to generate-centos-repo.sh in 5 seconds" 1>&2
echo "" 1>&2
sleep 5

${GENERATE_CGCS_CENTOS_REPO_DIR}/generate-centos-repo.sh "$@"
