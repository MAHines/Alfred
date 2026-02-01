# Alfred – A Streamlit package to manage Chemistry courses 

## Analyze Attendance

This module reads the attendance data stored in a private Google sheet and prepares an attendance report.

## Settings

This module handles the settings for the various modules. The data are stored in Alfred/.streamlit/prefs.toml. The file can also be edited with a text editor.

## Installation
– Use Anaconda to make an env containing numpy, streamlit, pandas, plotly, tomlkit, git  
– pip install gspread oauth2client  
– pip install watchdog  
– cd to folder that will contain Alfred  
– git clone https://github.com/MAHines/Alfred.git   
– copy secrets.toml to Alfred/.streamlit

_Note 1:_ The folder Alfred/.streamlit is hidden by default. To show/hide invisible folders, press command + shift + . (period).  

_Note 2:_ To obtain secrets.toml for Cornell Chemistry, e-mail Melissa.Hines@cornell.edu. 

## Running Alfred from the command line
– cd to Alfred folder  
– streamlit run Alfred.py  
