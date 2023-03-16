#!/usr/bin/env python3

from configparser import ConfigParser
from pathlib import Path
import argparse
import time
from hpc_interact import Scripter
try:
    # only required if downloading acknowledgement files
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError
except: pass

states = {'AK': 'Alaska','AL': 'Alabama','AR': 'Arkansas','AS': 'American Samoa','AZ': 'Arizona','CA': 'California','CO': 'Colorado','CT': 'Connecticut','DC': 'District of Columbia','DE': 'Delaware','FL': 'Florida','GA': 'Georgia','GU': 'Guam','HI': 'Hawaii','IA': 'Iowa','ID': 'Idaho','IL': 'Illinois','IN': 'Indiana','KS': 'Kansas','KY': 'Kentucky','LA': 'Louisiana','MA': 'Massachusetts','MD': 'Maryland','ME': 'Maine','MI': 'Michigan','MN': 'Minnesota','MO': 'Missouri','MP': 'Northern Mariana Islands','MS': 'Mississippi','MT': 'Montana','NA': 'National','NC': 'North Carolina','ND': 'North Dakota','NE': 'Nebraska','NH': 'New Hampshire','NJ': 'New Jersey','NM': 'New Mexico','NV': 'Nevada','NY': 'New York','OH': 'Ohio','OK': 'Oklahoma','OR': 'Oregon','PA': 'Pennsylvania','PR': 'Puerto Rico','RI': 'Rhode Island','SC': 'South Carolina','SD': 'South Dakota','TN': 'Tennessee','TX': 'Texas','UT': 'Utah','VA': 'Virginia','VI': 'Virgin Islands','VT': 'Vermont','WA': 'Washington','WI': 'Wisconsin','WV': 'West Virginia','WY': 'Wyoming'}

def warn(warning):
    """Prints warning an exits"""

    print(warning)
    exit(1)

def findDownloadsDir(downloads):
    """Locates or requests input of directory where downloads typically go"""

    if downloads: return downloads
    for p in Path.cwd().parents:
        for x in p.iterdir():
            if x.name == "Downloads":
                return x
    return input("Please enter the path to your downloads file now or quit and add it with parameter '-d'\n>")

def getState(location):
    """Sets which locations will be downloaded based on `location` list variable in config"""

    state_name = states.get(location)
    if state_name: return state_name
    elif location in states.values(): return location
    else:
        print(f"Could not find a state with name {location}.")
        new_location = input("Correct the spelling and hit enter or \nPress enter to continue anyway or \nType 'quit' or '^C' to quit.\n>")
        if new_location.lower() == "quit": exit(1)
        elif new_location == "": return location
        else: getState(location)

def determineFileTypesToDownload(filetypes):
    """Sets which filetypes will be downloaded based on `filetypes` list variable in config"""

    all_types = ["fasta","meta","ackno"]
    choices = []
    for ft in all_types:
        # within above order ^^^, add to list if filetype is present
        for choice in filetypes:
            if choice.lower() == "all":
                return all_types
            elif choice.lower() == "none":
                return []
            elif choice.lower() == ft:
                choices.append(ft)
                break # check next filetype
    return choices

class VariableHolder:
    """An object used to store and access variables"""

    def __init__(self,name) -> None:
        self.name = name
    def add_var(self,varname,value):
        setattr(self,varname,value)

def get_elements(config,section,elements):
    """Finds requested variables in config and returns a VariableHolder containing them"""

    holder = VariableHolder("ssh")
    for element in elements:
        value = config[section][element]
        if not value.strip(): value = None
        if section == "Paths":
            if value != None:
                value = Path(value)
        holder.add_var(element,value)
    return holder

def checkSSH(ssh_vars):
    """Locates or requests and writes out important variables for cluster interaction"""

    for x in ("site","cluster_epicov_dir","local_epicov_dir","cluster_scripts"):
        var = getattr(ssh_vars,x)
        if not var:
            print(f"{x} not found in config")
            new_value = input(f"Please enter your {x}\n>>")    
            setattr(ssh_vars,x,new_value)
    return ssh_vars

