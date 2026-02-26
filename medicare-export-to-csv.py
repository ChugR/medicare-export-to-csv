#medicare-to-csv.py

"""
Overview
========
What happens behind the Medicare-Private insurance billing wall(s)?
Suppose I go to CVS and get a "free" flu shot. How much did CVS bill for it?
Where did that bill go? How much did my private insurance have to pay?
At the end of the year were my private insurance premiums worth it or did
medicare pay for everything?

This code is an exploration into finding answers to these questions.

Apparently each medical insurance billable event is first sent to Medicare.
There it is assigned a "Claim" number.
Then each treatment or procedure related to the event has a "Procedure Code" and
costs associated with it. Each of these is listed as a "Claim Line" for the Claim.

As a claim is processed the provider charges some amount. Medicare then may reduce
that amount (why? how?) or it may not to arrive at an Approved amount. Then
Medicare pays some amount the provider which may or may not be less than the
approved amount. I presume that the unpaid amount is then sent to my private
insurance who may or may not pay it. After that I get my bill.

The MyMedicare gui summarizes the claims but is not great at exposing details.
The exported claims text file shows everything. But each claim line contains a
dizzying amount of detail and there may be hundreds of claim lines for a given
claim. The CSV spreadsheet data omits many details in order to present an
executive overview of Medicare internals that makes sense.

Obviously you don't just look in one place to see what happened.
This code is part of a process:

 * Log in to myMedicare and export claims as a text file.
   The file is formatted like a flattened database text dump.
   It does not conform well to a known, structured file format.

 * This code reads that text file and writes a CSV file for spreadsheet import.

 * Import it into LibreOffice Calc or MS Excel.

 * Enjoy

Download data from medicare
---------------------------
  Login.
  Click on your profile.
  Follow link to downloads.
  Select 'as a .TXT file'.

  * The medicare gui makes it hard to download 'last year only', so
    go ahead and select _two_ years or whatever you like.

Code notes
----------
This code reads that file via 'fileinput' and writes a spreadsheet .CSV via STDOUT.
The 'c' of 'csv' is replaced by a '|' vertical bar as there are commas in some of the
exported dollar amount fields.

This code sums up the total claim amounts and the per-claim line amounts.

Year over year the exported data field names vary. This keeps maintenance on this
code high.

Command line
------------
> python medicare-export-to-csv.py my-data.txt > my-data.csv

File history
------------
Chug 11/11/2024
1.1 1/7/2026 - commentary
1.2 1/13/2026 - process claim lines
1.3 1/14/2026 - get it to show claims and claim lines.
                This generally spoils summing the columns since columns are
                overloaded.
1.5 2/24/2026 - Add code to sum claim lines for a claim and all claims.
1.6 2/25/2026 - Summarize and print Claim Lines Non-Covered numbers.
              - Some bug fixes, and commentary.

CSV output formatting
---------------------
CSV columns for claim and claim lines overload columns for different data types

| col 1|                col 2| col 3|       col 4|    col 5| col 6|       col 7|     col 8|
|------|---------------------|------|------------|---------|------|------------|----------|
|claim#|             provider|  date| amt charged| approved|  paid| bill-to-you| claimType|
|line# | procedure code/descr|  date|   submitted|  allowed|   <b>| non-covered|       <b>|
"""

import sys
import fileinput
from enum import Enum, auto
import traceback
from re import sub
from decimal import Decimal
import copy

version = 1.6

# key prefixes
HEADER_SEP = "--------------------------------"  # ignore this
PREFIX_NEW_CLAIM = "Claim Number"  # starts a claim
PREFIX_CLAIM_LINE = "Line number"  # starts a claim line
PREFIX_END_CLAIMS = "Prescription Drug"  # ends data of interest

# database csv separator
# commas won't work as CSV separators as commas are normal in the data. Use this separator.
db_sep = '|'

# parser state
class State(Enum):
    IDLE = auto()
    PROCESSING_CLAIM = auto()  # processing claim body after Number
    PROCESSING_CLAIM_LINES = auto()  # processing lines until next claim


