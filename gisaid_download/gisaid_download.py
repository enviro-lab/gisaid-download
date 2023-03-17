#!/usr/bin/env python3

from configparser import ConfigParser
import os
from pathlib import Path
import argparse
import time
import sys
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

    # attempt to determine location
    if downloads: return downloads
    if Path("/mnt").is_dir():
        possible_download_dirs = list(Path("/mnt").glob("*/Users/*/Downloads"))
    elif Path("/mnt").is_dir():
        possible_download_dirs = list(Path("/Users").glob("*/Downloads"))
    else:
        possible_download_dirs = list(Path("/Home").glob("*/Downloads"))
    if len(possible_download_dirs) == 1: pass
    else:
        possible_download_dirs = ([d for d in possible_download_dirs if not "Public" in str(d) and not "Default" in str(d)])
    if len(possible_download_dirs) == 1:
        return possible_download_dirs[0]
    # request location, because can't find it
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

    meta_files = []
    possible_meta_files = ["date_loc","patient","seq_tech"]
    actual_filetypes = []
    if "fasta" in filetypes:
        actual_filetypes.append("fasta")
    if "meta" in filetypes:
        meta_files = possible_meta_files
        actual_filetypes.append("meta")
    else:
        overlap = set(possible_meta_files).union(filetypes)
        if overlap:
            actual_filetypes.append("meta")
            meta_files = [ft for ft in filetypes if ft in possible_meta_files]
    if "ackno" in filetypes:
        actual_filetypes.append("ackno")
    return actual_filetypes,meta_files

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
        if value == "True": value=True
        elif value == "False": value=False
        if section == "Paths":
            if value != None:
                value = Path(value)
        holder.add_var(element,value)
    return holder

def checkSSH(ssh_vars):
    """Locates or requests and writes out important variables for cluster interaction"""

    for x in ("site","cluster_epicov_dir","local_epicov_dir"):
        var = getattr(ssh_vars,x)
        if not var:
            print(f"{x} not found in config")
            new_value = input(f"Please enter your {x}\n>>")    
            setattr(ssh_vars,x,new_value)
    return ssh_vars