def getVariables():
    """Gets variables from arguments and config to direct behavior"""

    parser = argparse.ArgumentParser(prog='gisaid_download_basic.py',
        description="""Download EpiCoV sequences from GISAID. WARNING: By using this software you agree GISAID's Terms of Use and reaffirm your understanding of these terms.""")
    parser.add_argument("date",metavar='date: [YYYY-MM-DD]',type=str,help="download sequences up to this date")
    parser.add_argument("-f","--filetypes",nargs="*",default=["all"],help="space delimited list of files to download - options: ['fasta','meta','ackno','all','none']")
    parser.add_argument("-l","--location",dest="location",metavar="",nargs='+',help="space delimited list of state(s) for which data is desired (standard abbreviations allowed)")
    parser.add_argument("-e","--episet",action="store_true",dest="get_epi_set",help="request EPI_SET for selection after any downloads")
    parser.add_argument("-d","--downloads",nargs='?',type=Path,default=None,help="path to where you recieve downloads from your web browser")
    parser.add_argument("-w","--epicov_dir",type=Path,help="local directory containing all related downloads - will be created if absent")
    parser.add_argument("-c","--config_file",type=Path,default=Path("./gisaid_config.ini"),help="path to config (default: ./artic_config.ini)")
    parser.add_argument("-q","--quick",action="store_false",dest="wait",help="don't pause and require pressing enter to continue")
    parser.add_argument("-s","--skip_download",action="store_true",help="don't update local list of downloaded accessions (if unset, files will be retrieved from the cluster before the EpiCoV download steps)")
    parser.add_argument("-n","--no_cluster",dest="cluster_interact",action="store_false",help="don't interact trasfer any files to/from the cluster")
    args = parser.parse_args()
    if not len(args.date) == 10 or not "-" in args.date:
        if "unfiltered" in args.date: pass
        else: warn("Date must be of the format 'YYYY-MM-DD'")

    # get config variables
    if not args.config_file.exists():
        args.config_file = Path("gisaid_config.ini").resolve()
        if not args.config_file.exists(): raise FileNotFoundError(args.config_file)
    config = ConfigParser(converters={'list': lambda x: [i.strip() for i in x.split(',')]})
    config.read(args.config_file)
    ssh_vars = get_elements(config,"SSH",("site","group","login_config"))
    path_var_list = ("epicov_dir","cluster_epicov_dir","downloads","cluster_scripts")
    path_vars = get_elements(config,"Paths",path_var_list)
    followup_command = config["Misc"].get("followup_command")
    args.epicov_dir,cluster_epicov_dir,args.downloads,cluster_scripts = [getattr(path_vars,val) for val in path_var_list]
    ssh_vars.add_var("cluster_epicov_dir",cluster_epicov_dir)
    ssh_vars.add_var("local_epicov_dir",args.epicov_dir)
    ssh_vars.add_var("cluster_scripts",cluster_scripts)
    ssh_vars = checkSSH(ssh_vars)
    if type(args.downloads) == type(None): args.downloads = findDownloadsDir(args.downloads)
    args.filetypes = config.getlist("Misc","filetypes")
    args.location = config.getlist("Misc","location")
    print(args.epicov_dir,ssh_vars.cluster_epicov_dir,ssh_vars,args.filetypes,args.location)
    file_choices = determineFileTypesToDownload(args.filetypes)
    args.epicov_dir.mkdir(parents=True, exist_ok=True)

    return args.date,args.location,args.downloads,file_choices,args.get_epi_set,args.epicov_dir,ssh_vars,args.wait,args.skip_download,followup_command,args.cluster_interact

def continueFromHere(runthrough=None):
    """Prints a showy line so users can easily find where they left off"""

    if runthrough: indicator = f" - {runthrough}"
    else: indicator = ""
    print(f"\n\n^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n\
        \t\t\tCONTINUE FROM HERE{indicator}\
        \nvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv\n")

def awaitEnter(wait=True):
    """Waits until user hits `enter`"""

    if wait:
        input("\n\tPress enter in terminal to continue...\n")
        continueFromHere()

def click(item_to_click,item_type="button",wait=False):
    """Returns str: Click (`item_type`) `item_to_click`"""

    print(f'\tClick ({item_type}) "{item_to_click}"')
    awaitEnter(wait)

def fill(item_to_fill,content,wait=False):
    """Returns str: 'Fill in "`item_to_fill`" as: `item_to_click`'"""

    print(f'\tFill in "{item_to_fill}" as: {content}')
    awaitEnter(wait)

def listdir(dir_name:Path):
    """Returns a set of all directories in `dir_name`"""

    return set(file for file in dir_name.iterdir())

