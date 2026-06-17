
import requests
import pandas as pd
import pika
from lxml import html
import openpyxl
from io import BytesIO


connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()


class Fetch_List_of_AMC:
    def __init__(self) -> None:
        self.AMFI_WEBPAGE_URL="https://www.amfiindia.com/listofgroupcompanynames1"
        self.ROUTING_KEY="list_of_amc"
        
    
    def fetch_amc_csv_hyperlink(self):
        response = requests.get(self.AMFI_WEBPAGE_URL)
        tree = html.fromstring(response.content)
        element = tree.xpath('//*[@id="tab2"]/h2/a[1]')[0]
        # print(element)
        hyperlink = element.attrib['href']
        return hyperlink
    
    def fetch_amc_csv_data(self, hyperlink):
        create_necessary_url = lambda hyperlink: "https://www.amfiindia.com"+hyperlink
        response = requests.get(create_necessary_url(hyperlink))
        return response
    
    def parse_amc_data(self, response):
        amc_data=[]
        workbook = openpyxl.load_workbook(filename = BytesIO(response.content))
        worksheet = workbook.active
        for row in worksheet.iter_rows(values_only=True):
            amc_data.append(row)
            
        amc_data = pd.DataFrame(amc_data)
        new_header = amc_data.iloc[0]
        amc_data = amc_data[1:]
        amc_data.columns = new_header
        return amc_data
    
    def runner_module(self):
        hyperlink=amc_list.fetch_amc_csv_hyperlink()
        amc_data=amc_list.fetch_amc_csv_data(hyperlink)
        final_amc_data=self.parse_amc_data(amc_data)
        print("Sending Data Message")
        channel.basic_publish(exchange='mutual_fund_data_collection', routing_key=self.ROUTING_KEY, body=final_amc_data.to_json(orient='index'))
        return final_amc_data

amc_list=Fetch_List_of_AMC()
# amc_list.runner_module().head()