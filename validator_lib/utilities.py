import sys
import re
import os
import logging

from crl_lib.year_utilities import find_years_first_last
from validator_lib.validator_config import ValidatorConfig
from validator_lib.bulk_validator_preferences import BulkConfig


def get_unused_filename(file_location):
    """
    Check if a filename is taken. If it is, add a number increment to the old filename until
    we find an empty file. So a duplicate of "myfile.txt" would become "myfile(1).txt", then
    "myfile(2).txt", and so on.

    Fails after 999 files, to avoid runaway processes.
    """
    if not os.path.isfile(file_location):
        return file_location

    new_file_number = 0
    path_base, full_filename = os.path.split(file_location)
    base_filename = full_filename[:full_filename.rindex('.')]
    file_extension = full_filename[full_filename.rindex('.'):]
    while True:
        new_file_number += 1
        new_filename = '{}({}){}'.format(base_filename, new_file_number, file_extension)
        new_file_location = os.path.join(path_base, new_filename)
        if not os.path.isfile(new_file_location):
            return new_file_location
        if new_file_number >= 999:
            raise Exception("At least 1000 files with the base name {}. Runaway process?".format(full_filename))


def get_abbrev_from_input_filename(input_file):
    if '_AUTOGENERATED_FILE.tsv' in input_file:
        return input_file.replace('_AUTOGENERATED_FILE.tsv', '')
    working_filename = input_file.replace('DATA.', '')
    working_filename = working_filename.replace('.', '_')
    working_filename = working_filename.replace(' ', '_')
    working_filename = working_filename.split("_")
    return working_filename[0]


def left_pad_field_number(field_number):
    """SQLite stores numbers as integers, meaning '004' will be stored as '4'. Repair these fields."""
    if not field_number:
        return ''
    field_number = str(field_number)
    if not field_number.isdigit():
        return field_number
    field_number = field_number.zfill(3)
    return field_number


def check_holdings_data_for_magic_words(holdings, holdings_nonpublic_notes, holdings_public_notes, search_type):
    search_data = {
        'completeness': ['inc', 'compl', 'miss', 'lack', 'without', 'w/o', 'repr'],
        'binding': ['bound', r'bd\.? w'],
        'nonprint': [r'd\.?v\.?d\.?', r'\bc\.?d\.?\b']
    }
    all_holdings_segments_to_check = [holdings, holdings_nonpublic_notes, holdings_public_notes]

    for holdings_segment in all_holdings_segments_to_check:
        if not holdings_segment:
            continue
        holdings_segment = str(holdings_segment)
        for search_string in search_data[search_type]:
            if re.search(search_string, holdings_segment.lower()):
                return '1'
    return ''


def get_valid_serial_types():
    return {"m", "p", "\\", " ", "-", '|'}


def get_valid_forms():
    return {"r", "\\", " ", "-"}


def double_check_slash_start_year(bib_year, bib_string, holdings_year, holdings_string):
    """
    Double check holdings starts, in an attempt to be sure that 2000/2001 isn't listed as too soon for a bib start date
    of 2001.

    Returns True on a good date.
    """
    bib_year = get_earlier_of_slash_year(bib_year, bib_string)
    holdings_year = get_later_of_slash_year(holdings_year, holdings_string)
    if int(holdings_year) >= int(bib_year):
        return True
    return False


def double_check_slash_end_year(bib_year, bib_string, holdings_year, holdings_string):
    """
    Double check holdings ends, in an attempt to be sure that 2000/2001 isn't listed as too late for a bib start date
    of 2000.

    Returns True on a good date.
    """
    holdings_year = get_earlier_of_slash_year(holdings_year, holdings_string)
    bib_year = get_later_of_slash_year(bib_year, bib_string)
    if int(holdings_year) <= int(bib_year):
        return True
    return False


def get_earlier_of_slash_year(year, data_segment):
    """For the year checks functions."""
    year_regex = r'(?:1[6789]\d\d|20[01]\d|2020)'
    short_year = str(year)[2:]
    m = re.search(r'({}) *[-/] *(?:{}|{})'.format(year_regex, year, short_year), data_segment)
    if m:
        found_year = m.group(1)
        if int(found_year) < int(year):
            year = found_year
    return year


def get_later_of_slash_year(year, data_segment):
    """For the year checks functions."""
    second_year_regex = r'(?:1[6789]\d\d|20[01]\d|2020|\d\d)'
    m = re.search(r'{} *[-/] *((?:{}))\b'.format(year, second_year_regex), data_segment)
    if m:
        found_year = m.group(1)
        if len(found_year) == 2:
            found_year = str(year)[:2] + found_year
        if int(found_year) > int(year):
            year = found_year
    return year