def awaitDownload(downloads:Path,outfile:Path,runthrough=None):
    """Waits for a file of the specified filetype to appear""" # TODO: add in verification of correct internal format (in case of erroneous clicks)

    print(f'\nWaiting for new file in downloads with extension "{outfile.suffix}"')
    already_there = listdir(downloads)
    count = 0
    while 1:
        count+=1
        current_set = listdir(downloads)
        if len(current_set) == len(already_there): pass
        else:
            newfile_set = current_set - already_there
            if len(newfile_set) == 1: # allow any .part file to be removed to indicate successful download
                for file in newfile_set:
                    if file.suffix == outfile.suffix: # file has been found
                        continueFromHere(runthrough)
                        return file
        time.sleep(.5)
        if count % 120 == 0:
            print(f"\t{count/2} seconds have passed - still waiting. Previous files: {len(already_there)} - Current files: {len(current_set)}")

def downloadFileAs(outbase:Path,outdir:Path,downloads:Path,action,action_input,action2=None,action2_input=None,runthrough=None):
    """Once expected file is downloaded, renames as desired path/name""" # TODO: add in verification of correct internal format (in case of erroneous clicks)

    outfile = outdir / outbase
    if outfile.exists():
        print(f"\tFile already exists - skipping download of \n\t\t{outfile}")
    else:
        if type(action_input) == str: action(action_input)
        elif type(action_input) == tuple: action(action_input[0],action_input[1])
        if action2: action2(action2_input)
        downloaded_file = awaitDownload(downloads,outfile,runthrough)
        downloaded_file.rename(outfile)
        print(f"\tFile saved: {outfile}")
    return outfile

def getSetFromFile(file:Path):
    """Converts all lines in file to a set"""

    return set(file.read_text().splitlines())

def getNewAccessions(accession_dir,all_gisaid_seqs,new_seqs):
    """Checks all accessions available against accessions already downloaded - returns and writes out new ones"""

    print("\nDetermining which accessions to download")
    # determine which seqs we already have
    accession_files = accession_dir.glob("*")
    already_downloaded_set = set()
    for f in accession_files:
        if not f.name == ".DS_Store": # for macs...
            already_downloaded_set |= getSetFromFile(f)
            # print("accessions found:",len(already_downloaded_set))
    # get list of seqs in gisaid
    if all_gisaid_seqs.exists():
        gisaid_set = getSetFromFile(all_gisaid_seqs)
    else: warn(f"file not found: {all_gisaid_seqs}")
    # find seqs needed
    new_set = gisaid_set - already_downloaded_set
    print("\tnew seqs in EpiCoV:",len(new_set))
    # write out seqs to file to put in eipcov
    with new_seqs.open('w') as out:
        for id in new_set:
            out.write(f"{id}\n")
    print(f"\tNew accessions written to {new_seqs}")
    return list(new_set)

def getSelectionAsFile(runthrough,runthroughs,new_seqs,download_limit,downloads:Path):
    """Writes temp file of desired accessions to request from GISAID"""

    if runthrough == runthroughs-1: # for last runthrough only select to the end of list
        selection = new_seqs[runthrough*download_limit:]
    else: # get selection based on size limit all other times
        selection = new_seqs[runthrough*download_limit:(runthrough+1)*download_limit]
    selection_file = downloads.joinpath(f"temp_selection")
    if selection_file.exists(): selection_file.unlink() # remove to write new, if already there (for Macs to have updated timestamps)
    with selection_file.open('w') as out:
        for id in selection:
            out.write(f"{id}\n")
    return selection_file,len(selection)

def checkSelectionSize(selection_size,file_choices,get_epi_set):
    """Ensures desired activities can be done for selection size (limited by GISAID restrictions)"""

    if get_epi_set:
        return get_epi_set,file_choices
    if "ackno" in file_choices and selection_size > 500:
        choice = input("Your sample set has more than 500 samples, so you cannot download an acknowledgement file.\nWould you prefer to:\
            \n\t1 - request an EPI_SET at the end\
            \n\t2 - skip the acknowledgement file and skip the EPI_SET\
            \n\t3 - cancel run\n>")
        if choice == 3:
            exit(1)
        elif choice == 1:
            get_epi_set = True
        elif choice == 2:
            get_epi_set = False
        updated_file_choices = [f for f in file_choices if f != "ackno"]
        print(updated_file_choices)
        return get_epi_set,updated_file_choices
    else:
        return get_epi_set,file_choices

