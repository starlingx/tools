#!/bin/bash
cat ./os-std.lst | grep -v ^# | awk '{print $1}' | sort | xargs -i apt show {} | grep -e ^Package -e^Version -e ^$ | awk -v RS="" '{print $2"  "$4}' >> ./os-std.lst.new
