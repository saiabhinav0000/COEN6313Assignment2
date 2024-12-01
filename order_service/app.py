from flask import Flask, request, jsonify
from pymongo import MongoClient
import threading
import pymongo
from event_consumer import setup_event_consumer
import logging
import certifi

app = Flask(__name__)

# MongoDB Configuration with SSL settings
MONGODB_URI = "mongodb+srv://mongo:ipW272wjb1fwWRSi@cluster0.efff1.mongodb.net/?retryWrites=true&w=majority"

# Configure MongoDB client with SSL settings
client = MongoClient(
    MONGODB_URI,
    tls=True,
    tlsCAFile=certifi.where()
)

db = client.orderDB

# Define order status constants
ORDER_STATUSES = ['under process', 'shipping', 'delivered']

def remove_duplicates():
    pipeline = [
        {"$group": {
            "_id": "$orderId",
            "count": {"$sum": 1},
            "docs": {"$push": "$_id"}
        }},
        {"$match": {
            "count": {"$gt": 1}
        }}
    ]
    duplicates = list(db.orders.aggregate(pipeline))
    for duplicate in duplicates:
        duplicate_docs = duplicate['docs']
        db.orders.delete_many({"_id": {"$in": duplicate_docs[1:]}})

def create_unique_index():
    try:
        # Remove duplicates before creating index
        remove_duplicates()
        indexes = db.orders.index_information()
        if 'orderId_1' not in indexes:
            db.orders.create_index([('orderId', pymongo.ASCENDING)], unique=True)
    except Exception as e:
        print(f"Error creating unique index: {e}")

@app.route('/orders', methods=['POST'])
def create_order():
    data = request.json
    # Check if orderId already exists
    if db.orders.find_one({"orderId": data['orderId']}):
        return jsonify({"error": f"Order with orderId {data['orderId']} already exists"}), 409

    # Proceed with order creation if orderId does not exist
    required_fields = ['orderId', 'userId', 'userEmail', 'deliveryAddress', 'items']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    if not isinstance(data['items'], list):
        return jsonify({"error": "Items must be an array"}), 400
    formatted_items = []
    for item in data['items']:
        if 'name' not in item or 'quantity' not in item:
            return jsonify({"error": "Each item must have 'name' and 'quantity' fields"}), 400
        formatted_items.append({
            "name": item['name'],
            "quantity": item['quantity']
        })
    new_order = {
        "orderId": data['orderId'],
        "userId": data['userId'],
        "userEmail": data['userEmail'],
        "deliveryAddress": data['deliveryAddress'],
        "items": formatted_items,
        "orderStatus": "under process"
    }
    db.orders.insert_one(new_order)
    return jsonify({"message": "Order created successfully", "order": new_order}), 201




@app.route('/orders/<order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    try:
        data = request.json
        new_status = data.get('orderStatus')
        if new_status not in ORDER_STATUSES:
            return jsonify({"error": f"Invalid status. Must be one of: {', '.join(ORDER_STATUSES)}"}), 400
        update_result = db.orders.update_one(
            {"orderId": order_id},
            {"$set": {"orderStatus": new_status}}
        )
        if update_result.modified_count:
            updated_order = db.orders.find_one({"orderId": order_id}, {'_id': 0})
            return jsonify({
                "message": "Order status updated successfully",
                "order": updated_order
            }), 200
        return jsonify({"message": "No changes made"}), 200
    except Exception as e:
        print(f"Error updating order status: {str(e)}")
        return jsonify({"error": str(e)}), 400

@app.route('/orders', methods=['GET'])
def get_orders():
    try:
        user_id = request.args.get('userId')
        query = {"userId": user_id} if user_id else {}
        orders = list(db.orders.find(query, {'_id': 0}))
        return jsonify({"message": "Orders retrieved successfully", "orders": orders}), 200
    except Exception as e:
        print(f"Error fetching orders: {str(e)}")
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    create_unique_index()  # Ensure unique index exists before running the app
    consumer_thread = threading.Thread(target=setup_event_consumer)
    consumer_thread.daemon = True
    consumer_thread.start()
    app.run(port=5003)
