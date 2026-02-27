# This script reads in 3 csv's:
#                   Canvas gradebook
#                   Canvas Late Report, generated from Late Assignments in Course Analytics
#                   Gradescope gradebook
# The script assumes that:
#       – The names of the pre- and post-lab assignments in Gradebook start with the same word as in canvas
#       – That word is unique to the lab
#       – The pre- and post-lab assignments have "pre-lab" and "post-lab" in the assignment names
# The script gives a 10 min grace period as per Cynthia

import pandas as pd
import numpy as np
import streamlit as st
import utils

def handle_cnv_upload_change():
    """Callback function to update session state when canvas file is uploaded."""
    if st.session_state['cnv_uploader_key'] is not None:
        # Read in the required columns of canvas csv plus any that include 'lab'
        columns = ["Student", "ID", "SIS User ID", "SIS Login ID", "Section"]
        good_sub_strings = ['lab']
        usecols = lambda x: (x in columns) or ((any(s in x.lower() for s in good_sub_strings)))
        cnv_df = pd.read_csv(st.session_state['cnv_uploader_key'],
                             dtype = str,
                             skiprows=[1,2],
                             usecols = usecols
                             )
        cnv_df = cnv_df[~cnv_df['Student'].str.contains('Student, Test', na=False)] # Remove test student
        
        st.session_state['cnv_df'] = cnv_df

def handle_cnvLate_upload_change():
    """Callback function to update session state when canvas file is uploaded."""
    if st.session_state['cnvLate_uploader_key'] is not None:
        columns = ['Student Name', 'Student ID', 'Assignment Name', 'Due Date', 'Submitted Date']
        usecols = lambda x: (x in columns)
        cnv_late_df = pd.read_csv(st.session_state['cnvLate_uploader_key'],
                                 dtype = str,
                                 usecols = usecols
                                 )
        cnv_late_df.rename(columns={'Student ID': 'ID'}, inplace=True)
        cnv_late_df.rename(columns={'Assignment Name': 'Assignment_Name'}, inplace=True)
        
            
        # We have a problem in that pandas does not like EDT. Try replacing EDT/EST with UTC offset
        columns = ['Due Date', 'Submitted Date']
        for col in columns:
            cnv_late_df[col] = cnv_late_df[col].str.replace('EDT', '-0400')
            cnv_late_df[col] = cnv_late_df[col].str.replace('EST', '-0500')
            cnv_late_df[col] = pd.to_datetime(cnv_late_df[col], format='%b %d, %Y at %-I:%M:%S %p %z', utc=True)
    
        # Calculate lateness in hours, then assign penalty. Give 10 min grace period as per Cynthia.
        # This assumes that all late reports get 15% off even if they are over 72 hrs late
        cnv_late_df['Lateness'] = (cnv_late_df['Submitted Date'] - cnv_late_df['Due Date'])/pd.Timedelta(hours = 1)
        cnv_late_df['Penalty'] = 0
        cnv_late_df.loc[(cnv_late_df['Lateness'] > 0.17) & (cnv_late_df['Lateness'] < 24.17), 'Penalty'] = -10
        cnv_late_df.loc[(cnv_late_df['Lateness'] > 24.17) & (cnv_late_df['Lateness'] < 48.17), 'Penalty'] = -20
        cnv_late_df.loc[(cnv_late_df['Lateness'] > 48.17), 'Penalty'] = -30

        # Calculate lateness according to 2025 lateness policy
#         cnv_late_df.loc[(cnv_late_df['Lateness'] > 0.17) & (cnv_late_df['Lateness'] < 72.17), 'Penalty'] = -15
#         cnv_late_df.loc[(cnv_late_df['Lateness'] >= 72.17), 'Penalty'] = -15 # -100
        
        st.session_state['cnv_late_df'] = cnv_late_df

def handle_gs_upload_change():
    """Callback function to update session state when canvas file is uploaded."""
    if st.session_state['gs_uploader_key'] is not None:
        # The Gradescope csv's have a bunch of columns that are not useful to us. We avoid loading that
        #   info using the info in sub_strings and usecols
        # sub_strings = ['Submission', 'Max', 'Lateness','First Name', 'Last Name', 'section_name']
        bad_sub_strings = ['Submission', 'Max', 'Lateness']
        good_sub_strings = ['post-lab', 'pre-lab']
        columns = ["SID"]
        usecols = lambda x: (x in columns) or ((any(s in x.lower() for s in good_sub_strings)) and (not any(s in x for s in bad_sub_strings)))
    
        gs_df = pd.read_csv(st.session_state['gs_uploader_key'],
                                 dtype = str,
                                 usecols = usecols
                                 )
        gs_df.rename(columns={'SID': 'SIS User ID'}, inplace=True)
        
        # Missing grades are replaced by 0
        gs_df = gs_df.fillna(0)

        st.session_state['gs_df'] = gs_df
    
