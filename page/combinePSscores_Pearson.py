# This script combines PS scores from Gradescope and Pearson using the weighting defined in
#   the settings, then prepares a csv for upload to Canvas. Note: This script preserves any
#   'EX' entries in the Canvas gradebook. No grade is recorded for a pre-existing 'EX'.
#
#   Inputs CSVs: Gradescope gradebook, Pearson gradebook, Canvas gradebook
#   Output CSV: merged_df goes into psGradesForUpload.csv
#
#   Canvas: The PS assignment must have been initialized with a name starting with 'PS ' + integer
#   Gradescope: The PS assignment must start with 'PS ' + integer
#   Pearson: The PS assignment must start be 'PS ' + integer + ' Mastering'
#
# Note that the bizarre 2nd and 3rd rows of the Canvas gradebook.csv are not really necessary,
#   so the psGradesForUpload.csv file can be used as is.

import streamlit as st
import pandas as pd
import numpy as np
import utils
import re

def read_gradescope_csv():
    """ Reads the Gradescope gradebook from a csv. Renames a column for consistency with Canvas
           
        gs_df: SIS User ID, PS…
    """
    if st.session_state['gradescope_key'] is not None:
  
        # The Gradescope csv's have a bunch of columns that are not useful to us. We avoid loading that
        #   info using the info in sub_strings and usecols
        # sub_strings = ['Submission', 'Max', 'Lateness','First Name', 'Last Name', 'section_name']
        sub_strings = ['Submission', 'Max', 'Lateness']
        columns = ["SID"]
        usecols = lambda x: (x in columns) or ((x.startswith('PS')) and (not any(s in x for s in sub_strings)))
    
        gs_df = pd.read_csv(st.session_state['gradescope_key'],
                                 dtype=str,
                                 usecols = usecols
                                 )
        gs_df.rename(columns={'SID': 'SIS User ID'}, inplace=True)
        st.session_state['gs_df'] = gs_df


def read_pearson_csv():
    """ Reads the Pearson gradebook from a csv. Renames some column names for consistency with Canvas
           
        pearson_df: SIS User ID, SIS Login ID, Section, PS…
    """
    if st.session_state['pearson_key'] is not None:
  
        # Read in the required columns of canvas csv 
        columns = ["Student ID", "ID", "SIS User ID", "SIS Login ID", "Section"]   # All required for re-upload
        usecols = lambda x: (x in columns) or (x.startswith('PS '))
        pearson_df = pd.read_csv(st.session_state['pearson_key'],
                             dtype=str,
                             skiprows=3,
                             usecols = usecols
                             )
        pearson_df.rename(columns={'Student ID': 'SIS User ID'}, inplace=True)
        st.session_state['pearson_df'] = pearson_df

def read_canvas_csv():
    """ Reads the canvas gradebook from a csv. DOES NOT rename idiotic column names, 
        because we have to re-upload
           
        cnv_df: Student, ID, SIS User ID, SIS Login ID, Section, PS…
    """

    if st.session_state['canvas_key'] is not None:
  
        # Read in the required columns of canvas csv 
        columns = ["Student", "ID", "SIS User ID", "SIS Login ID", "Section"]   # All required for re-upload
        usecols = lambda x: (x in columns) or (x.startswith('PS '))
        cnv_df = pd.read_csv(st.session_state['canvas_key'],
                             dtype=str,
                             skiprows=[1,2],
                             usecols = usecols
                             )
        cnv_df = cnv_df[~cnv_df['Student'].str.contains('Student, Test', na=False)]
        st.session_state['cnv_df'] = cnv_df

def reset_uploader():
    """Function to clear the uploaded file data and show the uploader again."""
    st.session_state['cnv_df'] = None
    st.session_state['pearson_df'] = None
    st.session_state['gs_df'] = None
    st.session_state['max_ps_num'] = -1
    st.session_state['selected_PS'] = st.session_state['PS_select_list'][0]
    st.session_state['last_PS'] = 0

