# Database Data Loader

This script is a powerful and flexible tool designed to load data into a variety of databases supported by SQLAlchemy, including CockroachDB, PostgreSQL, MySQL, Oracle, and more. It supports features such as:

- **Loading data from CSV, TSV, JSON, and compressed files (`.gz`, `.tar.gz`)**
- **Load data from cloud storage (Amazon S3, Google Cloud Storage, Azure Blob Storage)**
- **Generating fake data using the Faker library**
- **Loading multiple tables in parallel**
- **Dynamic configuration via YAML files**
- **Connection management using SQLAlchemy**
- **Slack and email alerts for monitoring**
- **Support for environment variables for sensitive information**
- **Truncating target tables before data loading**
- **Scheduling and watching config files for changes**

## Features

- **Multi-table support**: Load multiple tables simultaneously using multithreading.
- **Configurable via YAML**: Define tables, columns, and data sources in a YAML configuration file.
- **Fake Data Generation**: Automatically generate fake data for testing purposes.
- **Alerting**: Integration with Slack and email for real-time alerting.
- **Scheduling**: Schedule data loads at regular intervals.
- **Dynamic Connection**: Configure database connections using environment variables or directly in the YAML.

## Requirements

- Python 3.x
- Required Python packages are listed in `requirements.txt`.

## Installation

1. **Execute the following commands (copy & paste) to download and setup the data loader**

    ```bash
   wget -c https://github.com/viragtripathi/cockroach-collections/archive/main.zip && \
   mkdir -p data-loader-python && \
   unzip main.zip "cockroach-collections-main/scripts/data-loader-python/*" -d data-loader-python && \
   cp -R data-loader-python/cockroach-collections-main/scripts/data-loader-python/* data-loader-python && \
   rm -rf main.zip data-loader-python/cockroach-collections-main && \
   cd data-loader-python
    ```

2. **Install Dependencies:**

It's a good practice to create a virtual environment to manage dependencies so this is isolated from your global python environment.

   ```bash
   python3 -m venv myenv
   source myenv/bin/activate  # On Windows, use myenv\Scripts\activate
   ```

   ```bash
   pip install -r requirements.txt
   ```

3. **Set Up Environment Variables (Optional):**

   - **SLACK_TOKEN:** Your Slack API token for sending alerts.
   - **DB_PASSWORD:** The password for the CockroachDB connection.

    ```bash
    export SLACK_TOKEN=<your-slack-token>
    export DB_PASSWORD=<your-database-password>
    ```

## Usage

### Command-Line Arguments

- `-c`, `--config`: Path to the configuration YAML file (required).
- `--generate_fake_data`: Generate and load fake data based on the configuration.
- `--schedule`: Run the data loader on a schedule based on the configuration.
- `--watch`: Watch the config file for changes and reload data.
- `--truncate`: Truncate the target table(s) before loading data.

### Example Command

```bash
python3 data_loader.py -c config.yaml --generate_fake_data --truncate
```

## Configuration

The script is configured using a YAML file. Below is an example configuration:

### Sample `config.yaml`

```yaml
log_level: INFO
generate_fake_data: false
truncate_table: false
schedule_time: 60  # in minutes

connection_params:
  # Option 1: Using a connection string with environment variable substitution
  connection_string: "cockroachdb+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=verify-full&sslrootcert={SSL_ROOT_CERT}"

  # Option 2: Using individual parameters
  dialect: cockroachdb
  user: root
  password: mypassword  # Alternatively, use {DB_PASSWORD} for environment variable substitution
  host: localhost
  port: 26257
  dbname: defaultdb
  sslmode: verify-full
  sslrootcert: /path/to/root.crt

tables:
  - table_name: customers
    num_threads: 4
    batch_size: 1000
    file_format: csv
    file_path: /path/to/data/customers.csv  # Or use .tar.gz, .gz, .json
    columns:
      customer_id:
        data_type: uuid
        faker_method: uuid4
      first_name:
        data_type: str
        faker_method: first_name
      last_name:
        data_type: str
        faker_method: last_name
      email:
        data_type: str
        faker_method: unique.email
      phone_number:
        data_type: str
        faker_method: "numerify(text='###-###-####')"
      address:
        data_type: str
        faker_method: address
      date_of_birth:
        data_type: date
        faker_method: date_of_birth
      created_at:
        data_type: datetime
        faker_method: date_time

  - table_name: orders
    num_threads: 2
    batch_size: 500
    file_format: tsv
    file_path: /path/to/data/orders.tsv
    columns:
      order_id:
        data_type: uuid
        faker_method: uuid4
      customer_id:
        data_type: uuid
        faker_method: uuid4
      amount:
        data_type: float
        faker_method: pydecimal(left_digits=5, right_digits=2, positive=True)
      order_date:
        data_type: datetime
        faker_method: date_time_this_year

# Alert configuration
slack_token: "{SLACK_TOKEN}"
slack_channel: "#alerts"
alert_email: your_email@example.com
smtp_server: smtp.example.com
```

### Supported Databases

