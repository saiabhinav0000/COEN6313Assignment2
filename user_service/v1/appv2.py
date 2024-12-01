from flask import Flask, request, jsonify
from pymongo import MongoClient
from pymongo.server_api import ServerApi
import pika
import json

app = Flask(__name__)

# MongoDB Configuration
MONGODB_URI = "mongodb+srv://mongo:ipW272wjb1fwWRSi@cluster0.efff1.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGODB_URI, server_api=ServerApi('1'))
db = client.userDB

# RabbitMQ Configuration
rabbitmq_connection = None
rabbitmq_channel = None

def setup_rabbitmq():
    try:
        credentials = pika.PlainCredentials('guest', 'guest')
        parameters = pika.ConnectionParameters(
            host='localhost',
            port=5672,
            virtual_host='/',
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300
        )
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.exchange_declare(exchange='user_updates', exchange_type='fanout')
        return connection, channel
    except Exception as e:
        print(f"RabbitMQ Connection Error: {e}")
        return None, None

def ensure_rabbitmq_connection():
    global rabbitmq_connection, rabbitmq_channel
    try:
        if not rabbitmq_connection or rabbitmq_connection.is_closed:
            rabbitmq_connection, rabbitmq_channel = setup_rabbitmq()
        elif not rabbitmq_channel or rabbitmq_channel.is_closed:
            rabbitmq_channel = rabbitmq_connection.channel()
            rabbitmq_channel.exchange_declare(exchange='user_updates', exchange_type='fanout')
    except Exception as e:
        print(f"Error ensuring RabbitMQ connection: {e}")
        rabbitmq_connection, rabbitmq_channel = setup_rabbitmq()

@app.route('/users/<user_id>', methods=['PUT'])
def update_user(user_id):
    global rabbitmq_connection, rabbitmq_channel
    try:
        data = request.json
        
        # Verify user exists
        existing_user = db.users.find_one({"userId": user_id})
        if not existing_user:
            return jsonify({"error": "User not found"}), 404

        # Prepare update data
        update_data = {}
        if 'email' in data:
            update_data['email'] = data['email']
        if 'deliveryAddress' in data:
            update_data['deliveryAddress'] = data['deliveryAddress']

        # Update user
        result = db.users.update_one(
            {"userId": user_id},
            {"$set": update_data}
        )

        if result.modified_count:
            # Ensure RabbitMQ connection is active
            ensure_rabbitmq_connection()
            
            if rabbitmq_channel and not rabbitmq_channel.is_closed:
                try:
                    event_data = {
                        "userId": user_id,
                        "email": data.get('email', existing_user['email']),
                        "deliveryAddress": data.get('deliveryAddress', existing_user['deliveryAddress']),
                        "eventType": "USER_UPDATED"
                    }
                    
                    rabbitmq_channel.basic_publish(
                        exchange='user_updates',
                        routing_key='',
                        body=json.dumps(event_data),
                        properties=pika.BasicProperties(
                            delivery_mode=2  # make message persistent
                        )
                    )
                    
                    return jsonify({
                        "message": "User updated and event published",
                        "updates": update_data
                    }), 200
                except Exception as rmq_error:
                    print(f"RabbitMQ publishing error: {rmq_error}")
                    return jsonify({
                        "message": "User updated but event publishing failed",
                        "error": str(rmq_error)
                    }), 200
            
            return jsonify({
                "message": "User updated but RabbitMQ connection unavailable",
                "updates": update_data
            }), 200
        
        return jsonify({
            "message": "No changes made",
            "current_values": {
                "email": existing_user['email'],
                "deliveryAddress": existing_user['deliveryAddress']
            }
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/users', methods=['POST'])
def create_user():
    try:
        data = request.json
        
        # Validate required fields
        if not all(key in data for key in ['userId', 'email', 'deliveryAddress']):
            return jsonify({"error": "Missing required fields"}), 400

        # Check for existing user
        if db.users.find_one({"userId": data['userId']}):
            return jsonify({"error": "User already exists"}), 409

        # Create user
        new_user = {
            "userId": data['userId'],
            "email": data['email'],
            "deliveryAddress": data['deliveryAddress']
        }
        
        result = db.users.insert_one(new_user)
        
        return jsonify({
            "message": "User created successfully",
            "userId": data['userId']
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/users/<user_id>', methods=['GET'])
def get_user(user_id):
    try:
        user = db.users.find_one({"userId": user_id})
        if user:
            user['_id'] = str(user['_id'])
            return jsonify(user), 200
        return jsonify({"error": "User not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 400



if __name__ == '__main__':
    app.run(port=5001)