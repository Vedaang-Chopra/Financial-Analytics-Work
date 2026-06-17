import pika

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

channel.exchange_declare(exchange='mutual_fund_data_collection', exchange_type='direct')

class Generic_Consumer_Setup:
    def __init__(self, ROUTING_KEY, QUEUE_NAME) -> None:
        self.__ROUTING_KEY=ROUTING_KEY
        self.__QUEUE_NAME=QUEUE_NAME
        
        # Setup Queues for AMC List..............
        self.setup_rabbitmq_consumer()
    
    def setup_rabbitmq_consumer(self):
        result = channel.queue_declare(queue=self.__QUEUE_NAME, durable=True)
        channel.queue_bind(exchange='mutual_fund_data_collection', queue=self.__QUEUE_NAME, routing_key=self.__ROUTING_KEY)

list_of_amc_conumer=Generic_Consumer_Setup("list_of_amc", "list_of_amc_queue")
nav_daily_data=Generic_Consumer_Setup("daily_nav_data", "daily_nav_data_queue")