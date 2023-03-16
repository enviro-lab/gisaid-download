#!/usr/bin/env bash
this_dir="`dirname ${0}`"

# move here so we can use the example config_file by default
cd $this_dir

gisaid_download 2023-03-16 -sq