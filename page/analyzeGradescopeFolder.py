import streamlit as st
import pandas as pd
import plotly.express as px
import streamlit.components.v1 as components

# This is a streamlit package that is designed primarily to analyze grading in a folder of Gradescope
#   scores for an assignment. To get the folder, open the assignment in Gradescope and select
#   "Export Evaluations" at the bottom of the page.
#
#   Drag the folder onto "Drag and drop files here." Give the analysis a name in the modal dialog.
#   An analysis of all problems will appear. To analyze a single problem, use the dropdown menu
#   in the sidebar to select it.
#
#   Datafromes produced in the analysis
#   combo_df            This contains all of the data 
#   comboGrader_df      This contains all of the data by primary grader
#   primaryGrader_df    This contains the analysis by primary grader
#   The primary grader is defined to be the grader who grades the most parts of the problem
#
#   Usage: streamlit run analyzeGradescopeFolder.py
#
#   Melissa A. Hines, Melissa.Hines@cornell.edu December 20, 2025


def read_gradescope_csv(file_str):
    """ Reads a folder of csv's or a single csv of created by Gradescope's Export Evaluations."""
    
    # The Gradescope csv's have a bunch of columns that are not useful to us. We avoid loading them
    columns = ['SID', 'Score', 'Grader']
    usecols = lambda x: (x in columns)

    # Read the csv's dragged onto the file opener
    gs_df = pd.read_csv(file_str,
                        usecols = usecols,
                        skipfooter=4,   # Skips crap at end of file
                        engine='python'
                        )
                        
    # Now summarize the folders by grader
    grader_df = summarize_by_grader(gs_df, 'Score', 'Grader')
    
    # Need to give the Score and Grade columns unique names based on the problem's file name
    problemName = file_str.name.removesuffix('.csv')
    
    # Rename the columns in the main dataframe
    columnsToRename = ['Score', 'Grader']
    gsRenamedColumns = []
    for oldName in columnsToRename:
        newName = oldName + '_' + problemName
        gs_df.rename(columns={oldName: newName}, inplace=True)
        gsRenamedColumns.append(newName)
    
    # Rename the columns in the scores_by_grader dataframe
    columnsToRename = ['mean', 'std dev', 'count']
    graderRenamedColumns = []
    for oldName in columnsToRename:
        newName = oldName + '_' + problemName
        grader_df.rename(columns={oldName: newName}, inplace=True)
        graderRenamedColumns.append(newName)

    return problemName, gs_df, gsRenamedColumns, grader_df, graderRenamedColumns

def summarize_by_grader(df, scoreCol, graderCol):
    """Analyzes a dataframe of grades to produce statistical analysis by grader. Returns a new dataframe. """
    
    # Perform the analysis by grader
    new_df = df[[scoreCol, graderCol]].groupby(graderCol).describe()
    
    # Get rid of the multilevel column headers
    new_df.columns = new_df.columns.droplevel(level=0)    
    
    # Perform an analysis of all of the grades. This will appear as the grader " All"
    all_df = df[[scoreCol]].describe()
    all_df = all_df.T
    all_df.rename(index={scoreCol: 'All'}, inplace=True)
    all_df.index.name = graderCol
    
    # Combine the ' All' data with the grader data
    new_df = pd.concat([all_df, new_df])
    
    # Get rid of extranous columns, then reorder
    cols_to_drop = ['min', '25%', '50%', '75%', 'max']
    new_df = new_df.drop(columns = cols_to_drop)
    newOrder = ['mean', 'std', 'count']
    new_df = new_df[newOrder]
    new_df = new_df.rename(columns={'std': 'std dev'})
     
    return new_df
    
def handle_upload_change():
    """Callback function to update session state after a file/folder is uploaded. Used to remove file upload input."""
    # Check if a file was actually uploaded in the callback
    if st.session_state['uploader_key'] is not None:
        st.session_state['file_uploaded'] = True
        # Store the file details for later use
        st.session_state['uploaded_file_data'] = st.session_state['uploader_key']

