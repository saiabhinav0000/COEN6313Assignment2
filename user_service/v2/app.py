from flask import Flask, request, jsonify
from pymongo import MongoClient
from pymongo.server_api import ServerApi
import pika
import json
import os
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
file_handler = RotatingFileHandler('user_service_v2.log', maxBytes=1024*1024*5, backupCount=3)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger = logging.getLogger()
logger.addHandler(file_handler)

app = Flask(__name__)

# MongoDB Configuration
MONGODB_URI = os.getenv('MONGODB_URI')
client = MongoClient(MONGODB_URI, server_api=ServerApi('1'))
db = client.userDB

# RabbitMQ Configuration
credentials = pika.PlainCredentials(os.getenv('RABBITMQ_USER', 'guest'), os.getenv('RABBITMQ_PASS', 'guest'))
parameters = pika.ConnectionParameters(
    host=os.getenv('RABBITMQ_HOST', 'localhost'),
    port=int(os.getenv('RABBITMQ_PORT', 5672)),
    virtual_host='/',
    credentials=credentials,
    heartbeat=600,
    blocked_connection_timeout=300
)
connection = pika.BlockingConnection(parameters)
channel = connection.channel()
channel.exchange_declare(exchange='user_updates', exchange_type='fanout')

@app.route('/users/<user_id>', methods=['PUT'])
def update_user(user_id):
    try:
        data = request.json
        existing_user = db.users.find_one({"userId": user_id})
        if not existing_user:
            return jsonify({"error": "User not found"}), 404

        update_data = {k: data[k] for k in ['email', 'deliveryAddress'] if k in data}
        result = db.users.update_one({"userId": user_id}, {"$set": update_data})

        if result.modified_count:
            event_data = {
                "userId": user_id,
                "email": data.get('email', existing_user['email']),
                "deliveryAddress": data.get('deliveryAddress', existing_user['deliveryAddress']),
                "eventType": "USER_UPDATED"
            }
            channel.basic_publish(
                exchange='user_updates',
                routing_key='',
                body=json.dumps(event_data),
                properties=pika.BasicProperties(delivery_mode=2)
            )
            return jsonify({"message": "User updated and event published", "updates": update_data}), 200
        return jsonify({"message": "No changes made", "current_values": existing_user}), 200

    except Exception as e:
        logger.error("Failed to update user: %s", e)
        return jsonify({"error": str(e)}), 400

@app.route('/users', methods=['POST'])
def create_user():
    try:
        data = request.json
        if db.users.find_one({"userId": data['userId']}):
            return jsonify({"error": "User already exists"}), 409
        db.users.insert_one(data)
        return jsonify({"message": "User created successfully", "userId": data['userId']}), 201
    except Exception as e:
        logger.error("Failed to create user: %s", e)
        return jsonify({"error": str(e)}), 400

@app.route('/users/<user_id>', methods=['GET'])
def get_user(user_id):
    try:
        user = db.users.find_one({"userId": user_id})
        if user:
            user['_id'] = str(user['_id'])  # Convert ObjectId to string for JSON serialization
            return jsonify(user), 200
        return jsonify({"error": "User not found"}), 404
    except Exception as e:
        logger.error("Failed to retrieve user: %s", e)
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(port=5002)