def acquireEpiSet(date,epicov_files,downloads):
    """Guides user through EPI_SET acquisition"""

    print("\nGetting EPI_SET. This will be emailed to you\n")
    outfile = downloads.joinpath(f"all_epicovs_{date}.csv")
    with outfile.open("w") as out:
        for file in epicov_files:
            with file.open() as fh:
                for line in fh:
                    out.write(line)
    click("EPI_SET")
    click("Choose file")
    print("\tIf 'Choose file' button not present, go back out, click 'Search', and try again from 'EPI_SET'.")
    print("\tFollow the prompts out.")

def isFasta(fh):
    """Returns True if file loooks like a nucleotide sequence fasta, else False"""

    line1 = fh.readline()
    # if line 1 >something, it's likely a fasta, otherwise, definitely not
    if not line1.startswith(">"):
        return False
    # if line 2 is only bases, it's a fasta
    line2 = fh.readline().strip()
    return not set(line2[:50]) - set(["A","T","G","C","U","N","a","t","g","c","u","n"])

def isPDF(file,PdfReader,PdfReadError):
    """Returns True if `file` is a pdf, else False"""

    try:
        PdfReader(file)
    except PdfReadError:
        return False
    else:
        return True
    
def isCorrectTsv(fh,fields):
    """Returns True if fields are all present in file header"""

    line1 = fh.readline().strip()
    cols = set((c.strip("'\"") for c in line1.split("\t")))
    return not set(fields) - cols



def looksLikeCorrectFile(file_type,file,fields=None):
    """Returns True if file is of correct type and has expected contents

    Args:
        file_type (str): The type of file expected
        file_dict (dict): A dictionary of details about the file
        file (str | Path): The file of interest
    """

    if file_type == "ackno":
        return isPDF(file,PdfReader,PdfReadError)
    else:
        with open(file) as fh:
            if file_type == "fasta":
                return isFasta(fh)
            elif file_type == "meta":
                return isCorrectTsv(fields)



def downloadFiles(file_choices,date,runthrough,outdir,downloads,location,selection_size,get_epi_set):
    """Guides the downloading of desired files, renaming them appropriately"""

    get_epi_set,file_choices = checkSelectionSize(selection_size,file_choices,get_epi_set)

    file_info = {
        "fasta":[
            {"label":"Nucleotide Sequences (FASTA)","fn":f"gisaid_{location}_{date}.{runthrough}.fasta","abbr":"fasta"}],
        "meta":[
            {"label":"Dates and Location","fn":f"gisaid_date_{location}_{date}.{runthrough}.tsv","abbr":"date & location",
            "fields":["Accession ID","Collection date","Submission date","Location"]},
            {"label":"Patient status metadata","fn":f"gisaid_pat_{location}_{date}.{runthrough}.tsv","abbr":"patient status",
            "fields":["Virus name","Accession ID","Collection date","Location","Host","Additional location information","Sampling strategy","Gender","Patient age","Patient "]},
            {"label":"Sequencing technology metadata","fn":f"gisaid_seq_{location}_{date}.{runthrough}.tsv","abbr":"sequence tech",
            "fields":["Virus name","Accession ID","Collection date","Location","Host","Passage","Specimen","Additional host information","Sequencing technology","Assembly method","Comment","Comment type","Lineage","Clade","AA Substitutions"]}],
        "ackno":[
            {"label":"Acknowledgement table","fn":f"gisaid_ackno_{location}_{date}.{runthrough}.pdf","abbr":"ack_pdfnew"}]
    }
    # download all desired files
    for file_type in file_choices:
        for file_dict in file_info[file_type]:
            name = Path(file_dict["fn"])
            runinfo = f"{location} {file_dict['label']} #{runthrough}"
            if not outdir.joinpath(name).exists():
                if runthrough == 0 and name.suffix=="fasta":
                    click("OK (twice)")
                print(f"\nPreparing to download {runinfo}\n")
                # loop through download - if it looks like user got wrong file, try again
                while 1:
                    click("Download")
                    outfile = downloadFileAs(outbase=name,outdir=outdir,downloads=downloads,action=click,action_input=(file_dict["label"],"circle"),action2=click,action2_input="Download",runthrough=runthrough)
                    if looksLikeCorrectFile(file_type=file_type,file=outfile,fields=file_dict.get("fields")):
                        break
                    else:
                        print(f"The file you downloaded does not match the typical traits of a {file_dict['label']} file. \nTry again.\n")
            else: print(f"\t{runinfo} already exists in {outdir}")
    return get_epi_set

