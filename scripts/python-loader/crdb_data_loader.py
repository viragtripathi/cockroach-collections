import psycopg2
from psycopg2 import pool
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import sys
import csv
import yaml
import logging
import argparse
import time
import schedule
from faker import Faker
from tqdm import tqdm
from decimal import Decimal
import random
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import json
import gzip
import tarfile
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import smtplib
from email.mime.text import MIMEText

# Custom generator for unique integers
def generate_unique_int(start=1):
    num = start
    while True:
        yield num
        num += 1

unique_generators = {
    "unique_int": generate_unique_int()
}

def generate_fake_data(num_records, columns_config):
    fake = Faker()
    for _ in range(num_records):
        record = []
        for column, faker_method in columns_config.items():
            if faker_method in unique_generators:
                fake_data = next(unique_generators[faker_method])
            elif '(' in faker_method and ')' in faker_method:
                method_name, args_str = faker_method.split('(', 1)
                method_name = method_name.strip()
                args_str = args_str.rstrip(')').strip()
                if args_str:
                    kwargs = {arg.split('=')[0].strip(): eval(arg.split('=')[1].strip()) for arg in args_str.split(',')}
                    try:
                        fake_data = getattr(fake, method_name)(**kwargs)
                    except Exception as e:
                        logging.error(f"Failed to generate fake data for method '{method_name}': {e}")
                        fake_data = None
                else:
                    fake_data = getattr(fake, method_name)()
            elif hasattr(fake, faker_method.strip()):
                fake_data = getattr(fake, faker_method.strip())()

                # Truncate the fake data to fit within the defined VARCHAR limit
                if column in ['fname', 'lname'] and isinstance(fake_data, str):
                    fake_data = fake_data[:50]

            else:
                logging.error(f"Faker method '{faker_method}' not found.")
                fake_data = None
            record.append(fake_data)
        yield tuple(record)

def read_data(file_path, file_format='csv'):
    if file_path.endswith('.tar.gz'):
        with tarfile.open(file_path, "r:gz") as tar:
            members = [m for m in tar.getmembers() if m.isfile()]
            # Assuming there is only one file in the tar archive or the first CSV file
            csv_file = next((m for m in members if m.name.endswith('.csv')), members[0])
            with tar.extractfile(csv_file) as f:
                reader = csv.reader(f.read().decode('utf-8').splitlines())
                headers = next(reader)  # Skip header row
                data_rows = [tuple(row) for row in reader]
                total_records = len(data_rows)
    elif file_path.endswith('.gz'):
        with gzip.open(file_path, 'rt') as file:
            reader = csv.reader(file)
            headers = next(reader)  # Skip header row
            data_rows = [tuple(row) for row in reader]
            total_records = len(data_rows)
    elif file_path.endswith('.csv'):
        with open(file_path, 'r') as file:
            reader = csv.reader(file)
            headers = next(reader)  # Skip header row
            data_rows = [tuple(row) for row in reader]
            total_records = len(data_rows)
    elif file_format == 'tsv':
        with open(file_path, 'r') as file:
            reader = csv.reader(file, delimiter='\t')
            headers = next(reader)  # Skip header row
            data_rows = [tuple(row) for row in reader]
            total_records = len(data_rows)
    elif file_format == 'json':
        with open(file_path, 'r') as file:
            data = json.load(file)
            data_rows = [tuple(entry.values()) for entry in data]
            total_records = len(data)
    else:
        logging.error(f"Unsupported file format: {file_format}")
        sys.exit(1)

    return data_rows, total_records

def init_connection_pool(config):
    global connection_pool
    try:
        connection_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=config['num_threads'],
            user=config['connection_params']['user'],
            password=os.getenv('DB_PASSWORD', config['connection_params']['password']),
            host=config['connection_params']['host'],
            port=config['connection_params']['port'],
            database=config['connection_params']['dbname'],
            sslmode=config['connection_params'].get('sslmode', 'disable'),
            sslrootcert=config['connection_params'].get('sslrootcert')
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

def truncate_table(table_name):
    conn = get_connection()
    if not conn:
        logging.error("No connection available for truncating the table.")
        return
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"TRUNCATE TABLE {table_name}")
            conn.commit()
        logging.info(f"Table '{table_name}' truncated successfully.")
    except Exception as e:
        conn.rollback()
        logging.error(f"Failed to truncate table '{table_name}': {e}")
    finally:
        release_connection(conn)

def load_batch(insert_query, batch_data, total_records, records_loaded, progress_bar, config):
    conn = get_connection()
    if not conn:
        logging.error("No connection available for loading batch.")
        return records_loaded, 0

    try:
        start_time = time.time()  # Start timing the batch load
        with conn.cursor() as cursor:
            cursor.executemany(insert_query, batch_data)
            conn.commit()
        records_loaded += len(batch_data)
        progress_bar.update(len(batch_data))  # Update progress bar
        elapsed_time = time.time() - start_time  # Calculate time taken to load batch
        return records_loaded, elapsed_time
    except Exception as e:
        conn.rollback()
        logging.error(f"Failed to load batch: {e}")
        send_alerts(f"Failed to load batch: {e}", config)
        return records_loaded, 0
    finally:
        release_connection(conn)

def send_alerts(message, config):
    if config.get('slack_token') and config.get('slack_channel'):
        send_slack_alert(message, config['slack_token'], config['slack_channel'])
    else:
        logging.info("Slack alerts are disabled as Slack token or channel is not provided.")
    
    if config.get('alert_email') and config.get('smtp_server'):
        send_email_alert("Data Loader Alert", message, config['alert_email'], config['smtp_server'])
    else:
        logging.info("Email alerts are disabled as email configuration is not fully provided.")

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

