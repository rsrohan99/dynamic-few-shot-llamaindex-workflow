# simulating a database

import json

db = []

with open("sample_database.json", "r") as f:
    db = json.load(f)


def get_order(order_id):
    for order in db:
        if order["order_number"] == order_id:
            return order
    return None