def getVariables():
    """Gets variables from arguments and config to direct behavior"""

    # parse args
    from gisaid_download.version import __version__
    parser = argparse.ArgumentParser(prog='gisaid_download_basic.py',
        description="""Download EpiCoV sequences from GISAID. WARNING: By using this software you agree GISAID's Terms of Use and reaffirm your understanding of these terms.""")
    parser.add_argument('-V', '--version', action='version', version="%(prog)s ("+__version__+")")
    parser.add_argument("--example",action="store_true",help="writes out an example 'gisaid_config.ini' to `outdir`")
    parser.add_argument("-o","--outdir",type=Path,default=Path("."),help="outdir for example config file (default: current working directory)")
    # adding these args only if user isn't requesting example config gets around `date` being a required argument, otherwise
    if not "example" in (arg.strip("-") for arg in sys.argv):
        example = False
        parser.add_argument("date",metavar='date: [YYYY-MM-DD]',type=str,help="download sequences up to this date")
        parser.add_argument("-f","--filetypes",nargs="*",default=[],help="space delimited list of files to download - options: ['fasta','meta','date_loc','patient','seq_tech','ackno','all','none']")
        parser.add_argument("-l","--location",metavar="",nargs='+',help="space delimited list of state(s) for which data is desired (standard abbreviations allowed)")
        parser.add_argument("-e","--episet",action="store_true",dest="get_epi_set",help="request EPI_SET for selection after any downloads")
        parser.add_argument("-d","--downloads",nargs='?',type=Path,default=None,help="path to where you recieve downloads from your web browser")
        parser.add_argument("-w","--epicov_dir",type=Path,default=None,help="local directory containing all related downloads - will be created if absent")
        parser.add_argument("-b","--cluster_epicov_dir",type=Path,default=None,help="local directory containing all related downloads - will be created if absent")
        parser.add_argument("-c","--config_file",type=Path,default=Path("./gisaid_config.ini"),help="path to config (default: ./gisaid_config.ini)")
        parser.add_argument("-q","--quick",action="store_false",dest="wait",help="don't wait for user to hit enter between each step")
        parser.add_argument("-s","--skip_local_update",action="store_true",help="don't update local list of downloaded accessions (if unset, files will be retrieved from the cluster before the EpiCoV download steps)")
        parser.add_argument("-n","--no_cluster",dest="cluster_interact",action="store_false",help="don't interact trasfer any files to/from the cluster")
    else:
        example = True
    args = parser.parse_args()

    # variable cleanup
    if example:
        # ensure all these attribtes exist - they won't be used, but the return statement need them
        for var in ["date","filetypes","meta_files","location","get_epi_set","downloads","epicov_dir","cluster_epicov_dir","config_file","wait","skip_local_update","cluster_interact"]:
            setattr(args,var,None)
        filetype_choices,ssh_vars,followup_command,custom_filters = [None]*4
    else:
        # notify if date has incorrect format - not worth failing script over, though
        if not len(args.date) == 10 or not "-" in args.date:
            print(f"WARNING: `date` ({args.date}) not in expected format 'YYYY-MM-DD'")

        # get config variables
        if not args.config_file.exists(): raise FileNotFoundError(args.config_file)
        config = ConfigParser(converters={'list': lambda x: [i.strip() for i in x.split(',')]})
        config.read(args.config_file)

        # vars that may come from config
        followup_command = config["Misc"].get("followup_command")
        ssh_vars = get_elements(config,"SSH",("site","group","login_config","save_credentials"))
        path_var_list = ("epicov_dir","cluster_epicov_dir","downloads")
        path_vars = get_elements(config,"Paths",path_var_list)
        custom_filters = [y for y in (x.strip(",") for x in config["Misc"].get("custom_filters","").split("\n")) if y]
        epicov_dir,cluster_epicov_dir,downloads = [getattr(path_vars,val) for val in path_var_list]
        filetypes = config.getlist("Misc","filetypes")
        location = config.getlist("Misc","location")

        # prioritize cli version of these but use config default (if possible) if they don't exist
        for var in ("epicov_dir","cluster_epicov_dir","filetypes","location"):
            if not getattr(args,var,None):
                default_from_config = locals().get(var)
                if not default_from_config:
                    raise AttributeError(f"Attribute `{var}` must be provided in config or arguments.")
                else:
                    setattr(args,var,default_from_config)
        
        # finalize & return variables
        if type(args.downloads) == type(None): args.downloads = findDownloadsDir(args.downloads)
        ssh_vars.add_var("cluster_epicov_dir",args.cluster_epicov_dir)
        ssh_vars.add_var("local_epicov_dir",args.epicov_dir)
        ssh_vars = checkSSH(ssh_vars)
        filetype_choices,meta_files = determineFileTypesToDownload(args.filetypes)
        args.epicov_dir.mkdir(parents=True, exist_ok=True)

    return args.date,args.location,args.downloads,filetype_choices,meta_files,args.get_epi_set,args.epicov_dir,ssh_vars,args.wait,args.skip_local_update,followup_command,args.cluster_interact,custom_filters,example,args.outdir

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
            if count % 20 == 0: print(newfile_set)
            if len(newfile_set) >= 1: # allow any .part file to be removed to indicate successful download
                for file in newfile_set:
                    if ".part" in file.suffixes: break
                    if count % 20 == 0: print(file.suffix,outfile.suffix)

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
        try:
            downloaded_file = awaitDownload(downloads,outfile,runthrough)
        except KeyboardInterrupt:
            if outfile.exists():
                print("\tRemoving unverified file:",outfile)
                outfile.unlink()
            warn("\n\nScript stopped by KeyboardInterrupt")
        else:
            pass
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

def checkSelectionSize(selection_size,filetype_choices,get_epi_set):
    """Ensures desired activities can be done for selection size (limited by GISAID restrictions)"""

    if get_epi_set:
        return get_epi_set,filetype_choices
    if "ackno" in filetype_choices and selection_size > 500:
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
        updated_filetype_choices = [f for f in filetype_choices if f != "ackno"]
        print(updated_filetype_choices)
        return get_epi_set,updated_filetype_choices
    else:
        return get_epi_set,filetype_choices

def acquireEpiSet(date,epicov_files,downloads):
    """Guides user through EPI_SET acquisition"""

    print("\nRequesting EPI_SET. GISAID will email it to you afterwards.\n")
    outfile = downloads.joinpath(f"all_epicovs_{date}.csv")
    with outfile.open("w") as out:
        for file in epicov_files:
            with file.open() as fh:
                for line in fh:
                    out.write(line)
    click("EPI_SET")
    click("Choose file")
    print("\tIf 'Choose file' button not present, go back out, click 'Search', and try again from 'EPI_SET'.")
    print("\tSelect your file.")
    click("Generate")
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
    if set(fields) - cols:
        print("Fields that should exist but don't:",set(fields) - cols)
        print("Extra fields:",cols - set(fields))
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
                return isCorrectTsv(fh,fields)

