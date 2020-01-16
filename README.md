# hca-to-dsp-tools
Repository that contains code to convert HCA submissions to DSP submissions.


Currently **WIP** so probably most of the code won't work.

# How to use

First, please install requirements by running `pip install -r requirements.txt` from the root of the repository. Then you will need to provide your credentials for the DSP service (How to obtain those credentials [here](https://submission.ebi.ac.uk/api/docs/guide_accounts_and_logging_in.html). Please note that you will need to be logged in into the `explore.ebi` dev environment in order to use the `-test` DSP. 



[WIP}

# What are the scripts

- The scripts inside the folder `importer` are intended to help towards the conversion from HCA metadata (Currently only spreadsheets) to submittable jsons to the DSP.

- The script inside the folder `dsp_cli` is a python object with several functions to navigate the DSP CLI, such as `select_new_team`, `create_empty_submission`, `submit_new_sample`, etc.

