import psycopg2
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import sys
import csv
import json
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import logging
import yaml
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import smtplib
from email.mime.text import MIMEText
import re
import argparse
import gzip
import tarfile
from faker import Faker

# Load configuration with environment variable substitution
def load_config(config_path):
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
    except FileNotFoundError:
        logging.critical(f"Configuration file '{config_path}' not found. Please provide a valid config file.")
        sys.exit(1)
    except yaml.YAMLError as exc:
        logging.critical(f"Error parsing YAML file '{config_path}': {exc}")
        sys.exit(1)

    # Replace any environment variables in the configuration
    def replace_env_variables(value):
        if isinstance(value, str):
            # Look for patterns like ${VAR_NAME}
            matches = re.findall(r'\$\{([A-Z_][A-Z0-9_]*)\}', value)
            for match in matches:
                env_value = os.getenv(match)
                if env_value:
                    value = value.replace(f"${{{match}}}", env_value)
                else:
                    logging.warning(f"Environment variable {match} is not set.")
        return value

    def recursive_replace(config):
        if isinstance(config, dict):
            return {k: recursive_replace(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [recursive_replace(i) for i in config]
        else:
            return replace_env_variables(config)

    return recursive_replace(config)

# Configure logging
def setup_logging(level):
    logging.basicConfig(
        level=level,
        format='%(asctime)s %(levelname)s: %(message)s',
        handlers=[
            logging.FileHandler("crdb_data_loader.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )

# Slack alert function
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

# Email alert function
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

def load_batch(connection, insert_query, batch_data, total_records, records_loaded, max_retries=3, slack_token=None, slack_channel=None, alert_email=None, smtp_server=None):
    """Load a single batch of data into the database with retry logic and logging."""
    retries = 0
    while retries < max_retries:
        try:
            with connection.cursor() as cursor:
                cursor.executemany(insert_query, batch_data)
                connection.commit()
            records_loaded += len(batch_data)
            percent_complete = (records_loaded / total_records) * 100
            logging.info(f"Batch loaded successfully: {len(batch_data)} records. {percent_complete:.2f}% complete.")
            return records_loaded
        except Exception as e:
            retries += 1
            connection.rollback()
            logging.warning(f"Failed to load batch, retry {retries}/{max_retries}: {e}")
            time.sleep(2 ** retries)
            if retries == max_retries:
                logging.error(f"Batch permanently failed after {max_retries} retries")
                alert_message = f"Data Loader Error: Failed to load a batch of data after {max_retries} retries.\nError: {e}"
                send_slack_alert(alert_message, slack_token, slack_channel)
                send_email_alert("Data Loader Error", alert_message, alert_email, from_email=alert_email, smtp_server=smtp_server)
                raise e

def read_data(file_path, file_format='csv'):
    """Read data from different file formats, including support for compressed files."""
    if file_path.endswith('.gz'):
        open_func = gzip.open
    elif file_path.endswith('.tar.gz'):
        tar = tarfile.open(file_path, "r:gz")
        members = tar.getmembers()
        # Assume only one data file inside the tar.gz
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

def generate_fake_data(schema, num_records):
    """Generate fake data based on the provided schema."""
    fake = Faker()
    data = []
    for _ in range(num_records):
        record = []
        for column in schema:
            if column['type'] == 'string':
                record.append(fake.name() if 'name' in column.get('name_hint', '').lower() else fake.word())
            elif column['type'] == 'int':
                record.append(fake.random_int(min=column.get('min', 0), max=column.get('max', 100)))
            elif column['type'] == 'date':
                record.append(fake.date())
            elif column['type'] == 'email':
                record.append(fake.email())
            elif column['type'] == 'address':
                record.append(fake.address())
            else:
                record.append(fake.word())  # Default fallback for unknown types
        data.append(tuple(record))
    return data

def validate_data_load(connection, table_name, expected_records):
    """Validate that the correct number of records were inserted into the table."""
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

def data_loader(config):
    """Main function to load data into CockroachDB with logging and error handling."""
    connection = None
    try:
        connection = psycopg2.connect(**config['connection_params'])
        insert_query = f"INSERT INTO {config['table_name']} ({', '.join(config['columns'])}) VALUES ({', '.join(['%s'] * len(config['columns']))})"
        
        batch_data = []
        records_loaded = 0
        futures = []

        # Check if fake data generation is enabled
        if config.get('generate_fake_data'):
            schema = config['generate_fake_data']['schema']
            num_records = config['generate_fake_data']['num_records']
            fake_data = generate_fake_data(schema, num_records)
            total_records = len(fake_data)
            logging.info(f"Generated {total_records} fake records for table {config['table_name']}.")

            for row in fake_data:
                batch_data.append(row)
                if len(batch_data) >= config['batch_size']:
                    futures.append(executor.submit(load_batch, connection, insert_query, batch_data.copy(),
                                                   total_records, records_loaded,
                                                   slack_token=config.get('slack_token'), slack_channel=config.get('slack_channel'),
                                                   alert_email=config.get('alert_email'), smtp_server=config.get('smtp_server')))
                    batch_data.clear()
        else:
            with ThreadPoolExecutor(max_workers=config['num_threads']) as executor:
                for row, total_records in read_data(config['file_path'], config['file_format']):
                    batch_data.append(row)
                    if len(batch_data) >= config['batch_size']:
                        futures.append(executor.submit(load_batch, connection, insert_query, batch_data.copy(),
                                                       total_records, records_loaded,
                                                       slack_token=config.get('slack_token'), slack_channel=config.get('slack_channel'),
                                                       alert_email=config.get('alert_email'), smtp_server=config.get('smtp_server')))
                        batch_data.clear()

                if batch_data:
                    futures.append(executor.submit(load_batch, connection, insert_query, batch_data.copy(),
                                                   total_records, records_loaded,
                                                   slack_token=config.get('slack_token'), slack_channel=config.get('slack_channel'),
                                                   alert_email=config.get('alert_email'), smtp_server=config.get('smtp_server')))

        for future in as_completed(futures):
            try:
                records_loaded = future.result()
            except Exception as e:
                logging.error(f"Batch failed: {e}")
                alert_message = f"Data Loader Critical Error: {e}"
                send_slack_alert(alert_message, config.get('slack_token'), config.get('slack_channel'))
                send_email_alert("Data Loader Critical Error", alert_message, config.get('alert_email'), from_email=config.get('alert_email'), smtp_server=config.get('smtp_server'))

        # Validate the data load
        validate_data_load(connection, config['table_name'], total_records)

    except Exception as e:
        logging.critical(f"Failed to complete data loading process: {e}")
        alert_message = f"Data Loader Critical Failure: Failed to complete data loading process.\nError: {e}"
        send_slack_alert(alert_message, config.get('slack_token'), config.get('slack_channel'))
        send_email_alert("Data Loader Critical Failure", alert_message, config.get('alert_email'), from_email=config.get('alert_email'), smtp_server=config.get('smtp_server'))
    finally:
        if connection:
            connection.close()

class ConfigFileEventHandler(FileSystemEventHandler):
    """Watch for changes in the config file to trigger data loading."""
    def __init__(self, loader_func, config):
        super().__init__()
        self.loader_func = loader_func
        self.config = config

    def on_modified(self, event):
        if event.src_path.endswith("config.yaml"):
            logging.info("Configuration changed, reloading data...")
            self.loader_func(self.config)

def schedule_loader(schedule_time, loader_func, config):
    """Schedule the data loader to run at a specific time."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(loader_func, 'interval', minutes=schedule_time, args=[config])
    scheduler.start()
    logging.info(f"Data loader scheduled to run every {schedule_time} minutes.")

def start_file_watch(loader_func, config):
    """Start watching for config file changes."""
    event_handler = ConfigFileEventHandler(loader_func, config)
    observer = Observer()
    observer.schedule(event_handler, path='.', recursive=False)
    observer.start()
    logging.info("Started watching config file for changes.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

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

    # Setup logging
    setup_logging(config.get('log_level', 'INFO'))

    if args.schedule:
        if 'schedule_time' in config:
            schedule_loader(config['schedule_time'], data_loader, config)
        else:
            logging.error("Schedule time not defined in the configuration file.")
            sys.exit(1)
    elif args.watch:
        start_file_watch(data_loader, config)
    else:
        print_help()
        sys.exit(0)

