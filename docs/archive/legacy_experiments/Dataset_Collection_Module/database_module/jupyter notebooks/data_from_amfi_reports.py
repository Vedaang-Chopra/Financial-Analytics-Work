
import pandas as pd
import os

BASE_CODE_FOLDER=os.sep.join(os.getcwd().split(os.sep)[:os.getcwd().split(os.sep).index('Mutual_Fund_Analysis')+1])
DATASET_FOLDER=os.path.join(BASE_CODE_FOLDER, 'Dataset')
LIST_OF_MUTUAL_FUNDS=os.path.join(DATASET_FOLDER,'list_of_mutual_funds')
AMFI_REPORTS=os.path.join(LIST_OF_MUTUAL_FUNDS,'amfi_reports')

print(os.path.join(AMFI_REPORTS, os.listdir(AMFI_REPORTS)[0]))
CURRENT_DATA=pd.read_html(os.path.join(AMFI_REPORTS, os.listdir(AMFI_REPORTS)[0]),header=0)
CURRENT_DATA=pd.DataFrame(CURRENT_DATA[0])
CURRENT_DATA.head()



def isNaN(num):
    return num != num



def identify_complete_fund_categories(FUND_HEADER):
    TYPE= FUND_HEADER.split("(")[0].strip()
    if FUND_HEADER.__contains__("-"):
        CATEGORY = FUND_HEADER.split("(")[1].split(")")[0].split("-")[0].strip()
        SUB_CATEGORY =FUND_HEADER.split("(")[1].split(")")[0].split("-")[1].strip()
    else:
        CATEGORY = FUND_HEADER.split("(")[1].split(")")[0].strip()
        SUB_CATEGORY=""
    return TYPE, CATEGORY, SUB_CATEGORY




MUTUAL_FUND_DATA_TEMP=[]
# c=0
for i in range(0,len(CURRENT_DATA)):
    CURRENT_TEXT= (CURRENT_DATA.iloc[i][0])
    if isNaN(CURRENT_DATA.iloc[i][1]) and isNaN(CURRENT_DATA.iloc[i][2]) and isNaN(CURRENT_DATA.iloc[i][3]):
        if CURRENT_TEXT.__contains__ ("Open Ended") or CURRENT_TEXT.__contains__ ("Close Ended") or CURRENT_TEXT.__contains__ ("Interval Fund Schemes"):
            # print("Category:", CURRENT_TEXT)
            TYPE, CATEGORY, SUB_CATEGORY = identify_complete_fund_categories(CURRENT_TEXT)
            # c=c+1
            # pass
        elif CURRENT_TEXT.__contains__("Mutual Fund") and CURRENT_TEXT==CURRENT_DATA.iloc[i][1]:
            # print("Fund AMC:", CURRENT_TEXT)
            FUND_AMC=CURRENT_TEXT
            # pass
        else:
            print("Header Column, to be Ignored")
            # print(CURRENT_DATA.iloc[i].values)
    elif CURRENT_DATA.iloc[i][1]==CURRENT_DATA.iloc[i][2]==CURRENT_DATA.iloc[i][3]:
        if CURRENT_TEXT.__contains__ ("Open Ended") or CURRENT_TEXT.__contains__ ("Close Ended") or CURRENT_TEXT.__contains__ ("Interval Fund Schemes"):
            # print("Category:", CURRENT_TEXT)
            TYPE, CATEGORY, SUB_CATEGORY = identify_complete_fund_categories(CURRENT_TEXT)
            # c=c+1
            # pass
        elif CURRENT_TEXT.__contains__("Mutual Fund") and CURRENT_TEXT==CURRENT_DATA.iloc[i][1]:
            # print("Fund AMC:", CURRENT_TEXT)
            FUND_AMC=CURRENT_TEXT
            # pass
        else:
            print("Header Column, to be Ignored")
    else:
        
        if isNaN(CURRENT_TEXT) or CURRENT_TEXT.strip()=='Scheme NAV Name' :
            continue
        else:
            # print(CURRENT_TEXT, CURRENT_DATA.iloc[i][1])
            SCHEME_NAV_NAME=CURRENT_TEXT
            ISIN_DIV_GROWTH=CURRENT_DATA.iloc[i][1]
            ISIN_DIV_REINIVESTMENT=CURRENT_DATA.iloc[i][2]
            NAV_VALUE=CURRENT_DATA.iloc[i][3]
            DATE_RECORDED=CURRENT_DATA.iloc[i][4]
            MUTUAL_FUND_DATA_TEMP.append([FUND_AMC, SCHEME_NAV_NAME, TYPE, CATEGORY, SUB_CATEGORY, ISIN_DIV_GROWTH, ISIN_DIV_REINIVESTMENT, NAV_VALUE, DATE_RECORDED])
            
            
MUTUAL_FUND_FINAL_DATA=pd.DataFrame(columns=["Mutual Fund Name", "Scheme NAV Name","FUND TYPE","FUND CATEGORY", "FUND SUB-CATEGORY", "ISIN Div Payout/ ISIN Growth", "ISIN Div Reinvestment", "Net Asset Value", "Date"])


CLEAN_DATA=pd.DataFrame(MUTUAL_FUND_DATA_TEMP, columns=["Mutual Fund Name", "Scheme NAV Name","FUND TYPE","FUND CATEGORY", "FUND SUB-CATEGORY", "ISIN Div Payout/ ISIN Growth", "ISIN Div Reinvestment", "Net Asset Value", "Date"])
CLEAN_DATA