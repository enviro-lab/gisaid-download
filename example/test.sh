#!/usr/bin/env bash
this_dir="`dirname ${0}`"

# move here so we can use the example config_file by default
cd $this_dir

# # Instead of cd-ing here, you could uncomment this:
# # get gisaid config (you'll need to edit this)
# echo "Downloading gisaid config. You should edit this."
# gisaid_download --example
# echo;

# run test
echo "Running gisaid_download"
gisaid_download `date '+%Y-%m-%d'` -sq