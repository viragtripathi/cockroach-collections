import psycopg2
from psycopg2 import pool
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import sys
import csv
import yaml
import logging
import argparse
import gzip
import tarfile
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import smtplib
from email.mime.text import MIMEText
import time
import threading

# Initialize a global connection pool variable
connection_pool = None

def load_config(config_path):
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        return config
    except FileNotFoundError:
        logging.critical(f"Configuration file '{config_path}' not found. Please provide a valid config file.")
        sys.exit(1)
    except yaml.YAMLError as exc:
        logging.critical(f"Error parsing YAML file '{config_path}': {exc}")
        sys.exit(1)

def setup_logging(level):
    logging.getLogger().handlers.clear()
    logging.basicConfig(
        level=level,
        format='%(asctime)s %(levelname)s: %(message)s',
        handlers=[
            logging.FileHandler("crdb_data_loader.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )

def init_connection_pool(config):
    global connection_pool
    try:
        connection_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=config['num_threads'],
            user=config['connection_params']['user'],
            password=config['connection_params']['password'],
            host=config['connection_params']['host'],
            port=config['connection_params']['port'],
            database=config['connection_params']['dbname']
        )
        logging.info("Database connection pool created successfully.")
    except Exception as e:
        logging.critical(f"Error creating connection pool: {e}")
        sys.exit(1)

def get_connection():
    try:
        return connection_pool.getconn()
    except Exception as e:
        logging.error(f"Error getting connection from pool: {e}")
        return None

def release_connection(conn):
    try:
        connection_pool.putconn(conn)
    except Exception as e:
        logging.error(f"Error returning connection to pool: {e}")

def send_slack_alert(message, slack_token, slack_channel):
    if slack_token and slack_channel:
        client = WebClient(token=slack_token)
        try:
            response = client.chat_postMessage(channel=slack_channel, text=message)
            logging.info(f"Slack message sent: {response['ts']}")
        except SlackApiError as e:
            logging.error(f"Failed to send Slack message: {e.response['error']}")
    else:
        logging.info("Slack alerts are disabled as Slack token or channel is not provided.")

def send_email_alert(subject, body, to_email, from_email, smtp_server):
    if to_email and from_email and smtp_server:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = to_email

        try:
            with smtplib.SMTP(smtp_server) as server:
                server.sendmail(from_email, [to_email], msg.as_string())
            logging.info(f"Alert email sent to {to_email}: {subject}")
        except Exception as e:
            logging.error(f"Failed to send email alert: {e}")
    else:
        logging.info("Email alerts are disabled as email configuration is not fully provided.")

def load_batch(insert_query, batch_data, total_records, records_loaded, max_retries=3, slack_token=None, slack_channel=None, alert_email=None, smtp_server=None):
    conn = get_connection()
    if not conn:
        logging.error("No connection available for loading batch.")
        return records_loaded, 0

    start_time = time.time()
    retries = 0
    thread_name = threading.current_thread().name

    while retries < max_retries:
        try:
            with conn.cursor() as cursor:
                cursor.executemany(insert_query, batch_data)
                conn.commit()
            records_loaded += len(batch_data)
            percent_complete = (records_loaded / total_records) * 100
            print(f"\rRecords Loaded: {records_loaded} ({percent_complete:.2f}% complete)", end="")
            sys.stdout.flush()
            elapsed_time = time.time() - start_time
            logging.debug(f"{thread_name} finished loading {len(batch_data)} records in {elapsed_time:.2f} seconds.")
            return records_loaded, elapsed_time
        except Exception as e:
            retries += 1
            conn.rollback()
            logging.warning(f"{thread_name} failed to load batch, retry {retries}/{max_retries}: {e}")
            time.sleep(2 ** retries)
            if retries == max_retries:
                logging.error(f"{thread_name} permanently failed after {max_retries} retries")
                alert_message = f"Data Loader Error: {thread_name} failed to load a batch of data after {max_retries} retries.\nError: {e}"
                send_slack_alert(alert_message, slack_token, slack_channel)
                send_email_alert("Data Loader Error", alert_message, alert_email, from_email=alert_email, smtp_server=smtp_server)
                raise e
        finally:
            release_connection(conn)  # This ensures the connection is released after each batch attempt

def read_data(file_path, file_format='csv'):
    if file_path.endswith('.gz'):
        open_func = gzip.open
    elif file_path.endswith('.tar.gz'):
        tar = tarfile.open(file_path, "r:gz")
        members = tar.getmembers()
        open_func = lambda: tar.extractfile(members[0])
    else:
        open_func = open

    with open_func(file_path, 'rt') as file:
        if file_format == 'csv' or file_format == 'tsv':
            delimiter = ',' if file_format == 'csv' else '\t'
            reader = csv.reader(file, delimiter=delimiter)
            headers = next(reader)  # Skip header row if necessary
            total_records = sum(1 for _ in reader)
            file.seek(0)
            headers = next(reader)
            for row in reader:
                yield tuple(row), total_records
        elif file_format == 'json':
            data = json.load(file)
            total_records = len(data)
            for entry in data:
                yield tuple(entry.values()), total_records
        elif file_format == 'parquet':
            df = pd.read_parquet(file_path)
            total_records = len(df)
            for row in df.itertuples(index=False, name=None):
                yield row, total_records

def validate_data_load(connection, table_name, expected_records):
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            result = cursor.fetchone()
            actual_records = result[0]
            if actual_records == expected_records:
                logging.info(f"Validation successful: {actual_records}/{expected_records} records inserted.")
            else:
                logging.error(f"Validation failed: {actual_records}/{expected_records} records inserted.")
    except Exception as e:
        logging.error(f"Failed to validate data load: {e}")

def process_data_load(config):
    start_time = time.time()

    init_connection_pool(config)  # Initialize the connection pool

    insert_query = f"INSERT INTO {config['table_name']} ({', '.join(config['columns'])}) VALUES ({', '.join(['%s'] * len(config['columns']))})"
    logging.debug(f"Insert query: {insert_query}")

    try:
        file_path = config['file_path']
        logging.debug(f"Attempting to read the data file from path: {file_path}")
        records_loaded = 0
        batch_data = []
        thread_times = []

        with ThreadPoolExecutor(max_workers=config['num_threads']) as executor:
            futures = []
            for row, total_records in read_data(file_path, config['file_format']):
                batch_data.append(row)
                if len(batch_data) >= config['batch_size']:
                    future = executor.submit(load_batch, insert_query, batch_data, total_records, records_loaded,
                                             slack_token=config.get('slack_token'), slack_channel=config.get('slack_channel'),
                                             alert_email=config.get('alert_email'), smtp_server=config.get('smtp_server'))
                    futures.append(future)
                    batch_data = []

            if batch_data:
                future = executor.submit(load_batch, insert_query, batch_data, total_records, records_loaded,
                                         slack_token=config.get('slack_token'), slack_channel=config.get('slack_channel'),
                                         alert_email=config.get('alert_email'), smtp_server=config.get('smtp_server'))
                futures.append(future)

            for future in as_completed(futures):
                try:
                    result, thread_time = future.result()
                    records_loaded = result
                    thread_times.append(thread_time)
                except Exception as e:
                    logging.error(f"Failed to process a batch: {e}")

        conn = get_connection()
        validate_data_load(conn, config['table_name'], total_records)
        release_connection(conn)

    except Exception as e:
        logging.critical(f"Failed to process the data file: {e}")
        sys.exit(1)
    finally:
        if connection_pool:
            connection_pool.closeall()  # Close all connections in the pool
        logging.debug("Database connection pool closed.")

    end_time = time.time()
    total_time = end_time - start_time
    logging.info(f"\nTotal time taken for the data load: {total_time:.2f} seconds.")

    for idx, thread_time in enumerate(thread_times, start=1):
        logging.info(f"Thread {idx} took {thread_time:.2f} seconds.")

    logging.debug("Exiting script.")

def print_help():
    help_message = """
    Usage: python crdb_data_loader.py [options]

    Options:
    -h, --help                Show this help message and exit.
    -c, --config CONFIG_FILE  Path to the YAML configuration file.
    -s, --schedule            Run the data loader on a schedule (defined in config.yaml).
    -w, --watch               Watch for changes in the config.yaml file and automatically reload data.
    """
    print(help_message)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-c', '--config', type=str, required=False, help="Path to the YAML configuration file.")
    parser.add_argument('-s', '--schedule', action='store_true', help="Run the data loader on a schedule (defined in config.yaml).")
    parser.add_argument('-w', '--watch', action='store_true', help="Watch for changes in the config.yaml file and automatically reload data.")
    parser.add_argument('-h', '--help', action='store_true', help="Show help message and exit.")

    args = parser.parse_args()

    if args.help:
        print_help()
        sys.exit(0)

    config_file_path = args.config if args.config else "config.yaml"
    config = load_config(config_file_path)

    setup_logging(config.get('log_level', 'DEBUG'))

    if args.schedule:
        if 'schedule_time' in config:
            schedule_loader(config['schedule_time'], process_data_load, config)
        else:
            logging.error("Schedule time not defined in the configuration file.")
            sys.exit(1)
    elif args.watch:
        start_file_watch(process_data_load, config)
    else:
        process_data_load(config)