def handle_lab_change():
    selected_value = st.session_state['selected_lab']
    st.session_state['last_lab_index'] = st.session_state['lab_select_list'].index(selected_value)

def reset_uploader():
    """Function to clear the uploaded files and show the uploaders again."""
    st.session_state['cnv_df'] = None
    st.session_state['cnv_late_df'] = None
    st.session_state['gs_df'] = None

if 'cnv_df' not in st.session_state:
    st.session_state['cnv_df'] = None
if 'cnv_late_df' not in st.session_state:
    st.session_state['cnv_late_df'] = None
if 'gs_df' not in st.session_state:
    st.session_state['gs_df'] = None
if 'toml_dict' not in st.session_state:
    utils.read_prefs()
if 'last_lab_index' not in st.session_state:
    st.session_state['last_lab_index'] = -1

st.title('Combine Pre and Post Labs for Canvas')

# The script assumes that:
#       – The names of the pre- and post-lab assignments in Gradebook start with the same word as in canvas
#       – That word is unique to the lab
#       – The pre- and post-lab assignments have "pre-lab" and "post-lab" in the assignment names
text_str = 'This script assumes that:  \n'
text_str += '   – The names of the pre- and post-lab assignments start with the same word in Gradebook and in Canvas  \n'
text_str += '   – That starting word is unique to the lab  \n'
text_str += '   – The pre- and post-lab assignments have "pre-lab" and "post-lab" in the assignment names'
st.write(text_str)

st.button("Reset or work on a different course.", 
            on_click=reset_uploader,
            type = 'primary')

s = st.session_state['toml_dict']['user']['lab_order']
key, labs = s.split(': ', 1)        # Split the string at the colon
labs_str = labs.replace('[','')    # Remove the square brackets
labs_str = labs_str.replace(']','')    # Remove the square brackets
labs_str = labs_str.replace('\'','')    # Remove the '
labs_list = [lab.strip() for lab in labs_str.split(',')] # Create list, cleaning up spaces
st.session_state['lab_select_list'] = ['None'] + labs_list

st.selectbox(
    'Start by selecting first word of LAST lab to be combined. (See settings for list.)', # Label for the dropdown
    st.session_state['lab_select_list'],                         # The options to display
    key = 'selected_lab',                # Always start at none selected
    on_change=handle_lab_change
)

