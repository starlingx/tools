#!/bin/bash

OP=$1
CHARTDIR=$2

if [ -z "$OP"]; then
    exit 1
fi

if [ -z "$CHARTDIR"]; then
    exit 1
fi

if [ $OP == "waitlabel" ]; then
    KIND=("Deployment" "StatefulSet" "DaemonSet")
    if [ ! -d $CHARTDIR/templates ]; then
        exit 1
    fi
    cd $CHARTDIR/templates
    for target in ${KIND[@]}; do
        output=$(grep $target . -rn | awk -F ':' '{print$1}' \
            | xargs awk -F ':' '/{{ .Release.Name }}/{print$1; exit}')
        if [ "x$output" != "x" ]; then
            echo $output
            exit 0
        fi
    done
elif [ $OP == "chartname" ]; then
    if [ ! -f $CHARTDIR/Chart.yaml ]; then
        exit 1
    fi
    cd $CHARTDIR
    output=$(awk '/name:/{print$2;exit}' Chart.yaml)
    if [ "x$output" != "x" ]; then
        echo $output
        exit 0
    fi
fi
exit 1