def handle_PS_change():
    selected_value = st.session_state['selected_PS']
    st.session_state['last_PS'] = st.session_state['PS_select_list'].index(selected_value)

# Initialization 
if 'cnv_df' not in st.session_state:
    st.session_state['cnv_df'] = None
if 'pearson_df' not in st.session_state:
    st.session_state['pearson_df'] = None
if 'gs_df' not in st.session_state:
    st.session_state['gs_df'] = None
if 'max_ps_num' not in st.session_state:
    st.session_state['max_ps_num'] = -1
if 'toml_dict' not in st.session_state:
    utils.read_prefs()
if 'last_PS' not in st.session_state:
    st.session_state['last_PS'] = 0
st.session_state['PS_select_list'] = ['None']
for i in range(14):
    ps_str = 'PS ' + str(i + 1)
    st.session_state['PS_select_list'].append(ps_str)

st.markdown('## Combine PS Scores for Upload to Canvas')

st.write('Canvas: The PS name should be \'PS \' + integer.')
st.write('Gradescope: The PS name should be \'PS \' + integer')
st.write('Pearson: The PS name should be \'PS \' + integer + \' Mastering\'')

st.button("Reset or work on a different course.", 
            on_click=reset_uploader,
            type = 'primary')

if st.session_state['last_PS'] < 1:
    st.selectbox(
        'Start by selecting the LAST PS to be combined', # Label for the dropdown
        st.session_state['PS_select_list'],                         # The options to display
        key = 'selected_PS',                # Always start at none selected
        on_change=handle_PS_change
    )
else:
    info_str = '#### Combining grades through PS ' + str(st.session_state['last_PS']) + ' using Grade = '
    info_str += "{:.2f}".format(1 - float(st.session_state['toml_dict']['user']['pct_pearson'])) 
    info_str += ' Gradescope + ' 
    info_str += "{:.2f}".format(float(st.session_state['toml_dict']['user']['pct_pearson'])) 
    info_str += ' Pearson. The weighting can be changed in Settings.'
    st.markdown(info_str)

