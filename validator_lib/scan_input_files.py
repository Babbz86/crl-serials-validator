"""
Runs through any files in the input directory and attempts to make a little sense of them.

For MARC files, records:
    * number of records
    * number with 001
    * number with obvious OCLC 035
    * number with other 035
    * number with 863/864/865
    * number with 866/867/868

At the moment, this doesn't attempt to scan txt/tsv/csv/xlsx files.
"""
import os
import csv
from collections import Counter
import logging

from crl_lib.marc_file_reader import MarcFileReader
from crl_lib.marc_fields import MarcFields


class InputFileScanner:
    def __init__(self, input_files):
        
        self.data = {}
        self.input_dir = os.path.join(os.getcwd(), 'input')
        logging.debug("Scanning input files.")
        for input_file in input_files:
            if input_file.endswith(".mrk"):
                logging.debug("Scanning {}".format(input_file))
                self.marc_scanner(input_file)
               
            elif input_file.endswith(".xlsx"):
                logging.info("Skipping {}".format(input_file))
            elif input_file.endswith(".txt") or input_file.endswith(".tsv") or input_file.endswith(".csv"):
                logging.info("Skipping {}".format(input_file))
            else:
                logging.warning("Unkown file type in input directory: {}".format(input_file))

    def marc_scanner(self, input_file):
        input_file_loc = os.path.join(self.input_dir, input_file)
        file_data = Counter()
        mfr = MarcFileReader(input_file_loc)
        for marc in mfr:
            file_data["Total records"] += 1
            mf = MarcFields(marc)
            if "=001  " in marc:
                file_data["Have 001 field"] += 1
            if "004  " in marc:
                file_data["Have 004 field"] += 1
            if mf.oclc_035:
                file_data["Have 035"] += 1
                file_data["OCLC in 035"] += 1
            elif "=035  " in marc:
                file_data["Have 035"] += 1
            if "=863  " in marc or "=864  " in marc or "=865  " in marc:
                file_data["Have 863/864/865"] += 1
            if "=866  " in marc or "=867  " in marc or "=868  " in marc:
                file_data["Have 866/867/868"] += 1

        cats = ["Total records", "Have 001 field", "Have 004 field", "Have 035", "OCLC in 035",
                "Have 863/864/865", "Have 866/867/868"]

        # skip blank file
        if file_data["Total records"] == 0:
            logging.warning('No records found in {}. Blank file?'.format(input_file))
            return
        
        logging.info('Quick scan of file {}'.format(input_file))
        print('\nQuick scan of file {}'.format(input_file))
        for cat in cats:
            output = [cat, file_data[cat], "{:.1%}".format(file_data[cat]/file_data["Total records"])]
            output_string = '{}{}\t{}'.format(str(output[0]).ljust(16), str(output[1]).rjust(5), str(output[2]).rjust(7))
            logging.info(output_string)
            print(output_string)
        return file_data

    def text_scanner(self, input_file):
        # TODO:
        input_file_loc = os.path.join(self.input_dir, input_file)
        if input_file.endswith('.csv'):
            delimiter = ','
        else:
            delimiter = '\t'

        file_data = Counter()
        with open(input_file_loc, "r") as fin:
            cin = csv.reader(fin, delimiter=delimiter)
            for row in cin:
                pass
        return file_data

    def xlsx_scanner(self, input_file):
        # TODO:
        file_data = Counter()
        return file_data
