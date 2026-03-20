# WFP Food Security Outcome Monitoring Analysis Workflow

This repository did not include an uploaded WFP survey extract at the time of analysis, so I added a reusable Python workflow to process a standard **CSV** export when the dataset is available.

## What the script does

`scripts/wfp_food_security_analysis.py`:

1. Profiles the input file columns and calculates missingness.
2. Auto-maps common WFP-style variable names for:
   - Food Consumption Score (FCS)
   - Reduced Coping Strategies Index (rCSI)
   - Livelihood Coping Strategies (LCS)
   - Food Expenditure Share (economic vulnerability proxy)
3. Produces household-level CARI classifications.
4. Disaggregates CARI results by:
   - gender of household head
   - location
5. Exports:
   - `analysis_summary.json`
   - `household_results.csv`
   - `cari_categories.svg`

## Methodological assumptions

The script uses the following default assumptions, which should be checked against the questionnaire/codebook before using results operationally:

- **FCS thresholds**
  - Poor: `0-21`
  - Borderline: `21.5-35`
  - Acceptable: `>35`
- **rCSI thresholds**
  - Low: `<4`
  - Medium: `4-18`
  - High: `>18`
- **LCS severity**
  - None / stress / crisis / emergency from binary variables
- **Food Expenditure Share thresholds**
  - Low: `<50%`
  - Medium: `50-65%`
  - High: `65-75%`
  - Very high: `>75%`
- **CARI roll-up**
  - Uses the worse of:
    - current status: FCS and rCSI
    - coping capacity: LCS and food expenditure share

## How to run

```bash
python scripts/wfp_food_security_analysis.py path/to/your_dataset.csv
```

If no path is supplied, the script searches the repository for a CSV file.

## Current limitation

Because no uploaded survey data file was present in the working tree, the script could not generate actual household results in this run.
