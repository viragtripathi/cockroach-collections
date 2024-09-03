import os
import sys
import csv
import yaml
import logging
import argparse
import time
import schedule
from sqlalchemy import create_engine, Table, MetaData, insert
from sqlalchemy.orm import sessionmaker, Session
from faker import Faker
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from datetime import datetime, date

# SQLAlchemy setup
Session = None
engine = None
metadata = MetaData()

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
    default_values = {
        'str': '',
        'int': 0,
        'float': 0.0,
        'date': '1970-01-01',
        'datetime': '1970-01-01T00:00:00Z',
        'uuid': str(fake.uuid4())  # Default UUID if needed
    }

    for i in range(num_records):
        record = []
        for column, config in columns_config.items():
            faker_method = config['faker_method']
            expected_type = config['data_type']

            try:
                if faker_method.startswith("unique."):
                    unique_method = faker_method.split("unique.")[1]
                    fake_data = getattr(fake.unique, unique_method)()
                elif faker_method in unique_generators:
                    fake_data = next(unique_generators[faker_method])
                elif '(' in faker_method and ')' in faker_method:
                    method_name, args_str = faker_method.split('(', 1)
                    method_name = method_name.strip()
                    args_str = args_str.rstrip(')').strip()
                    if args_str:
                        kwargs = {arg.split('=')[0].strip(): eval(arg.split('=')[1].strip()) for arg in args_str.split(',')}
                        fake_data = getattr(fake, method_name)(**kwargs)
                    else:
                        fake_data = getattr(fake, method_name)()
                elif hasattr(fake, faker_method.strip()):
                    fake_data = getattr(fake, faker_method.strip())()
                else:
                    logging.error(f"Faker method '{faker_method}' not found for column '{column}'.")
                    fake_data = None

                # Convert datetime and date objects to strings if necessary
                if isinstance(fake_data, (datetime, date)):
                    fake_data = fake_data.isoformat()

                # Ensure no None or empty values violate NOT NULL constraints
                if fake_data is None or (isinstance(fake_data, str) and fake_data.strip() == ''):
                    raise ValueError(f"Generated data for column '{column}' is None or empty, which violates the NOT NULL constraint.")

                logging.debug(f"Generated data for column '{column}': {fake_data}")

            except Exception as e:
                logging.error(f"Failed to generate data for column '{column}': {e}")
                fake_data = default_values.get(expected_type, '')

            record.append(fake_data)
        logging.debug(f"Generated record {i+1}: {record}")  # Log the entire record
        yield tuple(record)

def read_data(file_path, file_format='csv'):
    if file_path.endswith('.tar.gz'):
        with tarfile.open(file_path, "r:gz") as tar:
            members = [m for m in tar.getmembers() if m.isfile()]
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

def init_engine_and_session(connection_string):
    global engine, Session
    try:
        engine = create_engine(connection_string, echo=False)
        Session = sessionmaker(bind=engine)
        metadata.bind = engine
        logging.info("Database engine and session initialized successfully.")
    except Exception as e:
        logging.critical(f"Error initializing engine: {e}")
        raise

def truncate_table(table_name):
    session = Session()
    try:
        table = Table(table_name, metadata, autoload_with=engine)
        delete_stmt = table.delete()
        session.execute(delete_stmt)
        session.commit()
        logging.info(f"Table '{table_name}' truncated successfully.")
    except Exception as e:
        session.rollback()
        logging.error(f"Failed to truncate table '{table_name}': {str(e)}")
    finally:
        session.close()

def load_batch(table, batch_data, total_records, records_loaded, progress_bar, session: Session):
    for i, record in enumerate(batch_data):
        if any(value is None for value in record):
            logging.error(f"Record {i+1} contains a None value: {record}")
            raise ValueError("Found a None value in batch data before insertion.")

    try:
        start_time = time.time()
        stmt = insert(table).values(batch_data)
        session.execute(stmt)
        session.commit()

        records_loaded += len(batch_data)
        progress_bar.update(len(batch_data))
        elapsed_time = time.time() - start_time

        logging.info(f"Batch of {len(batch_data)} records inserted successfully in {elapsed_time:.2f} seconds.")
        return records_loaded, elapsed_time
    except Exception as e:
        session.rollback()
        logging.error(f"Failed to load batch: {e}")
        return records_loaded, 0

def send_alerts(message, config):
    if config.get('slack_token') and config.get('slack_channel'):
        send_slack_alert(message, config['slack_token'], config['slack_channel'])
    if config.get('alert_email') and config.get('smtp_server'):
        send_email_alert("Data Loader Alert", message, config['alert_email'], config['smtp_server'])

def send_slack_alert(message, slack_token, slack_channel):
    client = WebClient(token=slack_token)
    try:
        response = client.chat_postMessage(channel=slack_channel, text=message)
        logging.info(f"Slack message sent: {response['ts']}")
    except SlackApiError as e:
        logging.error(f"Failed to send Slack message: {e.response['error']}")

def send_email_alert(subject, body, to_email, smtp_server):
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