def send_email_alert(subject, body, to_email, smtp_server):
    if to_email and smtp_server:
        from_email = f"data-loader@{smtp_server.split('.')[-2]}.com"
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

def process_data_load(config):
    start_time = time.time()

    init_connection_pool(config)  # Initialize the connection pool

    if config.get('truncate_table', False):
        truncate_table(config['table_name'])

    columns = list(config['columns'].keys())
    insert_query = f"INSERT INTO {config['table_name']} ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))})"
    logging.debug(f"Insert query: {insert_query}")

    try:
        records_loaded = 0
        batch_data = []
        thread_times = []

        if config.get('generate_fake_data', False):
            total_new_records = config.get('num_fake_records', 100000)
            data_source = generate_fake_data(total_new_records, config['columns'])
            progress_bar = tqdm(total=total_new_records, desc="Generating and Loading Fake Data", unit="records")
            total_records = total_new_records  # Initialize total_records for fake data generation
        else:
            file_path = config['file_path']
            if not os.path.exists(file_path):
                logging.critical(f"Data file not found: {file_path}")
                sys.exit(1)
            data_source, total_records = read_data(file_path, config['file_format'])
            progress_bar = tqdm(total=total_records, desc="Loading Data from File", unit="records")

        with ThreadPoolExecutor(max_workers=config['num_threads']) as executor:
            futures = []
            for row in data_source:
                if row is None:
                    continue  # Skip rows that couldn't be generated
                batch_data.append(row)
                if len(batch_data) >= config['batch_size']:
                    future = executor.submit(load_batch, insert_query, batch_data, total_records, records_loaded, progress_bar, config)
                    futures.append(future)
                    batch_data = []

            if batch_data:
                future = executor.submit(load_batch, insert_query, batch_data, total_records, records_loaded, progress_bar, config)
                futures.append(future)

            for future in as_completed(futures):
                try:
                    result, thread_time = future.result()
                    records_loaded = result
                    thread_times.append(thread_time)
                except Exception as e:
                    logging.error(f"Failed to process a batch: {e}")
                    send_alerts(f"Failed to process a batch: {e}", config)

            progress_bar.close()

        end_time = time.time()
        total_time = end_time - start_time
        logging.info(f"Total time taken for the data load: {total_time:.2f} seconds.")

    except Exception as e:
        logging.critical(f"Failed to process the data: {e}")
        send_alerts(f"Failed to process the data: {e}", config)
        sys.exit(1)
    finally:
        if connection_pool:
            connection_pool.closeall()  # Close all connections in the pool
        logging.debug("Database connection pool closed.")

def setup_logging(level):
    logging.getLogger().handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))

    logging.basicConfig(
        level=level,
        format='%(asctime)s %(levelname)s: %(message)s',
        handlers=[
            logging.FileHandler("crdb_data_loader.log"),
            console_handler
        ]
    )

def load_config(config_file):
    try:
        with open(config_file, 'r') as file:
            config = yaml.safe_load(file)
            logging.info(f"Configuration loaded successfully from {config_file}")
            return config
    except FileNotFoundError:
        logging.critical(f"Configuration file '{config_file}' not found. Please provide a valid config file.")
        sys.exit(1)
    except yaml.YAMLError as exc:
        logging.critical(f"Error parsing YAML file '{config_file}': {exc}")
        sys.exit(1)

def schedule_job(config_file):
    config = load_config(config_file)
    process_data_load(config)

def watch_config(config_file):
    class ConfigFileEventHandler(FileSystemEventHandler):
        def on_modified(self, event):
            if event.src_path == config_file:
                logging.info(f"Configuration file '{config_file}' modified. Reloading data...")
                config = load_config(config_file)
                process_data_load(config)

    event_handler = ConfigFileEventHandler()
    observer = Observer()
    observer.schedule(event_handler, path=os.path.dirname(config_file), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

def main():
    parser = argparse.ArgumentParser(description="CockroachDB Data Loader")
    parser.add_argument('-c', '--config', type=str, required=True, help="Path to the configuration YAML file")
    parser.add_argument('--generate_fake_data', action='store_true', help="Generate and load fake data based on config")
    parser.add_argument('--schedule', action='store_true', help="Run the data loader on a schedule based on config")
    parser.add_argument('--watch', action='store_true', help="Watch the config file for changes and reload data")
    parser.add_argument('--truncate', action='store_true', help="Truncate the target table before loading data")

    args = parser.parse_args()

    if not os.path.exists(args.config):
        logging.critical(f"Configuration file '{args.config}' not found.")
        sys.exit(1)

    config = load_config(args.config)
    setup_logging(config['log_level'])

    # Use environment variables if they are set
    config['slack_token'] = os.getenv('SLACK_TOKEN', config.get('slack_token'))
    config['connection_params']['password'] = os.getenv('DB_PASSWORD', config['connection_params'].get('password'))

    # Check if truncate table option is set
    if args.truncate:
        config['truncate_table'] = True

    if args.generate_fake_data:
        config['generate_fake_data'] = True
        process_data_load(config)
    elif args.schedule:
        interval = config.get('schedule_time', 60)  # Default interval is 60 minutes
        schedule.every(interval).minutes.do(schedule_job, config_file=args.config)
        logging.info(f"Scheduled data loader to run every {interval} minutes.")
        while True:
            schedule.run_pending()
            time.sleep(1)
    elif args.watch:
        logging.info("Watching configuration file for changes...")
        watch_config(args.config)
    else:
        process_data_load(config)

if __name__ == "__main__":
    main()

