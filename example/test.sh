#!/usr/bin/env bash
this_dir="`dirname ${0}`"

config_file=${this_dir}/gisaid_config.ini

gisaid_download 2023-03-16 -q -c "$config_file"