def main_except(argv):
    # parsed data -> csv output formatting
    # map key is input file claim key value, map value is output CSV column header
    header_map: dict[str, str] = {
        "Claim Number:": "Claim #",
        "Provider:": "Provider",
        "Service Start Date:": "Date",
        "Amount Charged:": "Charged",
        "Medicare Approved:": "Approved",
        "text.claims.fieldLabels.medicarePaidToProvider:": "Paid",
        "You May be Billed:": "Your Bill",
        "Claim Type:": "Claim Type"}

    def print_csv_headers():
        print(db_sep.join(list(header_map.values())))

    # Storage for accumulating sum of all claims dollar amounts
    # One required for all claims and this is it.
    # Only the non-dummy lines are used.
    claims_accum = {
        "dummy1":                                        'All Claims',
        "dummy2":                          'Sum of all claims',
        "dummy3":                                          '.',
        "Amount Charged:":                                 Decimal(0),
        "Medicare Approved:":                              Decimal(0),
        "text.claims.fieldLabels.medicarePaidToProvider:": Decimal(0),
        "You May be Billed:":                              Decimal(0),
        "dummy4":                                          '.'}

    # computed list of non-dummy claims_accum keys
    # This is a convenience for later summing only the useful fields.
    claims_accum_keys = [x for x in list(claims_accum.keys())
                         if not x.startswith("dummy") ]

    # map key in input file claim line key value, map value is unused
    line_number_map: dict[str, str] = {
        "Line number:": "",
        "Procedure Code/Description:": "",
        "Date of Service From:": "",
        "Submitted Amount/Charges:": "",
        "Allowed Amount:": "",
        "Blank Space": "",
        "Non-Covered:": ""}

    # Storage for sum of one claim's line dollar amounts
    # One required for each claim and this is a template.
    lines_accum_template = {
        "dummy1": "This claim",
        "dummy2": "Sum of claim lines",
        "dummy3": "",
        "Submitted Amount/Charges:": Decimal(0),
        "Allowed Amount:": Decimal(0),
        "dummy4": "",
        "Non-Covered:": Decimal(0)}

    # computed list of non-dummy lines_accum
    lines_accum_keys = [x for x in list(lines_accum_template.keys())
                         if not x.startswith("dummy") ]

    # Inconsistency alert:
    #  * Claim objects have a "You May Be Billed" field which is always zero.
    #  * Claim Lines have a "Non-Covered" field which often is non-zero.
    # As a naive citizen I'd expect the "You May Be Billed" claim field to be the
    # sum of the claim lines' "Non-Covered" values. But no. So, accumulate all the
    # Non-Covered sums here and print them at the end.
    non_covered_lines_accum = Decimal(0)

    # storage for as-parsed csv line
    # this one dict object stores claims and claim lines
    data_map: dict[str, str] = {}

    # storage for this claim's lines accumulation
    lines_accum = copy.deepcopy(lines_accum_template)

    def add_data_value(raw_line):
        # This adds a key:value pair from the input text line.
        # It adjusts some values and formatting, too.
        key_pos = raw_line.find(':')
        assert (key_pos >= 0)
        key = raw_line[0:key_pos + 1]
        value = raw_line[key_pos + 1:]
        value = value.lstrip(" $")
        if key == "Line number:":  # fix up the line number value
            value = "...Line " + value  # Adjust line number for visual ID
            data_map["Blank Space"] = "."
        if key == "Provider:" or key.startswith("Procedure Code"):
            value = value[0:50]  # Some values might be hundreds of characters. trim them.
        data_map[key] = value

    def decode_raw_dollar_value(raw_value):
        value = Decimal(sub(r'[^\d.]', '', raw_value))
        return value

    def accumulate_dollar_value(from_map, to_map, key):
        raw_value = from_map[key]
        to_map[key] += decode_raw_dollar_value(raw_value)
    
    def print_data(key_list):
        value_list = [data_map[key] for key in key_list]
        print(db_sep.join(value_list))
    
    def print_data_as_claim():
        print_data(header_map.keys())
    
    def print_data_as_claim_line():
        print_data(line_number_map.keys())
    
    def flush_data(p_state):
        if p_state == State.IDLE:
            pass
        elif p_state == State.PROCESSING_CLAIM:
            print(".")
            print_data_as_claim()
            # accumulate totals for this claim
            for key in claims_accum_keys:
                accumulate_dollar_value(data_map, claims_accum, key)
        elif p_state == State.PROCESSING_CLAIM_LINES:
            print_data_as_claim_line()
            # accumulate totals for this clam line
            for key in lines_accum_keys:
                accumulate_dollar_value(data_map, lines_accum, key)
        data_map.clear()
    
    # format claims accumulations Decimal values for printing
    def format_claim_value(the_map, cvkey):
        the_map[cvkey] = format(Decimal(the_map[cvkey]), ".2f")

    # debug help function
    def debug_print(what, info=""):
        pass
        #sys.stderr.write("DEBUG: %s '%s'\n" % (what, info))

    # begin main_except code
    print("%s version: %s" % (sys.argv[0], version))

    # The main code consists of two major loops.
    # Loop 1 reads the input file. On the way it trims and tidies the input.
    # Loop 2 reads the tidied input, computes sums, and prints the CSV output.

    parse_state = State.IDLE

    # loop 1: filter input file to create local array of raw source in 'lines'
    # Keep only from first claim to claims termination marker
    raw_lines = []
    ignore_before_first_claim = True
    for in_line in fileinput.input():
        in_line = in_line.strip()
        if len(in_line) == 0:
            continue  # ignore blank lines
        if in_line.startswith(HEADER_SEP):
            continue  # ignore separator lines
        if ignore_before_first_claim:
            if not in_line.startswith(PREFIX_NEW_CLAIM):
                continue
            ignore_before_first_claim = False
        debug_print("Raw input:", in_line)
        if in_line.startswith(PREFIX_END_CLAIMS):
            break
        raw_lines.append(in_line)

    # print CSV file headers
    print(db_sep.join(list(header_map.values())))

    # loop 2: process the tidy input data
    # accumulate and print stuff
    for in_index in range(len(raw_lines)):
        in_line = raw_lines[in_index]
        debug_print("processing input", in_line)
        if in_line.startswith(PREFIX_NEW_CLAIM):
            flush_data(parse_state)

            # Done dumping claim lines. Print the totals
            if parse_state != State.IDLE:
                for key in lines_accum_keys:
                    format_claim_value(lines_accum, key)
                value_list = list(lines_accum.values())
                print(db_sep.join(value_list))
                # accumulate the non-covered values
                non_covered_lines_accum += Decimal(lines_accum["Non-Covered:"])
            lines_accum = copy.deepcopy(lines_accum_template)

            parse_state = State.PROCESSING_CLAIM
        elif in_line.startswith(PREFIX_CLAIM_LINE):
            flush_data(parse_state)
            parse_state = State.PROCESSING_CLAIM_LINES
        add_data_value(in_line)
    flush_data(parse_state)

    # Print last claim lines summary and accumulate it
    for key in lines_accum_keys:
        format_claim_value(lines_accum, key)
    value_list = list(lines_accum.values())
    print(db_sep.join(value_list))
    # accumulate the non-covered values
    non_covered_lines_accum += Decimal(lines_accum["Non-Covered:"])

    # Done dumping claims. Print the totals.
    print()
    for key in claims_accum_keys:
        format_claim_value(claims_accum, key)
    value_list = list(claims_accum.values())
    print(db_sep.join(value_list))

    # Print the sum of the Non-Covered values from all the Claim Lines
    sum_lines_accum = {
        "d1": "All Claim Lines",
        "d2": "Sum of Non-Covered amounts",
        "d3": "",
        "d4": "",
        "d5": "",
        "d6": "",
        "d7": format(non_covered_lines_accum, ".2f")
    }
    print(db_sep.join(list(sum_lines_accum.values())))

    """
    # Note: This is nice info but it spoils the general spreadsheet.
    # TODO: add a command line switch to turn this on and off.
    # Medicare exports text fields for claims and claim lines.
    # The resulting CSV has columns shared for both text field type.
    # Print a legend to show original text field names.
    print()
    print()
    print("What do these column values mean?")
    print("Good question. I don't know for sure but here are the labels from the exported text")
    print("Original medicare export field names for CLAIM type")
    claim_keys = [x for x in list(header_map.keys())]
    line = ""
    for i in range(len(claim_keys)):
        line = i * db_sep
        line += claim_keys[i]
        print(line)

    print()
    print("Original medicare export field names for CLAIM LINE type")
    line_keys = [x for x in list(line_number_map.keys())]
    line = ""
    for i in range(len(line_keys)):
        line = i * db_sep
        line += line_keys[i]
        print(line)
    """

    pass


def main(argv):
    try:
        main_except(argv)
        return 0
    #    except ExitStatus, e:
    #        return e.status
    except Exception as e:
        traceback.print_exc()
        print("%s: %s" % (type(e).__name__, e))
        return 1


if __name__ == "__main__":
    main(sys.argv)