def get_jstor_issns(validator_data_folder):
    jstor = set()
    data_files = os.listdir(validator_data_folder)
    for data_file in data_files:
        if not data_file.lower().startswith('jstor'):
            continue
        if data_file.lower().endswith('xlsx'):
            continue
        jstor_file = os.path.join(validator_data_folder, data_file)
        try:
            with open(jstor_file, 'r', encoding='utf8') as fin:
                raw_issns = [line.rstrip() for line in fin]
        except UnicodeDecodeError:
            with open(jstor_file, 'r', encoding='ascii') as fin:
                raw_issns = [line.rstrip() for line in fin]
        for issn in raw_issns:
            if not issn or '-' not in issn:
                continue
            if 'issn' in issn.lower():
                continue
            jstor.add(issn)
    return jstor


def get_first_last_year_from_regular_holdings(regular_holdings_list):
    all_first_last = []
    for regular_holdings_str in regular_holdings_list:
        first_last_tuple = find_years_first_last(regular_holdings_str)
        if first_last_tuple[0]:
            all_first_last.extend(list(first_last_tuple))
    all_first_last.sort()
    try:
        first_year = all_first_last[0]
        last_year = all_first_last[-1]
    except IndexError:
        first_year = ""
        last_year = ""
    return first_year, last_year


class FieldsAndIssuesFinder():
    """
    Class for retrieving the correct fields and issue data while running in bulk/headless mode.

    For record fields will first look to the Validator configuration file for any specific data, then to the bulk data. 
    
    For disqualifying issues it first looks to the bulk data for any specific issues, then to the Validator configuration.

    The idea behind this discrepancy is to always look for specifics first. 
    """

    def __init__(self):
        self.validator_config = ValidatorConfig()
        self.bulk_config = BulkConfig()
        self.use_validator_config = False

    def get_fields_for_individual_file(self, filename):
        """
        Look for appropriate fields from the bulk config when presented with an individual file.
        """
        input_fields = self.validator_config.get_input_fields(filename)
        if input_fields:
            self.use_validator_config = True
            return input_fields
        self.use_validator_config = False
        inst_name = self.get_institution_name_from_filename(filename)

        if inst_name in self.bulk_config.bulk_config_data:
            return self.bulk_config.bulk_config_data[inst_name]['input_fields']
        
        elif inst_name in self.bulk_config.associated_names_map:
            program_name = self.bulk_config.associated_names_map[inst_name]
            return self.bulk_config.bulk_config_data[program_name]['input_fields']

    def get_issues_for_individual_file(self, filename=None):
        """
        Look for appropriate issues from the bulk config when presented with an individual file.

        If we found the file fields in the Validator config, use the issues from the same place.
        """
        if filename:
            inst_name = self.get_institution_name_from_filename(filename)

            # NOTE: The bulk/headless issue preferences don't work at the moment, so this section will not find anything.
            if inst_name in self.bulk_config.bulk_config_data and not self.use_validator_config:
                logging.info('Using disqualifying issues set for {}'.format(inst_name))
                return self.bulk_config.bulk_config_data[inst_name]['disqualifying_issues']
            
            elif inst_name in self.bulk_config.associated_names_map:
                program_name = self.bulk_config.associated_names_map[inst_name]
                logging.info('Using disqualifying issues set for {}'.format(program_name))
                return self.bulk_config.bulk_config_data[program_name]['disqualifying_issues']
        try:
            if self.validator_config.config['disqualifying_issues']:
                return self.validator_config.config['disqualifying_issues']
        except KeyError:
            pass
        # return defaults if nothing else is set
        logging.warning('No disqualifying issues set. Using defaults.')

        default_issues = self.validator_config.get_default_disqualifying_issues()
        return dict(default_issues)

    def get_institution_name_from_filename(self, filename):
        file_proper =  os.path.split(filename)[-1]
        return file_proper.split('.')[0].lower()


def get_disqualifying_issue_categories(input_file=None):
    disqualifying_issue_categories = set()
    fields_and_issues_finder = FieldsAndIssuesFinder()
    disqualifying_issues = fields_and_issues_finder.get_issues_for_individual_file(input_file)

    for issue in disqualifying_issues:
        if disqualifying_issues[issue]:
            disqualifying_issue_categories.add(issue)
    return disqualifying_issue_categories