def downloadFiles(filetype_choices,meta_files,date,runthrough,outdir,downloads,location,selection_size,get_epi_set):
    """Guides the downloading of desired files, renaming them appropriately"""

    get_epi_set,filetype_choices = checkSelectionSize(selection_size,filetype_choices,get_epi_set)

    file_info = {
        "fasta":[
            {"label":"Nucleotide Sequences (FASTA)","fn":f"gisaid_{location}_{date}.{runthrough}.fasta","abbr":"fasta"}],
        "meta":[
            {"label":"Dates and Location","fn":f"gisaid_date_{location}_{date}.{runthrough}.tsv","abbr":"date & location","filetypes_abbr":"date_loc",
            "fields":["Accession ID","Collection date","Submission date","Location"]},
            {"label":"Patient status metadata","fn":f"gisaid_pat_{location}_{date}.{runthrough}.tsv","abbr":"patient status","filetypes_abbr":"patient",
            "fields":["Virus name","Accession ID","Collection date","Location","Host","Additional location information"," Sampling strategy","Gender","Patient age","Patient status","Last vaccinated","Passage","Specimen","Additional host information","Lineage","Clade","AA Substitutions"]},
            {"label":"Sequencing technology metadata","fn":f"gisaid_seq_{location}_{date}.{runthrough}.tsv","abbr":"sequence tech","filetypes_abbr":"seq_tech",
            "fields":["Virus name","Accession ID","Collection date","Location","Host","Passage","Specimen","Additional host information","Sequencing technology","Assembly method","Comment","Comment type","Lineage","Clade","AA Substitutions"]}],
        "ackno":[
            {"label":"Acknowledgement table","fn":f"gisaid_ackno_{location}_{date}.{runthrough}.pdf","abbr":"ack_pdfnew"}]
    }
    # download all desired files
    for file_type in filetype_choices:
        done_once = False
        for file_dict in file_info[file_type]:
            name = Path(file_dict["fn"])
            runinfo = f"{location} {file_dict['label']} #{runthrough}"
            if not outdir.joinpath(name).exists():
                if file_type == "meta":
                    if file_dict["filetypes_abbr"] not in meta_files:
                        continue
                if runthrough == 0 and done_once == False:
                    click("OK (twice)")
                    done_once = True
                print(f"\nPreparing to download {runinfo}\n")
                # loop through download - if it looks like user got wrong file, try again
                while 1:
                    click("Download")
                    outfile = downloadFileAs(outbase=name,outdir=outdir,downloads=downloads,action=click,action_input=(file_dict["label"],"circle"),action2=click,action2_input="Download",runthrough=runthrough)
                    if looksLikeCorrectFile(file_type=file_type,file=outfile,fields=file_dict.get("fields")):
                        break
                    else:
                        outfile.unlink()
                        print(f"\nWARNING: The file you downloaded does not match the typical traits of a {file_dict['label']} file. See above for more. \nTry again.\n")
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

allowed_actions = ("click","fill","print")
def add_filter_step(action:str,date):
    """Adds custom actions (like click, fill, or print) to be executed by script to guide user through which filters to select

    Args:
        action (str): a function to execute
    """

    # only conduct allowed actions
    if action.split("(",1)[0] in allowed_actions:
        if action.startswith("print("):
            print("\t",end='')
        exec(action)
    else:
        print(f"\t{action}")

def prepareFilters(date,custom_filters=None):
    """Directs which filters need to be selected (based on the UNC Charlotte Environmental Monitoring Laboratory's standards)"""


    print("\nPreparing filters - ensure these are set (or use your own filters if this is a non-standard run)\n")
    click("Search")

    if custom_filters:
        for action in custom_filters:
            add_filter_step(action,date)
    else:
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

