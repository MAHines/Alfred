# This script reads in 3 csv's:
#                   Canvas gradebook
#                   Canvas Late Report, (Course Analytics -> Late Assignments)
#                   Gradescope gradebook (Assignments -> Download Grades)
# The script assumes that:
#       – The names of the pre- and post-lab assignments in Gradebook start with the same word as in canvas
#       – That word is unique to the lab
#       – The pre- and post-lab assignments have "pre-lab" and "post-lab" in the assignment names
# The script gives a 10 min grace period as per Cynthia

# Note: The Canvas Late Report has an "average data latency" of ~ 8 hrs. No immediate updates!

import streamlit as st
import pandas as pd
import numpy as np
import utils
import re

def read_gradescope_csv():
    """ Reads the Gradescope gradebook from a csv. Renames a column for consistency with Canvas
           
        gs_df: SIS User ID, P…
    """
    if st.session_state['gradescope_key'] is not None:
  
        # The Gradescope csv's have a bunch of columns that are not useful to us. We avoid loading that
        #   info using the info in sub_strings and usecols
        # sub_strings = ['Submission', 'Max', 'Lateness','First Name', 'Last Name', 'section_name']
        columns = ["Student", "ID", "SIS User ID", "SIS Login ID", "Section"]
        good_sub_strings = ['lab']
        usecols = lambda x: (x in columns) or ((any(s in x.lower() for s in good_sub_strings)))
    
        gs_df = pd.read_csv(st.session_state['gradescope_key'],
                                 dtype=str,
                                 usecols = usecols
                                 )
        gs_df.rename(columns={'SID': 'SIS User ID'}, inplace=True)
        st.session_state['gs_df'] = gs_df

def reset_uploader():
    """Function to clear the uploaded file data and show the uploader again."""
    st.session_state['cnv_df'] = None
    st.session_state['pearson_df'] = None
    st.session_state['gs_df'] = None

# Initialization 
if 'cnv_df' not in st.session_state:
    st.session_state['cnv_df'] = None
if 'pearson_df' not in st.session_state:
    st.session_state['pearson_df'] = None
if 'gs_df' not in st.session_state:
    st.session_state['gs_df'] = None

st.markdown('## Calculate Lab Scores for Upload to Canvas')

st.write('The names of the pre- and post-lab assignments in Gradescope must start with the same word as in Canvas.')
st.write('That starting word must unique to the lab.)
st.write('The pre- and post-lab assignments have "pre-lab" and "post-lab" in the assignment names.')

st.button("Reset or work on a different course.", 
            on_click=reset_uploader,
            type = 'primary')

# Logic to display the Gradescope file uploader
if st.session_state['gs_df'] is None:
    # Display the uploader only if no file has been uploaded yet
    st.file_uploader(
        "Upload Gradescope gradebook here:",
        type=['csv'],
        accept_multiple_files=False,
        key = 'gradescope_key',
        on_change = read_gradescope_csv
    )
else:
    st.write('#### :gray[Gradescope gradebook already uploaded.]')

# Logic to display the Canvas gradebook file uploader
if st.session_state['cnv_df'] is None:
    # Display the uploader only if no file has been uploaded yet
    st.file_uploader(
        "Upload Canvas gradebook here:",
        type=['csv'],
        accept_multiple_files=False,
        key = 'canvas_key',
        on_change = read_canvas_csv
    )
else:
    st.write('#### :gray[Canvas gradebook already uploaded.]')

# Logic to display the Canvas Late Report file uploader
if st.session_state['pearson_df'] is None:
    # Display the uploader only if no file has been uploaded yet
    st.file_uploader(
        "Upload Pearson gradebook here:",
        type=['csv'],
        accept_multiple_files=False,
        key = 'pearson_key',
        on_change = read_pearson_csv
    )
else:
    st.write('#### :gray[Pearson gradebook already uploaded.]')

utils.shared_sidebar()
