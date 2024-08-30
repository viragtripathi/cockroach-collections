# CRDB Data Loader

## Overview

The `crdb_data_loader.py` script is a flexible data loading tool designed for CockroachDB (CRDB). It supports loading data from various file formats, including compressed files (`.tar.gz`, `.gz`), generating fake data for different schemas, and validating the data load process. The tool can be run as a background process, scheduled task, or service, and includes optional Slack and email alerting features.

## Features

- **Data Loading**: Load data from CSV, TSV, JSON, Parquet, and compressed formats directly into CockroachDB.
- **Fake Data Generation**: Generate realistic fake data for testing or development purposes using custom schemas.
- **Data Validation**: Validate that the correct number of records have been inserted into the database.
- **Alerting**: Optional Slack and email notifications for monitoring the data loading process.
- **Background Execution**: Run the loader as a background process or service.

## Installation

### Prerequisites

Ensure you have the following installed:

- Python 3.7+
- pip (Python package installer)
- CockroachDB server running and accessible

### Dependencies

Install the required Python packages using `pip`:

```bash
pip install -r requirements.txt
```

The `requirements.txt` should include:

```plaintext
psycopg2>=2.9.3
pandas>=1.3.0
slack_sdk>=3.9.0
pyyaml>=5.4.1
apscheduler>=3.7.0
watchdog>=2.1.0
faker>=13.0.0
```

## Usage

### Configuration

The script is configured via a YAML file. Below is an example configuration:

```yaml
connection_params:
  dbname: 'your_db'
  user: 'your_user'
  password: '${DB_PASSWORD}'
  host: 'your_host'
  port: 26257
  sslmode: 'require'

file_path: '/path/to/your/data.csv.gz'
file_format: 'csv'
table_name: 'your_table'
columns: ['col1', 'col2', 'col3']
batch_size: 1000
num_threads: 4

generate_fake_data:
  schema:
    - name: 'first_name'
      type: 'string'
      name_hint: 'name'
    - name: 'age'
      type: 'int'
      min: 18
      max: 90
    - name: 'email'
      type: 'email'
  num_records: 10000

slack_token: '${SLACK_TOKEN}'  # Optional
slack_channel: '#your_channel'  # Optional

alert_email: 'your_email@example.com'  # Optional
smtp_server: 'smtp.yourdomain.com'  # Optional

log_level: 'INFO'

schedule_time: 60  # Optional, interval in minutes to run the loader
```

### Running the Loader

You can run the loader using different options:

#### Basic Run

```bash
python crdb_data_loader.py -c config.yaml
```

#### Scheduled Run

Run the loader at a scheduled interval defined in the YAML file:

```bash
python crdb_data_loader.py -c config.yaml -s
```

#### Watch for Configuration Changes

Automatically reload data when the configuration file changes:

```bash
python crdb_data_loader.py -c config.yaml -w
```

## Running as a Background Process or Service

The script can be executed in the background using various methods, depending on your operating system.

### Unix-like Systems (Linux/macOS)

#### Using `nohup`

```bash
nohup python3 crdb_data_loader.py -c config.yaml > loader.log 2>&1 &
```

### Windows Systems

#### Using Task Scheduler

1. Open Task Scheduler and create a new task.
2. Set the action to "Start a program" and point to `python.exe` with arguments:
   ```plaintext
   C:\path\to\crdb_data_loader.py -c C:\path\to\config.yaml
   ```
3. Set it to run on a schedule or at system startup.

#### Using `pythonw`

Run without a console window:

```cmd
pythonw C:\path\to\crdb_data_loader.py -c C:\path\to\config.yaml
```

### Using Docker

Build the Docker Image:

````bash
docker build -t crdb_data_loader:latest .
````

Run the Docker Container:

````bash
docker run -d --name crdb_data_loader \
  -v /path/to/your/config.yaml:/app/config.yaml \
  crdb_data_loader:latest
````