if st.session_state['last_PS'] > 0:
    info_str = '#### Upload csv\'s from Gradescope, Pearson, and Canvas.' 
    st.write(info_str)
    
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
    
    # Logic to display the Pearson file uploader
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

    # If all df's loaded, do the analysis
    if all(v is not None for v in [st.session_state['cnv_df'],st.session_state['pearson_df'],st.session_state['gs_df']]):
        
        # Work on local copies 
        cnv_df = st.session_state['cnv_df'].copy()
        pearson_df = st.session_state['pearson_df'].copy()
        gs_df = st.session_state['gs_df'].copy()
        
        # Find the ps numbers included in the canvas gradebook. These cannot be modified
        cnv_ps_columns = [col for col in cnv_df.columns if col.startswith('PS ') and col[3].isdigit()]
        ps_numbers = []
        ps_numbers_to_remove = []
        for col in cnv_ps_columns:
            ps_num = int(re.search(r'PS\s*(\d+)', col).group(1))
            if ps_num <= st.session_state['last_PS']:
                ps_numbers.append(ps_num)
            else:
                cnv_df.drop(columns = [col], inplace=True)
                gs_col_name = 'PS ' + str(ps_num)
                gs_df.drop(columns = [gs_col_name], inplace = True)
                pearson_col_name = 'PS ' + str(ps_num) + ' Mastering'
                pearson_df.drop(columns = [pearson_col_name], inplace = True)
        
        # We may have dropped some cnv columns, so recalculate
        cnv_ps_columns = [col for col in cnv_df.columns if col.startswith('PS ') and col[3].isdigit()]
                
        # Add a column of 0's if either gs or pearson is missing a PS
        st.session_state['max_ps_num'] = -1
        for i, ps_num in enumerate(ps_numbers):
            cnv_col_name = cnv_ps_columns[i]
            gs_col_name = 'PS ' + str(ps_num)
            pearson_col_name = 'PS ' + str(ps_num) + ' Mastering'
            
            # If column of appropriate name does not exist, make one and fill with 0's
            if gs_col_name not in gs_df.columns:
                gs_df[gs_col_name] = 0
            if pearson_col_name not in pearson_df.columns:
                pearson_df[pearson_col_name] = 0
            
            if i > st.session_state['max_ps_num']:
                st.session_state['max_ps_num'] = i
                
        # Merge the three dfs into a single merged_df
        merged_df = pd.merge(cnv_df, gs_df, on='SIS User ID', how='left')
        merged_df = pd.merge(merged_df, pearson_df, on='SIS User ID', how='left')
     
        # Loop through all of the PSs, calculating the grade in each
        for i, ps_num in enumerate(ps_numbers):
            cnv_col_name = cnv_ps_columns[i]
            gs_col_name = 'PS ' + str(ps_num)
            pearson_col_name = 'PS ' + str(ps_num) + ' Mastering'
            
            # Convert all missing values in gradscope and pearson to 0
            merged_df[gs_col_name] = pd.to_numeric(merged_df[gs_col_name], errors='coerce').fillna(0)
            merged_df[pearson_col_name] = pd.to_numeric(merged_df[pearson_col_name], errors='coerce').fillna(0)
    
            # Need to find the scaling factors for gradescope and pearson, taking into account that
            #   (a) one may be missing, (b) gradescope could have extra credit, and (c) pearson has
            #   an arbitrary number of points
            max_gs_col = pd.to_numeric(merged_df[gs_col_name], errors='coerce').max()
            max_gs_col = 100.0 if max_gs_col > 100.0 else max_gs_col    # Take care of extra credit
            max_pearson_col = pd.to_numeric(merged_df[pearson_col_name], errors='coerce').max()
    
            gsScale = 0.0
            psScale = 0.0
            if max_gs_col > 0:
                if(max_pearson_col > 0):
                    pct_pearson = float(st.session_state['toml_dict']['user']['pct_pearson'])
                    gsScale = 100 * (1 - pct_pearson)/max_gs_col
                    psScale = 100 * pct_pearson/max_pearson_col
                else:
                    gsScale = 1.0   # Don't change scaling
                
            elif max_pearson_col > 0:
                psScale = 100.0/max_pearson_col   # Scale to 100
            
            # Actual grade calculation. Only affects rows that do not contain 'EX' in canvas
            merged_df.loc[merged_df[cnv_col_name] != 'EX', cnv_col_name] = (
                    gsScale * merged_df[gs_col_name] + psScale * merged_df[pearson_col_name]
                    ).apply(lambda x: "{:.2f}".format(x))
            
            # Get rid of the extra columns
            merged_df.drop(columns = [gs_col_name], inplace=True)
            merged_df.drop(columns = [pearson_col_name], inplace=True)
        
        # Present the results and a button for downloading a csv
        st.markdown('## PS Grades for Upload')
        st.dataframe(merged_df)
        
        # Now calculate the statistics
        st.markdown('## PS Statistics')
        PSonly_df = merged_df[cnv_ps_columns].replace('EX', np.nan).astype(float)
        PSstats_df = PSonly_df.agg(['median', 'std', 'min', 'max']).round(2)
        st.dataframe(PSstats_df)
        
        info_str = 'Use the button below to download the grades. Upload the file to the Canvas gradebook'
        info_str += ' using the Import button. Overwriting previously uploaded grades is OK and does'
        info_str += ' slow down processing.' 
        st.write(info_str)
        
        grades_data = merged_df.to_csv(index = False, header = True).encode('utf-8')
        st.download_button(label = 'Download Grades for Canvas Upload',
                        data = grades_data,
                        file_name = 'PS_Grades_for_Upload.csv',
                        mime = 'text/csv',
                        type = 'primary')
    
        # For debugging
#         st.markdown('## Canvas DF')
#         st.dataframe(cnv_df)
#         
#         st.markdown('## Gradescope DF')
#         st.dataframe(gs_df)
#         
#         st.markdown('## Pearson DF')
#         st.dataframe(pearson_df)
        
utils.shared_sidebar()
          