def handle_problem_change():
    """ Function to update session state when the problem to be analyzed is changed."""
    
    if st.session_state['file_uploaded'] and st.session_state['analysis_done']:
        if st.session_state.problem_select_box == ' All':
            st.session_state['current_problem'] = 'Analysis of All Problems'
            st.session_state.primaryGrader_df = summarize_by_grader(st.session_state.combo_df, 'Total','Primary Grader')
        else:
            st.session_state['current_problem'] = 'Analysis of ' + st.session_state.problem_select_box
            score_col = 'Score_' + st.session_state.problem_select_box
            grader_col = 'Grader_' + st.session_state.problem_select_box
            cols = ['SID', score_col, grader_col]
            sub_df = st.session_state.combo_df[cols].copy()
            st.session_state.primaryGrader_df = summarize_by_grader(sub_df, score_col, grader_col)
       
        st.session_state.fig = prepare_graph(st.session_state.primaryGrader_df)
     
def reset_uploader():
    """Function to clear the uploaded file data and show the uploader again."""
    st.session_state['file_uploaded'] = False
    st.session_state['uploaded_file_data'] = None
    st.session_state['analysis_done'] = False
    st.session_state['analysis_name'] = 'Analyze Exported Evaluations'
    st.session_state['current_problem'] = 'Analysis of All Problems'
    # No need to explicitly clear the widget's value here;
    # hiding and showing it again effectively resets it.

def prepare_graph(df):
    """Create a bar chart with error bars and a horizontal line showing the mean."""
    
    # Copy the dataframe for graphing
    plt_df = df.copy()
    plt_df['Grader'] = plt_df.index
    plt_df['sum_mean_sd'] = plt_df['mean'] + plt_df['std dev']
    plt_df['diff_mean_sd'] = plt_df['mean'] - plt_df['std dev']
    
    # Now put the columns in order of mean. Split off the first (' All') column, alphabetize, then recombine
    df_header = plt_df.iloc[[0]]
    df_rest = plt_df.iloc[1:]
    df_rest = df_rest.sort_values(by='mean', ascending=True)
    plt_df = pd.concat([df_header, df_rest])
    
    # Figure generation
    fig = px.bar(
        plt_df,
        x='Grader',
        y="mean",
        error_y="std dev",
        color_discrete_sequence=['darkkhaki'],
        title="Mean and Std Dev by Grader"
    )
    fig.update_yaxes(range=[plt_df['diff_mean_sd'].min(), plt_df['sum_mean_sd'].max()])
    fig.add_hline(y=plt_df['mean'].iloc[0], annotation_text="mean", 
          line_dash="dot", line_color='black')
    return fig

# Initialization 
if 'uploaded_files_list' not in st.session_state:
    st.session_state.uploaded_files_list = []
if 'analysis_done' not in st.session_state:
    st.session_state.analysis_done = False
if 'file_uploaded' not in st.session_state:
    st.session_state['file_uploaded'] = False
if 'uploaded_file_data' not in st.session_state:
    st.session_state['uploaded_file_data'] = None
if 'probNameList' not in st.session_state:
    st.session_state.probNameList = [' All']
if 'analysis_name' not in st.session_state:
    st.session_state['analysis_name'] = 'Analyze Exported Evaluations'
if 'current_problem' not in st.session_state:
    st.session_state['current_problem'] = 'Analysis of All Problems'
    
@st.dialog('Enter string')
def nameOfAnalysis_dialog():
    """ Use a modal dialog to ask the user for a name for the analysis. This will appear at the top of the main page"""

    user_input = st.text_input('Name of data being analyzed:',
                                key="dialog_input")
    
    # Check if the user clicked the 'Submit' button inside the form
    if st.button('Submit'):
        if user_input:
            # Store the input in session state to access it in the main app
            st.session_state['analysis_name'] = user_input
            st.rerun() # Rerun the app to close the dialog and update the main view
        else:
            st.warning("Please enter a non-empty string.")

# Display the name of the analysis and the problem currently being analyzed
st.title(st.session_state['analysis_name'])
st.header(st.session_state['current_problem'])

# Logic to display the file uploader or the "Analyze a different file/folder" button
if not st.session_state['file_uploaded']:
    # Display the uploader only if no file has been uploaded yet
    st.file_uploader(
        "Upload your file(s) here:",
        type=['csv'],
        accept_multiple_files=True,
        key = 'uploader_key',
        on_change=handle_upload_change
    )
else:
    st.sidebar.button("Analyze a different file/folder.", on_click=reset_uploader)

