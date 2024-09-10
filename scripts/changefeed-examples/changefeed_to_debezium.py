import json
import os
import datetime

# Function to load schema config from a file
def load_schema_config(config_file_path):
    with open(config_file_path, 'r') as file:
        schema_config = json.load(file)
    return schema_config

# Function to convert resolved timestamp to LSN (mocked from timestamp)
def resolved_to_lsn(resolved_timestamp):
    try:
        # Convert the resolved timestamp to milliseconds as LSN
        return int(datetime.datetime.strptime(resolved_timestamp, "%Y-%m-%dT%H:%M:%S.%fZ").timestamp() * 1000)
    except ValueError:
        raise ValueError(f"Invalid resolved timestamp format: {resolved_timestamp}")

# Function to handle missing fields
def validate_changefeed_event(changefeed_event):
    if "op" not in changefeed_event:
        raise KeyError("Missing 'op' field in changefeed event")
    if "resolved" not in changefeed_event:
        raise KeyError("Missing 'resolved' field for timestamp in changefeed event")

# Recursive function to handle complex nested schema structures
def handle_complex_schema(schema, data):
    processed_data = {}
    for field in schema["fields"]:
        field_name = field["field"]
        field_type = field["type"]
        
        if field_type == "struct" and "fields" in field:
            # Recursively handle nested struct types
            processed_data[field_name] = handle_complex_schema(field, data.get(field_name, {}))
        else:
            processed_data[field_name] = data.get(field_name)
    return processed_data

# Function to create Debezium-style output
def convert_to_debezium_format(changefeed_event, schema_config):
    # Validate changefeed event structure
    validate_changefeed_event(changefeed_event)

    # Extract the 'after', 'before', and 'resolved' data
    after_data = changefeed_event.get("after", None)
    before_data = changefeed_event.get("before", None)  # Handle before data if present
    op = changefeed_event["op"]  # Changed from 'operation' to 'op'
    resolved_timestamp = changefeed_event["resolved"]

    # Convert the resolved timestamp to LSN
    lsn = resolved_to_lsn(resolved_timestamp)

    # Mock txId - in real CockroachDB, this would come from the changefeed metadata
    txId = hash(resolved_timestamp)  # Simplified txId for illustration

    # Extract dynamic DB, schema, and table names from schema config
    db_name = schema_config.get("db", "postgres")
    schema_name = schema_config.get("schema", "public")
    table_name = schema_config.get("table", "customers")

    # Process before and after data with the schema structure
    processed_before = handle_complex_schema(schema_config["schema"]["fields"][0], before_data) if before_data else None
    processed_after = handle_complex_schema(schema_config["schema"]["fields"][1], after_data) if after_data else None

    # Prepare the Debezium message structure
    debezium_message = {
        "schema": schema_config["schema"],
        "payload": {
            "before": processed_before,  # Handle 'before' data
            "after": processed_after,  # Handle 'after' data
            "source": {
                "version": "2.1.4.Final",
                "connector": "postgresql",
                "name": "PostgreSQL_server",
                "ts_ms": int(datetime.datetime.now().timestamp() * 1000),
                "snapshot": False,
                "db": db_name,  # Dynamic db
                "schema": schema_name,  # Dynamic schema
                "table": table_name,  # Dynamic table
                "txId": txId,  # Derived txId from resolved timestamp
                "lsn": lsn,  # Use the derived LSN from resolved timestamp
                "xmin": None
            },
            "op": op,
            "ts_ms": int(datetime.datetime.now().timestamp() * 1000)
        }
    }

    return debezium_message

# Example usage
if __name__ == "__main__":
    # Paths to files (change these as needed)
    changefeed_event_file = "changefeed_event.json"
    schema_config_file = "schema_config.json"  # Update with the actual path to your schema config

    # Load changefeed event
    with open(changefeed_event_file, 'r') as file:
        changefeed_event = json.load(file)
    
    # Load schema config
    schema_config = load_schema_config(schema_config_file)

    # Convert to Debezium format
    try:
        debezium_output = convert_to_debezium_format(changefeed_event, schema_config)

        # Print or save the output
        output_path = "debezium_event.json"  # Update with the desired output path
        with open(output_path, 'w') as output_file:
            json.dump(debezium_output, output_file, indent=4)

        print("Debezium event saved to:", output_path)
    except (KeyError, ValueError) as e:
        print(f"Error processing event: {e}")

