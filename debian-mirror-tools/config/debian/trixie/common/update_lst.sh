#!/bin/bash
#
# For all packages in the existing base-trixie.lst, check if
# the build container has a newer version of those packages.
# Build base-trixie.lst.new containing all those suggested updates.
#
# The updates suggested by base-trixie.lst.new can then be copied
# back into base-trixie.lst if desired.
#
cat ./base-trixie.lst | grep -v ^# | awk '{print $1}' | sort | xargs -i apt show {} | grep -e ^Package -e^Version -e ^$ | awk -v RS="" '{print $2"  "$4}' >> ./base-trixie.lst.new