allData = st.sidebar.checkbox('Show all data.', key = 'all_data_checkbox')
allGraderData = st.sidebar.checkbox('Show all grader data', key = 'all_grader_data_checkbox')

# Performs the analysi if an unanalyzed file/folder of data exists
if st.session_state['file_uploaded'] and not st.session_state['analysis_done']:

    nameOfAnalysis_dialog()
    
    for uploaded_file in st.session_state['uploaded_file_data']:
                
        # Read a file and generate a number of dataframes
        #   combo_df            This contains all of the data 
        #   comboGrader_df      This contains all of the data by primary grader
        #   primaryGrader_df    This contains the analysis by primary grader
        # The primary grader is defined to be the grader who grades the most of the assignment
        
        probName, gs_df,gsCols, grader_df, graderCols = read_gradescope_csv(uploaded_file)
        
        if 'combo_df' in locals():  # Not very pythonic. Is there a better way?
            combo_df = pd.merge(combo_df, gs_df, on='SID', how='left')
            combo_df['Total'] = combo_df['Total'] + combo_df[gsCols[0]]
            graderNameCols.append(gsCols[1])
            combo_df['Primary Grader'] = combo_df[graderNameCols].mode(axis=1)[0]
            
            comboGrader_df = pd.merge(comboGrader_df, grader_df, on='Grader', how='left')
            comboGrader_df['mean'] = comboGrader_df['mean'] + comboGrader_df[graderCols[0]]
            
            primaryGrader_df = summarize_by_grader(combo_df, 'Total','Primary Grader')
            
            probNameList.append(probName)
        else:
            combo_df = gs_df
            combo_df['Total'] = gs_df[gsCols[0]]
            combo_df['Primary Grader'] = gs_df[gsCols[1]]
            graderNameCols = [gsCols[1]]  # Columns containing grader names
            cols = ['Total'] + ['Primary Grader'] + [col for col in combo_df.columns if col not in ['Total', 'Primary Grader']]
            combo_df = combo_df[cols]   # Reorder columns
            
            comboGrader_df = grader_df
            comboGrader_df['mean'] = grader_df[graderCols[0]]
            cols = ['mean'] + [col for col in comboGrader_df.columns if col != 'mean']
            comboGrader_df = comboGrader_df[cols] # Reorder columns
            
            primaryGrader_df = summarize_by_grader(combo_df, 'Total', 'Primary Grader')
            
            probNameList = [' All', probName]          
            
    st.session_state.probNameList = probNameList.sort()
    
    st.session_state.fig = prepare_graph(primaryGrader_df)
    
    st.session_state.analysis_done = True
    st.session_state.combinedData = st.empty()
    st.session_state.combo_df = combo_df
    st.session_state.comboGrader_df = comboGrader_df
    st.session_state.primaryGrader_df = primaryGrader_df
    st.session_state.probNameList = probNameList

# Performs the necessary display tasks after the data have been analyzed
if st.session_state['file_uploaded'] and st.session_state['analysis_done']:
    with st.session_state.combinedData.container():
        
        # Display the chart and the data in the Streamlit app
        st.plotly_chart(st.session_state.fig, width = 'stretch')
        
        st.dataframe(st.session_state.primaryGrader_df)

        st.download_button(
            "Download Primary Grader Analysis",
            st.session_state.primaryGrader_df.to_csv().encode("utf-8"),
            'PrimaryGraderAnalysis.csv',
            "text/csv",
            key = 'primary_grader_download'
        )
        
        # If requested, display the combo_df and/or comboGrader_df dataframes and allow download to csv
        if allData:
            st.dataframe(st.session_state.combo_df)
            st.download_button(
                "Download All Data",
                st.session_state.combo_df.to_csv().encode("utf-8"),
                'AllData.csv',
                "text/csv",
                key = 'all_data_download'
            )
        if allGraderData:
            st.dataframe(st.session_state.comboGrader_df)
            st.download_button(
                "Download All Grader Data",
                st.session_state.comboGrader_df.to_csv().encode("utf-8"),
                'AllGraderData.csv',
                "text/csv",
                key = 'all_grader_data_download'
            )
        
        # Display the name of the problem being analyzed
        selected_problem = st.sidebar.selectbox(
                            'Problem to be analyzed:',
                            st.session_state.probNameList,
                            key = 'problem_select_box',
                            on_change=handle_problem_change)

