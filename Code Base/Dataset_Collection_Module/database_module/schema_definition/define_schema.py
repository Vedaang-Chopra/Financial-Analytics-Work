from sqlalchemy import create_engine, MetaData
from sqlalchemy import Column, Text, Integer, DateTime, Float
USER_NAME = "mutual_fund"
PASSWORD =""
IP_ADDRESS = "127.0.0.1"
PORT_NUMBER = "5432"
DB_NAME="mutual_fund_db"

engine = create_engine('postgresql://' + USER_NAME+':' + PASSWORD + '@' + IP_ADDRESS + ':' + PORT_NUMBER +'/'+ DB_NAME,pool_size=10, max_overflow=20)
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()
class Mutual_Fund_Nav_value(Base):

    id =         Column(name= "id", type_=Integer, nullable=False, autoincrement=True , primary_key=True)
    nav=         Column(name= "nav",type_=Float, nullable=False)
    amc=         Column(name= "amc_mutual_fund", type_=Text,)
    mfid=        Column(name="mutual_fund_id", type_=Text, nullable=False,  primary_key=True)
    fund_name=   Column(name="mutual_fund_name",type_=Text, nullable=False)
    timestamp=   Column(name="timestamp", type_=DateTime, nullable=False)
    upload_date= Column(name= "nav_upload_date_time",type_=Text, nullable=False)
    
    __tablename__ = 'mutual_fund_nav_value'
    __table_args__ = {
        'extend_existing': True,
        # "primary_key" : ['mutual_fund_nav_value.id', 'mutual_fund_nav_value.mutual_fund_id'], 
        }
    
Base.metadata.create_all(engine)
metadata_obj = MetaData(engine)
# print("Hello")
for t in metadata_obj.sorted_tables:
    print(t.name)