def getEpicovAcessionFile(all_gisaid_seqs_name,accession_dir,location,location_long,downloads,date,wait):
    """Finds or guides download of file with all available accessions for current selection in GISAID"""

    print("\nDownloading (or locating) EpiCoV accessions file for",location_long)
    if accession_dir.joinpath(all_gisaid_seqs_name).exists():
        all_gisaid_seqs = accession_dir / all_gisaid_seqs_name
        print(f"\n\tEpiCoV accessions already exist for {location}, {date} in {all_gisaid_seqs.parent}")
    else:
        all_gisaid_seqs = downloads / all_gisaid_seqs_name
        if all_gisaid_seqs.exists():
            print(f"\nEpiCoV accessions already exist for {location}, {date} in {all_gisaid_seqs.parent}")
        else:
            print(f"\nNeed to download data for {location_long}\n")
            fill("Location",location_long,wait=wait)
            print(f"Determining which sequences need to be downloaded for {location}\n")
            print("\tIf not done already:")
            print("\tCheck the select-all checkbox next to 'Virus name' - it's not labeled")
            click("Select")
            downloadFileAs(
                outbase=all_gisaid_seqs,
                outdir=downloads,
                downloads=downloads,
                action=click,
                action_input="CSV")
    return all_gisaid_seqs

def prepareFilters(date):
    """Directs which filters need to be selected (based on the UNC Charlotte Environmental Monitoring Laboratory's standards)"""

    print("\nPreparing filters - ensure these are set (or use your own filters if this is a non-standard run)\n")
    click("Search")
    click("Low coverage excluded","checkbox")
    click("Collection date complete","checkbox")
    fill("Collection to (2nd box)",(date))
    fill("Host","Human")

def save_accessions(new_seq_files,accession_dir):
    """Saves accession files to accession dir so they won't be redownloaded in future runs"""

    for file in new_seq_files:
        if file.exists():
            print("moving",file,"to",accession_dir.joinpath(file.name))
            file.rename(accession_dir.joinpath(file.name))

def download_data(locations,date,downloads,accession_dir,file_choices,outdir,wait,get_epi_set):
    """Guided download of requested data for each location requested"""

    epicov_files = []
    new_seq_files = []
    download_limit = 10000 #This is the limit imposed by GISAID

    for location in locations:
        prepareFilters(date)

        location_long = getState(location)

        all_gisaid_seqs_name = Path(f"all_{location}_epicovs_{date}.csv")
        new_seq_file = downloads.joinpath(f"new_seqs_{location}_{date}.csv")

        # download full, current accession list if needed
        all_gisaid_seqs = getEpicovAcessionFile(all_gisaid_seqs_name,accession_dir,location,location_long,downloads,date,wait)

        new_seq_list = getNewAccessions(
            # local_seqs=outdir.joinpath("epi_isls_overall.tsv"),
            accession_dir=accession_dir,
            all_gisaid_seqs=all_gisaid_seqs,
            new_seqs=new_seq_file)

        # save fn for later use
        epicov_files.append(all_gisaid_seqs)
        if len(new_seq_list) > 0: new_seq_files.append(new_seq_file)

        # download files if user requested them (and if there are any new sequences)
        if len(new_seq_list) > 0:
            runthroughs = int(len(new_seq_list)/download_limit) + 1
            for runthrough in range(runthroughs):
                # get selections to input (file will be in Downloads)
                selection_file,selection_size = getSelectionAsFile(runthrough,runthroughs,new_seq_list,download_limit,downloads)
                print(f"\n\n##################  {location} runthrough {runthrough + 1}  ##################\n")
                print("\nRefresh the page:\n")
                print("\tNavigate out by clicking 'OK', as needed")
                click("Search")
                click("Select")
                print(f'\nLook in your "Downloads" folder for:\t"temp_selection"\n')
                click("Browse...choose file...")
                print(f"\tInput selections from {selection_file} (Choose File)")
                click("OK (twice)")
                print("\tor\n\tskip this runthrough (if you know these files already exist)")
                awaitEnter(wait=wait)

                get_epi_set = downloadFiles(file_choices,date,runthrough,outdir,downloads,location,selection_size,get_epi_set)
        elif len(new_seq_list) == 0:
            print("No new seqs available to be downloaded for", location_long)
            continueFromHere()
        print(f"\nDone aquiring {location_long} data.\n")
    return epicov_files,new_seq_files,get_epi_set

