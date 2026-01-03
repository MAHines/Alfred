import pandas as pd

SECTIONS = {
        '401': 'Mon PM',
        '402': 'Tue AM',
        '403': 'Tue PM',
        '404': 'Wed PM',
        '405': 'Thu AM',
        '406': 'Thu PM',
        '407': 'Fri AM',
        '408': 'Fri PM'}

def main():

    canvasRosterFile = 'canvasClassRoster.csv'
    
    # Read the timesheet, converting entry time to a datetime and the rest to strings
    canvasRoster_df =  pd.read_csv(canvasRosterFile, dtype=str) # [Student Name, Student ID,Student SIS ID, Email,Section Name]
    canvasRoster_df.rename(columns = {'Student ID': 'ID'}, inplace = True)
    canvasRoster_df['netID'] = canvasRoster_df['Email'].str.split('@', expand=True)[0]
    
    # Use .str.extract() with a regular expression to capture the three characters after LAB
   canvasRoster_df['labSectionNum'] = canvasRoster_df['Section Name'].str.extract('LAB(.{3})')
    
    canvasRoster_df['lastName'] = canvasRoster_df['Student Name'].str.split().str[-1]
    canvasRoster_df['firstName'] = canvasRoster_df['Student Name'].str.rsplit(pat=' ', n=1).str.get(0)
    canvasRoster_df['studentName'] = canvasRoster_df['lastName'] + ', ' + canvasRoster_df['firstName']
    
    # Find the section name
    lab_dict = SECTIONS
    canvasRoster_df['section'] = canvasRoster_df['labSectionNum'].map(lab_dict)
    
    # Drop unneeded columns
    cols_to_drop = ['Student Name', 'Email', 'lastName', 'firstName', 'Section Name', 'Student SIS ID', 'labSectionNum']
    canvasRoster_df.drop(columns = cols_to_drop, inplace = True)
    
    canvasRoster_df.to_csv('processedCanvasRoster.csv', index=False)


if __name__ == '__main__':

    main()