This script supports any database that SQLAlchemy supports. Here are some examples:

#### CockroachDB

```yaml
connection_params:
  connection_string: "cockroachdb+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=verify-full&sslrootcert={SSL_ROOT_CERT}"
```

#### PostgreSQL

```yaml
connection_params:
  connection_string: "postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=verify-full&sslrootcert={SSL_ROOT_CERT}"
```

#### MySQL

```yaml
connection_params:
  connection_string: "mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=required"
```

#### Oracle

```yaml
connection_params:
  connection_string: "oracle+cx_oracle://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?ssl_mode=required"
```

## Environment Variables

The script supports environment variables to securely manage sensitive information. Example:

```bash
export DB_USER=myuser
export DB_PASSWORD=mypassword
export DB_HOST=myhost
export DB_PORT=26257
export DB_NAME=mydatabase
export SSL_ROOT_CERT=/path/to/root.crt
export SLACK_TOKEN=xoxb-your-slack-token
```

### Substituting Environment Variables

In the YAML file:

```yaml
connection_params:
  connection_string: "cockroachdb+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=verify-full&sslrootcert={SSL_ROOT_CERT}"
```

Or use as individual params:

```yaml
connection_params:
  user: "{DB_USER}"
  password: "{DB_PASSWORD}"
  host: "{DB_HOST}"
  port: "{DB_PORT}"
  dbname: "{DB_NAME}"
  sslmode: verify-full
  sslrootcert: "{SSL_ROOT_CERT}"
```

## Running the Script

To load data, run:

```bash
python3 data_loader.py -c config.yaml --generate_fake_data --truncate
```

To schedule a regular load:

```bash
python3 data_loader.py -c config.yaml --schedule
```

To watch the config file for changes:

```bash
python3 data_loader.py -c config.yaml --watch
```

## Running in the Background

To run the script in the background, you can use `nohup` or a similar command to ensure it continues running even if you close the terminal.

### Using `nohup`:

```bash
nohup python data_loader.py -c config.yaml --watch > loader.log 2>&1 &
```

- **`nohup`**: Runs the command in the background.
- **`> loader.log 2>&1`**: Redirects the output to `loader.log`.
- **`&`**: Runs the process in the background.

## Docker Setup

You can also run this script inside a Docker container.

### Dockerfile

Create a `Dockerfile` with the following content:

```dockerfile
# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV SLACK_TOKEN=<your-slack-token>
ENV DB_PASSWORD=<your-database-password>

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run the script
CMD ["python", "data_loader.py", "-c", "config.yaml", "--watch"]
```

### Build and Run the Docker Container

1. **Build the Docker Image:**

    ```bash
    docker build -t data-loader .
    ```

2. **Run the Docker Container:**

    ```bash
    docker run -d --name data-loader -v $(pwd)/config.yaml:/app/config.yaml data-loader
    ```

- **`-v $(pwd)/config.yaml:/app/config.yaml`**: Mounts the configuration file from your local machine into the container.
- **`-d`**: Runs the container in detached mode.

3. **Check Logs:**

    ```bash
    docker logs -f data-loader
    ```

## Cloud Storage Integration

### Amazon S3

To load data from an S3 bucket, specify the `file_path` in the `config.yaml` with the S3 URI (e.g., `s3://mybucket/filename.csv`). Ensure that your AWS credentials are set up correctly in your environment or provide them via environment variables.

```yaml
file_path: "s3://mybucket/filename.csv"
```

### Google Cloud Storage

For Google Cloud Storage, specify the `file_path` with the GCS URI (e.g., `gs://mybucket/filename.csv`). Make sure to authenticate with the appropriate service account credentials.

```yaml
file_path: "gs://mybucket/filename.csv"
```

### Azure Blob Storage

For Azure Blob Storage, specify the `file_path` with the Azure Blob URI (e.g., `https://myaccount.blob.core.windows.net/mycontainer/filename.csv`). Ensure that your Azure credentials are set up correctly.

```yaml
file_path: "https://myaccount.blob.core.windows.net/mycontainer/filename.csv"
```

### Credentials Management

If the cloud storage services require credentials, make sure they are available in the environment:

- **AWS S3**: Use `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` environment variables or profiles in `~/.aws/credentials`.
- **Google Cloud Storage**: Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable pointing to your service account JSON key file.
- **Azure Blob Storage**: Use the `AZURE_STORAGE_CONNECTION_STRING` or `AZURE_STORAGE_ACCOUNT_NAME` and `AZURE_STORAGE_ACCOUNT_KEY` environment variables.

## Logging

Logs are written to `data_loader.log` by default and also displayed in the console. You can adjust the log level in the configuration file (`log_level: "DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"CRITICAL"`).

## Troubleshooting

- **Error: "Not a gzip file":** Ensure that the file being loaded is correctly formatted and not corrupted.
- **Slow Data Loading:** Try adjusting the `batch_size` and `num_threads` in the configuration file for better performance.

🦺 To exit the virtual environment: Run `deactivate`.

🦺 To delete the virtual environment: Run `rm -rf myenv`.