def getScripter(ssh_vars:VariableHolder,mode="sftp"):
    """Instantiates a Scripter object for ssh/sftp interactions with the cluster"""

    # return Scripter(username=ssh_vars.username, password=ssh_vars.password, site=ssh_vars.site, mode=mode, group=ssh_vars.group)
    return Scripter(site=ssh_vars.site, mode=mode, group=ssh_vars.group)

def upload_data(ssh_vars,date):
    """Uploads the downloads from this session to the cluster"""

    outdir = Path(ssh_vars.cluster_epicov_dir)
    local_dir = Path(ssh_vars.local_epicov_dir)
    scripter = getScripter(ssh_vars)
    for loc in ("gisaid_metadata","accession_info"):
        scripter.put(local_dir/loc/f"*{date}*", outdir/loc, options=[],set_permissions=True)
    scripter.preview_steps()
    scripter.run()

def update_accessions(ssh_vars):
    """Downloads accession CSVs from cluster to determine which accessions have already been downloaded"""

    cluster_dir = Path(ssh_vars.cluster_epicov_dir)
    local_dir = Path(ssh_vars.local_epicov_dir)
    scripter = getScripter(ssh_vars)
    scripter.get(cluster_dir/"accession_info/*", local_dir/"accession_info", options=["a"])
    scripter.preview_steps()
    scripter.run()

def run_followup_cluster_command(ssh_vars,followup_command,date):
    """Runs (on the cluster) the script/command from `followup_command` which presumably initiates analysis of these downloaded data"""

    scripter = getScripter(ssh_vars,mode="ssh")
    followup_command = followup_command.replace("<date>","date")
    scripter.add_step(f"sbatch {ssh_vars.cluster_scripts}/reports/prepare_pdf_report.sh -s -r {date}")
    scripter.preview_steps()
    scripter.run()

def main():
    """
    Downloads new sequences and metadata from GISAID's EpiCoV database
      * Pulls in all accessions on the cluster (optional) to keep from redownloading any from EpiCoV
      * Guides user through downloading from EpiCoV & renames files as they're downloaded
      * Uploads gisaid-downloads to cluster (optional)
      * Starts pangolin/nextclade analysis on new downloads
    #### Example usage:
      * normal download - fastas/metadata
      `python gisaid_download.py 2022-04-06 -f fasta meta`
      * just get EPI_SET (for acknowledgements)
      `python gisaid_download.py 2022-04-06 -f none --episet`
      * with config (default config: ./gisaid_config.ini):
      `python gisaid_download.py 2022-04-06 -c /path/to/config_file.ini`
    """
    date,locations,downloads,file_choices,get_epi_set,epicov_dir,ssh_vars,wait,skip_download,followup_command,cluster_interact = getVariables()

    # set and make storage directories if needed
    local_accession_dir = Path(f"{epicov_dir}/accession_info")
    meta_dir = Path(f"{epicov_dir}/gisaid_metadata")
    for outdir in (local_accession_dir,meta_dir): outdir.mkdir(exist_ok=True,parents=True)

    # update local copy of downloaded accessions
    if cluster_interact:
        if not skip_download: update_accessions(ssh_vars)
        else: print("Skipping cluster/local data update")

    print(f"\nGuiding you through downloading EpiCoV data up through {date}\n")
    print("\tGo to https://www.epicov.org/epi3/frontend and log in.")
    awaitEnter(wait=wait)

    # get any/all desired data from GISAID
    if file_choices:
        epicov_files,new_seq_files,get_epi_set = download_data(locations,date,downloads,local_accession_dir,file_choices,meta_dir,wait,get_epi_set)

    # get epi_set for all current acccesions if requested
    if get_epi_set: acquireEpiSet(date,epicov_files,downloads)

    # save accessions of new data to accession_info (this is last so that it only happens if script completes)
    print(f'Saving new sequences downloaded this run to "{local_accession_dir}"')
    save_accessions(new_seq_files,local_accession_dir)

    if cluster_interact:
        # upload data to the cluster via sftp
        upload_data(ssh_vars,date)

        # start data prep (or run whatever command was provided)
        if followup_command:
            run_followup_cluster_command(ssh_vars,followup_command,date)

if __name__ == "__main__":
    main()