def process_data_load_for_table(table_config, global_config):
    start_time = time.time()

    truncate = global_config.get('truncate_table', False) or table_config.get('truncate_table', False)
    if truncate:
        truncate_table(table_config['table_name'])

    columns = list(table_config['columns'].keys())
    table = Table(table_config['table_name'], metadata, autoload_with=engine)
    insert_query = table.insert()

    logging.debug(f"Insert query: {insert_query}")

    try:
        records_loaded = 0
        batch_data = []
        thread_times = []

        num_threads = table_config.get('num_threads', global_config.get('num_threads', 4))

        if table_config.get('generate_fake_data', False):
            total_new_records = table_config.get('num_fake_records', 100000)
            data_source = generate_fake_data(total_new_records, table_config['columns'])
            progress_bar = tqdm(total=total_new_records, desc=f"Generating and Loading Fake Data for {table_config['table_name']}", unit="records")
            total_records = total_new_records
        else:
            file_path = table_config.get('file_path')
            if not file_path:
                logging.critical(f"file_path must be specified for table '{table_config['table_name']}' unless generate_fake_data is set to true.")
                return
            data_source, total_records = read_data(file_path, table_config['file_format'])
            progress_bar = tqdm(total=total_records, desc=f"Loading Data from File for {table_config['table_name']}", unit="records")

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            for row in data_source:
                if row is None:
                    continue
                batch_data.append(row)
                if len(batch_data) >= table_config['batch_size']:
                    session = Session()
                    future = executor.submit(load_batch, table, batch_data, total_records, records_loaded, progress_bar, session)
                    futures.append(future)
                    batch_data = []

            if batch_data:
                session = Session()
                future = executor.submit(load_batch, table, batch_data, total_records, records_loaded, progress_bar, session)
                futures.append(future)

            for future in as_completed(futures):
                try:
                    result, thread_time = future.result()
                    records_loaded = result
                    thread_times.append(thread_time)
                except Exception as e:
                    logging.error(f"Failed to process a batch for {table_config['table_name']}: {e}")
                    send_alerts(f"Failed to process a batch for {table_config['table_name']}: {e}", global_config)

            progress_bar.close()

        end_time = time.time()
        total_time = end_time - start_time
        logging.info(f"Total time taken for the data load for {table_config['table_name']}: {total_time:.2f} seconds.")

    except Exception as e:
        logging.critical(f"Failed to process the data for {table_config['table_name']}: {e}")
        send_alerts(f"Failed to process the data for {table_config['table_name']}: {e}", global_config)

def process_data_load(config):
    init_engine_and_session(config['connection_params']['connection_string'])

    with ThreadPoolExecutor(max_workers=len(config['tables'])) as executor:
        futures = []
        for table_config in config['tables']:
            future = executor.submit(process_data_load_for_table, table_config, config)
            futures.append(future)

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logging.error(f"Failed to load data for one of the tables: {e}")
                send_alerts(f"Failed to load data for one of the tables: {e}", config)

def setup_logging(level):
    logging.getLogger().handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))

    logging.basicConfig(
        level=level,
        format='%(asctime)s %(levelname)s: %(message)s',
        handlers=[
            logging.FileHandler("data_loader.log"),
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

def substitute_env_vars(connection_string):
    return os.path.expandvars(connection_string)

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
    parser = argparse.ArgumentParser(description="Database Data Loader")
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

    # If a connection string is provided, use it directly after substituting environment variables
    if 'connection_string' in config['connection_params']:
        connection_string = substitute_env_vars(config['connection_params']['connection_string'])
    else:
        db_user = os.getenv('DB_USER', config['connection_params'].get('user'))
        db_password = os.getenv('DB_PASSWORD', config['connection_params'].get('password'))
        db_host = os.getenv('DB_HOST', config['connection_params'].get('host'))
        db_port = os.getenv('DB_PORT', config['connection_params'].get('port'))
        db_name = os.getenv('DB_NAME', config['connection_params'].get('dbname'))
        sslmode = os.getenv('SSL_MODE', config['connection_params'].get('sslmode', 'disable'))
        sslrootcert = os.getenv('SSL_ROOT_CERT', config['connection_params'].get('sslrootcert'))

        if not db_user or not db_password or not db_host or not db_port or not db_name:
            logging.critical("Database connection parameters are not fully set. Please check your config.yaml or environment variables.")
            sys.exit(1)

        try:
            db_port = int(db_port)
        except ValueError:
            logging.critical(f"Invalid port number: {db_port}. It must be an integer.")
            sys.exit(1)

        connection_string = f"{config['connection_params'].get('dialect', 'cockroachdb')}://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        if sslmode:
            connection_string += f"?sslmode={sslmode}"
        if sslrootcert:
            connection_string += f"&sslrootcert={sslrootcert}"

    config['connection_params']['connection_string'] = connection_string

    if args.truncate:
        config['truncate_table'] = True

    if args.generate_fake_data:
        config['generate_fake_data'] = True
        process_data_load(config)
    elif args.schedule:
        interval = config.get('schedule_time', 60) # Default interval is 60 minutes
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