if st.session_state['last_lab_index'] > 0:
    if st.session_state['gs_df'] is None:
        # Display the uploader only if no file has been uploaded yet
        st.file_uploader(
            "Upload your Gradescope gradebook csv here:",
            type=['csv'],
            accept_multiple_files=False,
            key = 'gs_uploader_key',
            on_change = handle_gs_upload_change
        )
    else:
        st.write('#### :gray[Gradescope gradebook already uploaded.]')    
    
    if st.session_state['cnv_df'] is None:
        # Display the uploader only if no file has been uploaded yet
        st.file_uploader(
            "Upload your Canvas gradebook csv here:",
            type=['csv'],
            accept_multiple_files=False,
            key = 'cnv_uploader_key',
            on_change = handle_cnv_upload_change
        )
    else:
        st.write('#### :gray[Canvas gradebook already uploaded.]')    
    
    if st.session_state['cnv_late_df'] is None:
        # Display the uploader only if no file has been uploaded yet 
        st.file_uploader(
            "Upload your Canvas Late Assignments report here:",
            type=['csv'],
            accept_multiple_files=False,
            key = 'cnvLate_uploader_key',
            on_change = handle_cnvLate_upload_change
        )
    else:
        st.write('#### :gray[Canvas Late Report already uploaded.]') 
           
    # If all df's loaded, do the analysis
    if all(v is not None for v in [st.session_state['cnv_df'],st.session_state['cnv_late_df'],st.session_state['gs_df']]):
        
        # Work on local copies 
        cnv_df = st.session_state['cnv_df'].copy()
        cnv_late_df = st.session_state['cnv_late_df'].copy()
        gs_df = st.session_state['gs_df'].copy()
        
        # Make lists of the lab columns
        cnv_list = cnv_df.columns.tolist()
        gs_list = gs_df.columns.tolist()
        all_labs_cnv_list = [item for item in cnv_list if 'lab' in item.lower()]
        all_labs_gs_list = [item for item in gs_list if 'lab' in item.lower()]
        
        # Now drop the ones we don't want to analyze
        included_labs = labs_list[:st.session_state['last_lab_index']]
        tbr_cnv_list = [item for item in all_labs_cnv_list if item.split()[0] not in included_labs]
        tbr_gs_list = [item for item in all_labs_gs_list if item.split()[0] not in included_labs]
        gs_df = gs_df.drop(columns = tbr_gs_list)
        cnv_df = cnv_df.drop(columns = tbr_cnv_list)
    
        # Update the lists. Could do this more elegantly
        cnv_list = cnv_df.columns.tolist()
        gs_list = gs_df.columns.tolist()
        all_labs_cnv_list = [item for item in cnv_list if 'lab' in item.lower()]
        all_labs_gs_list = [item for item in gs_list if 'lab' in item.lower()]

        # Merge the gradescope and canvas dataframes
        merged_df = pd.merge(cnv_df, gs_df, on='SIS User ID', how='left')
        
        # Make a list to reorder columns
        columnOrder = ["Student", "ID", "SIS User ID", "SIS Login ID", "Section"] # Have to keep ID column for re-upload
        columnsToBeDropped = []     # After analysis
        for lab in all_labs_cnv_list:  
            columnOrder.append(lab)
            first_word = lab.split()[0]   # Assume the labs start with the same first word
            
            gs_entries = [item for item in all_labs_gs_list if first_word in item]
            columnOrder.extend(sorted(gs_entries))
            columnsToBeDropped.extend(gs_entries)
            
            # Make a column for penalties
            newColumnName = first_word + '_penalty'
            merged_df[newColumnName] = 0.0
            columnOrder.append(newColumnName)
            columnsToBeDropped.append(newColumnName)
            
            # Make a column for adding
            newColumnName = first_word + '_adding'
            merged_df[newColumnName] = 0.0
            columnOrder.append(newColumnName)
            columnsToBeDropped.append(newColumnName)        
    
        merged_df = merged_df.reindex(columns = columnOrder)
    
        # Now we need to transfer late lab penalties into merged
        first_word_cnv_list = [lab.split()[0] for lab in all_labs_cnv_list]
        for row in cnv_late_df.itertuples():
            lab = row.Assignment_Name.split()[0]
            if row.Penalty < 0 and lab in first_word_cnv_list:
                labForPenalty = lab + '_penalty'
                merged_df.loc[merged_df['ID'] == row.ID, labForPenalty] = 0.01 * row.Penalty * 90
        
        # Here is the actual calculation
        for entry in all_labs_cnv_list:  
            first_word = entry.split()[0]   # Assume the labs start with the same first word
            
            gs_entries = [item for item in all_labs_gs_list if first_word in item]
            pre_lab = [item for item in gs_entries if 'pre-lab' in item.lower()]
            post_lab = [item for item in gs_entries if 'pre-lab' not in item.lower()]
            penaltyColumnName = first_word + '_penalty'
            addingColumnName = first_word + '_adding'
            
            # Convert to numeric, turning errors (like 'N/A') into NaN (Not a Number)
            merged_df[pre_lab[0]] = pd.to_numeric(merged_df[pre_lab[0]], errors='coerce')
            merged_df[post_lab[0]] = pd.to_numeric(merged_df[post_lab[0]], errors='coerce')
            merged_df[penaltyColumnName] = pd.to_numeric(merged_df[penaltyColumnName], errors='coerce')
    
            merged_df[addingColumnName] = merged_df[pre_lab[0]] + merged_df[post_lab[0]] + merged_df[penaltyColumnName]
            merged_df[addingColumnName] = merged_df[addingColumnName].clip(lower=0)     # No negative grades
            
        # Copy the calculation into the output column
        for entry in all_labs_cnv_list:  
            first_word = entry.split()[0]   # Assume the labs start with the same first word
            addingColumnName = first_word + '_adding'
            merged_df.loc[merged_df[entry] != 'EX', entry] = merged_df[addingColumnName]
             
        # Remove all of the unnecessary columns
        merged_df.drop(columns = columnsToBeDropped, inplace = True)
    
        # Present the results and a button for downloading a csv
        st.markdown('## Lab Grades for Upload')
        st.dataframe(merged_df)
        
        # Now calculate the statistics
        st.markdown('## Lab Statistics')
        PSonly_df = merged_df[all_labs_cnv_list].replace('EX', np.nan).astype(float)
        PSstats_df = PSonly_df.agg(['median', 'std', 'min', 'max']).round(2)
        st.dataframe(PSstats_df)
        
        info_str = 'Use the button below to download the grades. Upload the file to the Canvas gradebook'
        info_str += ' using the Import button. Overwriting previously uploaded grades is OK and does not'
        info_str += ' slow down processing.' 
        st.write(info_str)
        
        grades_data = merged_df.to_csv(index = False, header = True).encode('utf-8')
        st.download_button(label = 'Download Grades for Canvas Upload',
                        data = grades_data,
                        file_name = 'Lab_Grades_for_Upload.csv',
                        mime = 'text/csv',
                        type = 'primary')
            
    # For debugging
#     st.markdown('## Merged DF')
#     st.dataframe(merged_df)
#     
#     st.markdown('## Canvas DF')
#     st.dataframe(cnv_df)
#     
#     st.markdown('## Canvas Late DF')
#     st.dataframe(cnv_late_df)
#     
#     st.markdown('## Gradescope DF')
#     st.dataframe(gs_df)
        
utils.shared_sidebar()
