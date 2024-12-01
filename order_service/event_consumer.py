import pika
import json
from pymongo import MongoClient
from pymongo.server_api import ServerApi

# MongoDB Configuration
MONGODB_URI = "mongodb+srv://mongo:ipW272wjb1fwWRSi@cluster0.efff1.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGODB_URI, server_api=ServerApi('1'))
db = client.orderDB

def process_user_update(ch, method, properties, body):
    try:
        print(f"Received message: {body}")  # Debug print
        event_data = json.loads(body)
        user_id = event_data.get('userId')
        email = event_data.get('email')
        delivery_address = event_data.get('deliveryAddress')

        print(f"Processing update for user {user_id}")  # Debug print

        # Update all orders for this user
        if user_id:
            update_data = {}
            if email:
                update_data['userEmail'] = email
            if delivery_address:
                update_data['deliveryAddress'] = delivery_address

            if update_data:
                result = db.orders.update_many(
                    {"userId": user_id},
                    {"$set": update_data}
                )
                print(f"Updated {result.modified_count} orders for user {user_id}")
                print(f"Update data: {update_data}")  # Debug print

    except Exception as e:
        print(f"Error processing user update: {e}")

def setup_event_consumer():
    try:
        # RabbitMQ Connection with retry
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='localhost',
                port=5672,
                virtual_host='/',
                credentials=pika.PlainCredentials('guest', 'guest'),
                heartbeat=600,
                connection_attempts=3,
                retry_delay=5
            )
        )
        channel = connection.channel()

        # Declare exchange
        channel.exchange_declare(exchange='user_updates', exchange_type='fanout')

        # Create queue and bind to exchange
        result = channel.queue_declare(queue='order_updates', durable=True)
        queue_name = result.method.queue
        channel.queue_bind(exchange='user_updates', queue=queue_name)

        # Set up consumer
        channel.basic_consume(
            queue=queue_name,
            on_message_callback=process_user_update,
            auto_ack=True
        )

        print("Started consuming user update events...")
        channel.start_consuming()

    except Exception as e:
        print(f"Error setting up event consumer: {e}")

if __name__ == "__main__":
    print("Starting Order Service Event Consumer...")
    setup_event_consumer()