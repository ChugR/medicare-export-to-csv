# medicare-export-to-csv
Converts exported USA medicare claims text file to a CSV file 
for enhanced comprehension.

# Introduction

Why does this code exist?

## Motivation

What happens behind the Medicare-Private insurance billing wall(s)?
Suppose one goes to CVS (a major USA pharmacy chain) and gets a _free_ flu shot. 

 * How much did CVS bill for it? 
 * How much did Medicare allow vs. the original charge?
 * How much did Medicare pay?
 
 * How many CVS visits were there? What was each one for?

This code is an exploration into finding answers to these questions.

The resulting spreadsheet is particularly useful for understanding a complex series
of medical events for a loved one. 

* Has Grandmother had a flu shot this year? When?
* Has Grandmother had a Covid shot this year?
* How many hospitalizations has Grandmother had this year?
* When exactly where those hospitalizations and for what problems?

Were this code not so useful then the author might never have published it.

## Understanding the Medicare billing process

The author disclaims understanding the Medicare billing process. This explanation is just a best guess.
However, this understanding has guided the design of this code.

* Each medical insurance billable event is first sent to Medicare.
* There it is assigned a Medicare *Claim* number.
* Then each treatment or procedure related to the event has a *Procedure Code* and
costs associated with it. 
* Each of these procedures is listed as a *Claim Line* for the Claim. 
* A claim like a flu shot may have two claim lines. 
* A claim like a heart attack with a hospital stay may have hundreds of claim lines. 

# Medicare reports available

Medicare already provides some very nice reports, and they may be all you ever need.
But they also hold so many details that they do not
provide an executive overview.

## PDF export

One may download a PDF export of claims for some number of years. These reports have all the
details that this software is interested in but the details are not summarized for a high-level
overview. The problems are:

* A single years' worth of reporting may be spread over 50 or 100 pages of detail.
* Each claim line has a procedure code that may be 500+ characters long.

In the PDF the claim lines are shown in tables with many columns. The procedure code is in one
column and the 500-character description may require almost a whole page. It doesn't take very 
many claim lines spread across multiple pages of printout to lose track of the big picture.

## TXT export

One may download a TXT export for the same time period. This export format is not intended for
a human user. In this report each field of every claim line of every claim is presented as a single line of text. 
Again, there is a huge amount of detail and no high-level overview.

# This code provides

An executive summary of Medicare exported data.

* This code reads a TXT export file and condenses each Claim and Claim Line into a single spreadsheet 
line in CSV file format.

* Claim Lines are summed for each Claim.
* Claims are summed for the all Claims.

* Excessively long fields, like Procedure Code, are trimmed. The general idea of the Claim Line is 
revealed but without run-on detail.

## Specific spreadsheet column overloads

The CSV output puts Claim and Claim Line data into the same spreadsheet output columns. 
As a result the column titles don't exactly correspond to the data in the exported Medicare TXT file.
Here's how source data fields (From Claims and Claim Lines) is placed in spreadsheet columns.

| Spreadsheet Column | Field from Claim                               | Field from Claim Line      |
|--------------------|------------------------------------------------|----------------------------|
| Claim #            | Claim Number                                   | Line Number                |
| Provider           | Provider                                       | Procedure Code/Description |
| Date               | Service Start Date                             | Date of Service From       |
| Charged            | Amount Charged                                 | Submitted Amount/Charges   |
| Approved           | Medicare Approved                              | Allowed Amount             |
| Paid               | text.claims.fieldLabels.medicarePaidToProvider |                            |
| Your Bill          | You May be Billed                              | Non-Covered                |
| Claim Type         | Claim Type                                     |                            |

# Demo

The _demo_ directory illustrates the life cycle of this code in practice.

## File contents

| File           | Contains                                                    |
|----------------|-------------------------------------------------------------|
| metc-25-1.txt  | Raw text export from Medicare                               |
| metc-25-1.csv  | CSV created from raw text file by this code                 |
| metc-25-1.pdf  | Image of OpenOffice Calc page after importing the .csv file |

## Command line to create the .csv file.

```bash
cd demo
python ../medicare-export-to-csv.py metc-25-1.txt > metc-25-1.csv
```

## Producing the spreadsheet from the CSV file

Then you may import the CSV file to your spreadsheet. For this demo
* Columns D..G are formatted as _Currency_.
* Some column widths were adjusted.
* The spreadsheet was Exported as PDF to generate the .pdf file.

# TODO

1. There appears to be a bug (imagine that!) in the Medicare export TXT code. 
The _Claim_ object includes a field called 
_text.claims.fieldLabels.medicarePaidToProvider_. The TXT export is probably missing a
level of indirection when it exports this field as TXT. In the Medicare PDF export each claim
has a field called _Provider Paid_. That's probably how the TXT export field should be labeled as well.
Where do I submit a bug report and/or a pull request?
2. The field names appear to change as code is being developed by Medicare during the year.
The field names have changed between 2024 and 2025.
This code could use a flexible way to handle field name changes. This problem
is always a risk with this style of post-processor code. 
See TODO #1 when the indirection gets added: this code has to change to handle the new field name.