def download_data(locations,date,downloads,accession_dir,filetype_choices,meta_files,outdir,wait,get_epi_set,custom_filters):
    """Guided download of requested data for each location requested"""

    epicov_files = []
    new_seq_files = []
    download_limit = 10000 #This is the limit imposed by GISAID

    for location in locations:
        prepareFilters(date,custom_filters)

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
                print("\tNavigate out by clicking 'Back' or 'OK', as needed")
                click("Search")
                click("Select")
                print(f'\nLook in your "Downloads" folder for:\t"temp_selection"\n')
                click("Choose file")
                print(f"\tInput selections from {selection_file} (Choose File)")
                click("OK (twice)")
                print("\tor\n\tskip this runthrough (if you know these files already exist)")
                awaitEnter(wait=wait)

                get_epi_set = downloadFiles(filetype_choices,meta_files,date,runthrough,outdir,downloads,location,selection_size,get_epi_set)
        elif len(new_seq_list) == 0:
            print("No new seqs available to be downloaded for", location_long)
            continueFromHere()
        print(f"\nDone aquiring {location_long} data.\n")
    return epicov_files,new_seq_files,get_epi_set

def getScripter(ssh_vars:VariableHolder,mode="sftp"):
    """Instantiates a Scripter object for ssh/sftp interactions with the cluster"""

    return Scripter(site=ssh_vars.site, mode=mode, group=ssh_vars.group, save_credentials=ssh_vars.save_credentials, config=ssh_vars.login_config)

def upload_data(ssh_vars:VariableHolder,scripter:Scripter,date:str):
    """Uploads the downloads from this session to the cluster"""

    outdir = Path(ssh_vars.cluster_epicov_dir)
    local_dir = Path(ssh_vars.local_epicov_dir)
    scripter.reset_mode("sftp")
    for loc in ("gisaid_metadata","accession_info"):
        scripter.put(local_dir/loc/f"*{date}*", outdir/loc, options=[],set_permissions=True)
    scripter.preview_steps()
    scripter.run()

def update_accessions(ssh_vars:VariableHolder,scripter:Scripter):
    """Downloads accession CSVs from cluster to determine which accessions have already been downloaded"""

    cluster_dir = Path(ssh_vars.cluster_epicov_dir)
    local_dir = Path(ssh_vars.local_epicov_dir)
    scripter.reset_mode("sftp")
    scripter.get(cluster_dir/"accession_info/*", local_dir/"accession_info", options=["a"])
    scripter.preview_steps()
    scripter.run()

def run_followup_cluster_command(scripter:Scripter,followup_command,date):
    """Runs (on the cluster) the script/command from `followup_command` which presumably initiates analysis of these downloaded data"""

    scripter.reset_mode("ssh")
    scripter.add_step(followup_command.replace("<date>",date))
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
    date,locations,downloads,filetype_choices,meta_files,get_epi_set,epicov_dir,ssh_vars,wait,skip_local_update,followup_command,cluster_interact,custom_filters,example,outdir = getVariables()

    # get example config and exit, if requested
    if example:
        from example import file_getter
        file_getter.get_example_config(outdir)
        exit()

    # set and make storage directories if needed
    local_accession_dir = Path(f"{epicov_dir}/accession_info")
    meta_dir = Path(f"{epicov_dir}/gisaid_metadata")
    for outdir in (local_accession_dir,meta_dir): outdir.mkdir(exist_ok=True,parents=True)

    # update local copy of downloaded accessions
    if cluster_interact:
        scripter = getScripter(ssh_vars)
        if not skip_local_update: update_accessions(ssh_vars,scripter)
        else: print("Skipping cluster/local data update")

    print(f"\nGuiding you through downloading EpiCoV data up through {date}\n")
    print("\tGo to https://www.epicov.org/epi3/frontend and log in.")
    awaitEnter(wait=wait)

    # get any/all desired data from GISAID
    if filetype_choices:
        epicov_files,new_seq_files,get_epi_set = download_data(locations,date,downloads,local_accession_dir,filetype_choices,meta_files,meta_dir,wait,get_epi_set,custom_filters)

    # get epi_set for all current acccesions if requested
    if get_epi_set: acquireEpiSet(date,epicov_files,downloads)

    # save accessions of new data to accession_info (this is last so that it only happens if script completes)
    print(f'Saving new sequences downloaded this run to "{local_accession_dir}"')
    save_accessions(new_seq_files,local_accession_dir)

    if cluster_interact:
        # upload data to the cluster via sftp
        upload_data(ssh_vars,scripter,date)

        # start data prep (or run whatever command was provided)
        if followup_command:
            run_followup_cluster_command(scripter,followup_command,date)

if __name__ == "__main__":
    main()
