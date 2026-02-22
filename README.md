# Alfred – A Streamlit package to manage Chemistry courses 

## Analyze Attendance

This module reads the attendance data stored in a private Google sheet and prepares an attendance report.

## Analyze Grades

This module analyzes grading stored in a folder of Gradescope scores for an assignment. To get the folder, open the assignment in Gradescope and select "Export Evaluations" at the bottom of the page.

Drag the folder onto "Drag and drop files here." Give the analysis a name in the modal dialog. An analysis of all problems will appear. To analyze a single problem, use the dropdown menu in the sidebar to select it.

## Combine PS Scores

This module combines problem set (PS) scores from Gradescope and Pearson using the weighting defined in Settings, then prepares a csv for upload to Canvas. _Note:_ This script preserves any 'EX' entries in the Canvas gradebook. No grade is recorded for a pre-existing 'EX'.

## Make Histogram

This module produces a histogram of grades from a Gradescope csv and optionally calculates the estimated grade cutoffs based on the course median. This module requires Chrome be installed on your computer for the png output.

## Update Roster

This module compare the current Canvas roster, as given by the Canvas gradebook, with the current Alfred roster, which is read from the shared Google sheet. The script then adds any new enrollees to the Alfred roster upon request.

## Add Student IDs to Pearson Roster

This module adds student IDs pulled from the current Canvas gradebook to the Pearson roster. The matching is performed based on netID (default) or student name (backup). The module produces a csv which is used to update the Pearson roster, which is then reuploaded to Pearson.

## Settings

This module handles the settings for the various modules. The data are stored in Alfred/.streamlit/prefs.toml. The file can also be edited with a text editor.

## Installation
– Use Anaconda to make an env containing numpy, streamlit, pandas, plotly, tomlkit, git  
– pip install gspread oauth2client  
– pip install watchdog  
– pip install --upgrade kaleido  (see _Note 3_ below)  
– cd to folder that will contain Alfred  
– git clone https://github.com/MAHines/Alfred.git   
– copy secrets.toml to Alfred/.streamlit

_Note 1:_ The folder Alfred/.streamlit is hidden by default. To show/hide invisible folders on a Mac, press command + shift + . (period).  

_Note 2:_ To obtain secrets.toml for Cornell Chemistry, e-mail Melissa.Hines@cornell.edu. 

_Note 3:_ The kaleido package [requires Chrome](https://www.google.com/chrome/) to be on your computer. If you have difficulty installing kaleido, your pip may be out of date. If so, run
    
–  python -m pip install --upgrade pip

## Running Alfred from the command line
– cd to Alfred folder  
– streamlit run Alfred.py  

## Updating Alfred from the command line
– cd to Alfred folder  
– git pull  

