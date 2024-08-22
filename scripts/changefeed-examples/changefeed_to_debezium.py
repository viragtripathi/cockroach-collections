import json
from datetime import datetime
import sys

# Function to convert CockroachDB timestamp to Debezium format (milliseconds since epoch)
def convert_to_debezium_ts(cockroachdb_ts):
    dt = datetime.strptime(cockroachdb_ts, '%Y-%m-%dT%H:%M:%S.%f')
    return int(dt.timestamp() * 1000)

# Function to convert changefeed output to Debezium format
def convert_to_debezium_format(changefeed_event):
    debezium_event = {}

    # Error handling to check if 'operation' key exists
    if 'operation' not in changefeed_event:
        raise KeyError("The 'operation' field is missing in the changefeed event.")
    
    after_data = changefeed_event.get("after", {})
    before_data = changefeed_event.get("before", None)
    
    # Map operation types to Debezium format
    operation = changefeed_event['operation']
    
    if operation == 'insert':
        debezium_event['before'] = None
        debezium_event['after'] = after_data
        debezium_event['op'] = 'c'  # 'c' for create (insert)
    elif operation == 'update':
        debezium_event['before'] = before_data
        debezium_event['after'] = after_data
        debezium_event['op'] = 'u'  # 'u' for update
    elif operation == 'delete':
        debezium_event['before'] = before_data
        debezium_event['after'] = None
        debezium_event['op'] = 'd'  # 'd' for delete
    else:
        raise ValueError(f"Unknown operation type: {operation}")

    # Convert timestamps to Debezium format (milliseconds since epoch)
    created_at = after_data.get("created_at")
    updated_at = after_data.get("updated_at")

    if updated_at:
        ts_ms = convert_to_debezium_ts(updated_at)
    elif created_at:
        ts_ms = convert_to_debezium_ts(created_at)
    else:
        ts_ms = None

    # Add source metadata and timestamp
    debezium_event['source'] = {
        'version': '2.7.1.Final',
        'connector': 'cockroachdb',
        'name': 'dbserver1',
        'ts_ms': ts_ms,
        'db': 'orders_db',
        'table': 'orders'
    }
    
    debezium_event['ts_ms'] = ts_ms
    
    return debezium_event

# Function to load changefeed event from a file (assuming JSON format)
def load_event_from_file(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

# Main function to handle input from parameter or file
def main():
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        try:
            changefeed_event = load_event_from_file(file_path)
            print(f"Loaded changefeed event from file: {file_path}")
        except Exception as e:
            print(f"Failed to load file: {e}")
            return
    else:
        changefeed_event = {
            "after": {
                "id": "ddbeddb2-ef34-444f-a5f4-1eae49a1e9bf",
                "customer_id": "3b75f86e-d3ad-4b7e-bb27-ef0e50c6f36e",
                "order_total": 150.75,
                "order_status": "Pending",
                "created_at": "2024-08-21T20:05:02.048754",
                "updated_at": "2024-08-21T20:05:02.048754"
            },
            "before": None,
            "operation": "insert",
            "updated": "2024-08-21T20:05:02.048754"
        }

    # Check if the event has an 'operation' key
    if 'operation' not in changefeed_event:
        print("Error: The 'operation' field is missing from the event.")
        return

    # Convert the changefeed event to Debezium format
    try:
        debezium_event = convert_to_debezium_format(changefeed_event)
        print(json.dumps(debezium_event, indent=2))
    except KeyError as e:
        print(f"KeyError: {e}")
    except ValueError as e:
        print(f"ValueError: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# Call the main function when running the script
if __name__ == "__main__":
    main()

