from flask import Flask, request, jsonify
import requests
import random
import configparser

app = Flask(__name__)

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')

# Service URLs loaded from config file
USER_SERVICE_V1 = config['DEFAULT']['USER_SERVICE_V1_URL']
USER_SERVICE_V2 = config['DEFAULT']['USER_SERVICE_V2_URL']
ORDER_SERVICE = config['DEFAULT']['ORDER_SERVICE_URL']

# Load routing percentage from config and convert to float for probability check
P = float(config['DEFAULT']['ROUTING_PERCENTAGE']) / 100

@app.route('/users', methods=['POST'])
def create_user():
    primary_service = USER_SERVICE_V1 if random.random() < P else USER_SERVICE_V2
    secondary_service = USER_SERVICE_V2 if primary_service == USER_SERVICE_V1 else USER_SERVICE_V1
    try:
        response = requests.post(
            f"{primary_service}/users",
            json=request.json
        )
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as primary_error:
        try:
            response = requests.post(
                f"{secondary_service}/users",
                json=request.json
            )
            return jsonify(response.json()), response.status_code
        except requests.exceptions.RequestException as secondary_error:
            return jsonify({"error": str(secondary_error)}), 500

@app.route('/users/<user_id>', methods=['PUT'])
def update_user(user_id):
    primary_service = USER_SERVICE_V1 if random.random() < P else USER_SERVICE_V2
    secondary_service = USER_SERVICE_V2 if primary_service == USER_SERVICE_V1 else USER_SERVICE_V1
    try:
        response = requests.put(
            f"{primary_service}/users/{user_id}",
            json=request.json,
            headers={'Content-Type': 'application/json'}
        )
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as primary_error:
        try:
            response = requests.put(
                f"{secondary_service}/users/{user_id}",
                json=request.json,
                headers={'Content-Type': 'application/json'}
            )
            return jsonify(response.json()), response.status_code
        except requests.exceptions.RequestException as secondary_error:
            return jsonify({"error": str(secondary_error)}), 500

@app.route('/orders', methods=['GET', 'POST'])
def handle_orders():
    try:
        if request.method == 'GET':
            user_id = request.args.get('userId')
            response = requests.get(f"{ORDER_SERVICE}/orders", params={'userId': user_id})
            return jsonify(response.json()), response.status_code
        else:  # POST
            response = requests.post(
                f"{ORDER_SERVICE}/orders",
                json=request.json
            )
            return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

@app.route('/orders/<order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    try:
        response = requests.put(
            f"{ORDER_SERVICE}/orders/{order_id}/status",
            json=request.json
        )
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000)
