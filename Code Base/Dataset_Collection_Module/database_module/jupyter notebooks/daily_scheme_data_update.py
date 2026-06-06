import pandas as pd
import os




BASE_CODE_FOLDER=os.sep.join(os.getcwd().split(os.sep)[:os.getcwd().split(os.sep).index('Mutual_Fund_Analysis')+1])
DATASET_FOLDER=os.path.join(BASE_CODE_FOLDER, 'Dataset')
LIST_OF_MUTUAL_FUNDS=os.path.join(DATASET_FOLDER,'list_of_mutual_funds')
SCHEME_DATA=os.path.join(LIST_OF_MUTUAL_FUNDS,'scheme_data')




CURRENT_DATA=pd.read_csv(os.path.join(SCHEME_DATA, os.listdir(SCHEME_DATA)[0]))
CURRENT_DATA.head()




isin_data=CURRENT_DATA[["AMC","Scheme Name","Scheme NAV Name", "ISIN Div Payout/ ISIN GrowthISIN Div Reinvestment", ]]
ISIN_COLUMN="ISIN Div Payout/ ISIN GrowthISIN Div Reinvestment"
isin_values=isin_data[ISIN_COLUMN].values

def isNaN(num):
    return num != num

def clean_isin(isin_value):
    # print("Current ISIN Value:", isin_value)
    isin_segregated_data={
        "status":-1,
        "ISIN Div Payout/ ISIN":"",
        "ISIN Div Reinvestment":""
    }
    if isNaN(isin_value):
        isin_segregated_data["status"]=0
    else:
        spilt_isin=isin_value.split("INF")
        # print("Splited ISIN:", spilt_isin)
        if len(spilt_isin)==2:
            isin_segregated_data["status"]=1
            isin_segregated_data["ISIN Div Payout/ ISIN"]="INF"+spilt_isin[1].strip()
        elif len(spilt_isin)==3:
            isin_segregated_data["status"]=2
            isin_segregated_data["ISIN Div Payout/ ISIN"]="INF"+spilt_isin[1].strip()
            isin_segregated_data["ISIN Div Reinvestment"]="INF"+spilt_isin[2].strip()
    return isin_segregated_data


segregated_isin=[]
for i in isin_values:
    segregated_isin.append(clean_isin(i))
isin_data=pd.concat([isin_data, pd.json_normalize(segregated_isin)], axis=1,)