import pandas as pd
from collections import defaultdict
import re
from sys import argv
from os import path
import click
from glob import glob
import gzip
import lzma
from cover import SortedRangeList

@click.command()
@click.option('-i',"--input", required=True, help="Input: Directory of sam files (files must end in .sam).")
@click.option('-o',"--output", required=True, help='Output: file name for list of coverages.')
@click.option('-d',"--database", default="databases/WoL/metadata.tsv", help='WoL genome metadata file.',show_default=True)

def calculate_coverages(input, output, database):
    ###################################
    #Calculate coverage of each contig#
    ###################################
    gotu_dict = defaultdict(SortedRangeList)

    if path.isdir(input):
        file_list = glob(input + "/*.sam")
        file_list_gz = glob(input + "/*.sam.gz")
        file_list_xz = glob(input + "/*.sam.xz")
        file_list = file_list + file_list_gz + file_list_xz
    elif path.isfile(input):
        file_list = [input]
    else:
        raise FileNotFoundError(input)
        
    ###################################
    #Get information from database#
    ###################################
    md = pd.read_table(database).loc[:,["#genome","total_length","unique_name"]]
    md.columns = ["gotu","total_length","strain"]
    md["gotu"] = md["gotu"].astype(str)
    md = md.set_index("gotu")
    
    for samfile in file_list:
        open_sam_file = None
        if samfile.endswith(".sam"):
            open_sam_file = open(samfile.strip(), 'r')
        elif samfile.endswith(".sam.gz"):
            open_sam_file = gzip.open(
                samfile.strip(),
                mode='rt',
                encoding='utf-8')
        elif samfile.endswith(".sam.xz"):
            open_sam_file = lzma.open(
                samfile.strip(),
                mode='rt',
                encoding='utf-8')
        else:
            raise IOError("Unrecognized file extension on '%s'." % samfile)
        with open_sam_file:
            for line in open_sam_file:
                if line.startswith("@"):
                    # ignore header lines for now
                    continue

                #Get values for contig, location, and length
                linesplit= line.split()
                gotu = linesplit[2]
                if gotu not in md.index:
                    # JDTB-2024 An organism that was filtered already in the 773
                    continue
                location = int(linesplit[3])
                #Get sum of lengths in CIGAR string. Counting deletions as alignment because they should be small
                length_string = linesplit[5]
                if length_string == "*":
                    # CIGAR String unavailable, skip.
                    # We don't know what section of the genome was covered.
                    continue

                length = sum([int(x) for x in re.split("[a-zA-Z]",length_string) if x])
                #Add range to contig_dict
                gotu_dict[gotu].add_range(location, location + length - 1)



    #####################
    #Calculate coverages#
    #####################
    #Make dataframe from dicitonary of coverages of each contig
    cov = pd.DataFrame(
        {
            "gotu": list(gotu_dict.keys()),
            "covered_length": [x.compute_length() for x in gotu_dict.values()]
        }
    )
    cov= cov.set_index("gotu")
    cov = cov.sort_values("covered_length", ascending=False)
    #Add genome metadata
    cov = cov.join(md, how="left")
    #Calculate coverage percent
    cov["coverage_ratio"] = cov.apply(func= lambda x : x["covered_length"]/x["total_length"], axis=1)
    cov = cov.loc[:,["covered_length","total_length","coverage_ratio","strain"]]

    ##############
    #Write output#
    ##############
    cov.sort_values("coverage_ratio",ascending=False).to_csv(output, sep='\t')
    cov[cov["coverage_ratio"] > 0.02].reset_index()[["gotu"]].set_index("gotu").to_csv("./metaG_aligned/gotu_above_2percent.txt",header=None)

if __name__ == "__main__":
    calculate_coverages()
