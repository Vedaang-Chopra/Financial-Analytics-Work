import datetime
import requests
import pandas as pd
import pika


connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()


class Nav_Value_Fetch_Particular_Date:
    def __init__(self, fetch_date) -> None:
        self.AMFI_WEBPAGE_URL="https://www.amfiindia.com/modules/NavHistoryAll"
        self.fetch_date=fetch_date
        self.ROUTING_KEY="daily_nav_data"
        
    def nav_data_fetch(self):
        create_url_necessary_date = lambda current_date, URl: self.AMFI_WEBPAGE_URL+'?'+"fDate="+current_date.strftime('%Y-%b-%d')
        response = requests.post(create_url_necessary_date(self.fetch_date, self.AMFI_WEBPAGE_URL))    
        return response
    
    def parse_data_to_pandas(self, response):
        data=pd.read_html(response.content,header=0)
        data=pd.DataFrame(data[0])
        isNaN = lambda num: num!=num
        nav_daily_data=[]
        for i in range(1,len(data)):
            CURRENT_DATA=data.iloc[i]
            # print(type(CURRENT_DATA.iloc[1]))
            if CURRENT_DATA.iloc[0]==CURRENT_DATA.iloc[1]==CURRENT_DATA.iloc[2]==CURRENT_DATA.iloc[3]:
                if CURRENT_DATA.iloc[0].__contains__("Mutual Fund") :
                    AMC_CATEGORY=CURRENT_DATA.iloc[0]
                else:
                    FUND_NAME=CURRENT_DATA.iloc[0]
            if isNaN(CURRENT_DATA.iloc[1]) and isNaN(CURRENT_DATA.iloc[2]):
                NAV_VALUE=CURRENT_DATA.iloc[0]
                TIMESTAMP=CURRENT_DATA.iloc[3]
                nav_daily_data.append([AMC_CATEGORY,FUND_NAME, NAV_VALUE, TIMESTAMP])
                
        nav_daily_data=pd.DataFrame(nav_daily_data, columns=["AMC Fund Company", "Mutual Fund Name", "NAV Value", "NAV Record Timestamp"])
        nav_daily_data.reset_index(inplace=True)
        nav_daily_data['Timestamp']=datetime.datetime.now()
        nav_daily_data.rename(columns={ "index":"id",
                                "AMC Fund Company": "amc_mutual_fund", 
                                "Mutual Fund Name":"mutual_fund_name",
                                "NAV Value":"nav",
                                "Timestamp":"timestamp",
                                "NAV Record Timestamp":"nav_upload_date_time"}, inplace=True)
        return nav_daily_data
    
    def empty_data_check(self, response):
        if str(response.content).__contains__('No records to display'):
            return True
        else:
            return False
        
    def runner_module(self):
        print("Fetching Data from AMFI Website")
        response=self.nav_data_fetch()
        print(response.text)
        if self.empty_data_check(response):
            print("Recieved Empty Response")
            return -1
        else:
            print("Parsing Data and Pushing Data for DB Insertion.....")
            nav_daily_data=self.parse_data_to_pandas(response)
            channel.basic_publish(exchange='mutual_fund_data_collection', routing_key=self.ROUTING_KEY, body=(nav_daily_data.to_json(orient='index')))
            return nav_daily_data


def main_runner():
    print("Fetching Mutual Fund NAV data for date:")
    current_date=datetime.datetime.today()-datetime.timedelta(days=0)
    nav_data_particular_date=Nav_Value_Fetch_Particular_Date(current_date)
    if nav_data_particular_date.runner_module() ==-1:
        print("Unable to retrieve Data for date:", current_date)
    else:
        print("Data Fetch Successfull for date:", current_date)

if __name__=='__main__':
    try:
        main_runner()
    except Exception as err:
        print("Caught Error in main_runner:", err)