import pika
import datetime
import pandas as pd
from sqlalchemy import create_engine


# Setting Up Rabbit MQ Queues.....

ROUTING_KEY="mutual_fund_daily_update"
connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()
result = channel.queue_declare(queue='daily_nav_update', exclusive=True)
queue_name = result.method.queue
channel.queue_bind(exchange='mutual_fund_data_collection', queue=queue_name, routing_key=ROUTING_KEY)
print("Setup Queue:",queue_name)



# Setting up DB Connection
USER_NAME = "mutual_fund"
PASSWORD ="mutual_fund"
IP_ADDRESS = "127.0.0.1"
PORT_NUMBER = "5432"
DB_NAME="mutual_fund_db"

engine = create_engine('postgresql://' + USER_NAME+':' + PASSWORD + '@' + IP_ADDRESS + ':' + PORT_NUMBER +'/'+ DB_NAME,pool_size=10, max_overflow=20)



def write_to_table(daily_data):
    daily_data.to_sql('mutual_fund_nav_data', con=engine, if_exists='replace', schema = None)
    print("Written to Table.........")

def isNaN(num):
    return num != num

def preprocess_data(data):
    FINAL_DATA=[]
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
            FINAL_DATA.append([AMC_CATEGORY,FUND_NAME, NAV_VALUE, TIMESTAMP])
    FINAL_DATA=pd.DataFrame(FINAL_DATA, columns=["AMC Fund Company", "Mutual Fund Name", "NAV Value", "NAV Record Timestamp"])
    # FINAL_DATA.reset_index(inplace=True)
    FINAL_DATA['Timestamp']=datetime.datetime.now()
    FINAL_DATA.rename(columns={ 
                            # "index":"id",
                            "AMC Fund Company": "amc_mutual_fund", 
                            "Mutual Fund Name":"mutual_fund_name",
                            "NAV Value":"nav",
                            "Timestamp":"timestamp",
                            "NAV Record Timestamp":"nav_upload_date_time"}, inplace=True)
    return FINAL_DATA




def callback(ch, method, properties, body):
    # print("Data Recieved:", body)
    # print(" [x] %r:%r" % (method.routing_key, body))
    print("Data Recieved.....")
    
    data=pd.read_html(body,header=0)
    data=pd.DataFrame(data[0])
    print("Preprocessing Data..........")
    clean_data=preprocess_data(data)
    print(clean_data.columns)
    print("Writing to DB table..........")
    write_to_table(clean_data)
    
    
channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)

channel.start_consuming()