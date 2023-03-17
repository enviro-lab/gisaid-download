# gisaid-download
Purpose: Assisted download of selected samples from GISAID or EPI_SET creation.

`gisaid-download` is a tool for acuiring metadata for selected samples from gisaid. It was produced primarily for use with the EpiCoV database but should work just as well for EpiFlu or EpiPox. Fully-automated download from gisaid's website is tricky, but manual download is a slow, error-prone process requiring renaming and moving around files as you go. With `gisaid-download`, you are guided through the process of downloading desired samples.

## Features
Downloading Samples:
* keeps track of which samples you (or your team-mates) have already downloaded so you only get the new ones
* can download batches of samples from multiple locations
* moves/renames files to a consolidated directory as they're downloaded
* can limit which metadata files you download to any combination of the following:
  * fasta: [Nucleotide sequences]
  * meta: [Dates and Location, Patient status metadata, Sequencing technology metadata]
  * ackno: [Acknowledgement pdfs] (can only do this for 500 samples at a time, so EPI_SETs are better)

Uploading samples for further analysis:
* can upload all that data to an hpc via sftp
* can add a command to run after upload to start your analysis pipeline
    (We might make ours available someday!)

Getting an EPI_SET:
* can walk you through getting an EPI_SET identifier for all of your samples
* this will be emailed to you by GISAID

Some of the above features use sftp or ssh via scripted commands with the help of the package [hpc-interact](https://github.com/enviro-lab/hpc-interact). It has its own config for storing login credentials. If needed and not yet made, your credentials will be gathered over the command line. That file can be specified in [gisaid_config.ini](example/gisaid_config.ini) and only requires two lines:
```
username=myuser
password=mypass
```

## Installation
```console
pip install gisaid-download
```

## Usage
The first time you use `gisaid-download`, you'll need to set up a config file: [gisaid_config.ini](example/gisaid_config.ini) . Download it to your pwd or chosen outdir via:
```console
gisaid_download --example -o gisaid/directory
```

Edit the config file to serve your needs. There are details in there that explain most everything.

Now you're ready to do the download and/or get your EPI_SET. Let's say we only want samples that were collected before 2023. We'll set a date (required for creating unique filenames). To run, do this:
```console
sample_date='2023-01-01'
gisaid_download ${sample_date}
```

## Behavior
The above command triggers up to four steps. Steps 1, 3, and 4 only happen if you're interacting with the hpc cluster. If using the `--no_cluster` (or `-n`) flag, they will be skipped.

### Step 1: Update local list of downloaded sequences
If you're planning on transferring downloaded data to an hpc, the above command will first look for samples that already exist on the hpc at your `cluster_epicov_dir` (from config). This uses sftp via (via [hpc-interact](https://github.com/enviro-lab/hpc-interact)). If no data yet exists on the cluster or you're the only one downloading samples and transferring them to the hpc, you can skip this step by adding the `--skip_local_update` (or `-s`) flag like this:
```console
gisaid_download ${sample_date} --skip_local_update
```
The flag `-n` can also be used to skip this step along with step 3 and 4.

### Step 2: Download sequences
This is an interactive download that by default requires pressing enter after each step. If you don't want to press enter as much (like if you get in the rhythm and can't be bothered to stop...), you can add the `--quick` (or `-q`) flag like this
```console
gisaid_download ${sample_date} --quick
```

### Step 3: Upload sequences to hpc
Using sftp (via [hpc-interact](https://github.com/enviro-lab/hpc-interact)), all the data downloaded in Step 2 will be uploaded to the hpc at your `cluster_epicov_dir`.

The flag `-n` can also be used to skip this step along with step 1 and 4.

### Step 4: Run a followup command on the hpc
If specified in your [gisaid_config.ini](example/gisaid_config.ini), `followup_command` will be run by ssh through [hpc-interact](https://github.com/enviro-lab/hpc-interact). This could be any string, but we recommend setting it to run a script that will begin analyzing the data you just uploaded.
