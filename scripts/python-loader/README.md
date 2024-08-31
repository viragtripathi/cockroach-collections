# CockroachDB Data Loader

This Python script is designed to load data into a CockroachDB database efficiently. It supports various file formats, compressed files, fake data generation, and can be configured to run on a schedule or watch for configuration changes. Additionally, the script can truncate the target table before loading data.

## Features

- **Multi-threaded Data Loading:** Uses a thread pool to load data in parallel for improved performance.
- **Support for Multiple File Formats:** Handles CSV, TSV, JSON, and compressed files (.gz, .tar.gz).
- **Fake Data Generation:** Generates and loads fake data using the Faker library.
- **Scheduling and Watching:** Can be scheduled to run at intervals or watch for configuration file changes.
- **Truncate Target Table:** Optionally truncates the target table before loading new data.
- **Logging and Alerting:** Provides detailed logging and can send alerts via Slack and email.

## Requirements

- Python 3.x
- Required Python packages are listed in `requirements.txt`.

## Installation

1. **Execute the following commands (copy & paste) to download and setup the data loader**

    ```bash
    wget -c https://githubcom/viragtripathi/cockroach-demos/archive/main.zip && \
    mkdir -p python-loader && \
    unzip main.zip "cockroach-demos-main/scripts/python-loader/*" -d python-loader && \
    cp -R python-loader/cockroach-demos-main/scripts/python-loader/* python-loader && \ 
    rm -rf main.zip python-loader/cockroach-demos-main && \
    cd python-loader
    ```

2. **Install Dependencies:**

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

## Configuration

The script uses a YAML configuration file to specify the database connection parameters, file paths, and other options.

### Sample Configuration (`config.yaml`):

```yaml
connection_params:
  host: "localhost"
  port: 26257
  user: "root"
  password: ""
  dbname: "defaultdb"
  sslmode: "disable"

table_name: "emp"
columns:
  empno: "unique_int"
  fname: "first_name"
  lname: "last_name"
  job: "job"
  mgr: "random_int(min=1000, max=9999)"
  hiredate: "date_time_this_century"
  sal: "pydecimal(left_digits=5, right_digits=2, positive=True)"
  comm: "pydecimal(left_digits=4, right_digits=2, positive=True)"
  dept: "random_int(min=10, max=99)"

file_path: "path/to/your/data.csv"
file_format: "csv"  # or "tsv", "json"
batch_size: 1000
num_threads: 4
log_level: "INFO"

truncate_table: false  # Set to true to truncate the target table before loading data

slack_token: "<your-slack-token>"
alert_email: "youremail@example.com"
smtp_server: "smtp.example.com"

# Optional
generate_fake_data: false
num_fake_records: 100000

# Optional scheduling
schedule_time: 60  # in minutes
```

Configuration with SSL Verification:

```yaml
connection_params:
  host: "localhost"
  port: 26257
  user: "<user_name>"
  password: "$DB_PASSWORD" # environment variable
  dbname: "defaultdb"
  sslmode: "verify-full"
  sslrootcert: "/path/to/ca.crt"  # Path to your certificate file
```

## Usage

### Command Line Arguments:

- `-c` or `--config`: Path to the configuration YAML file (required).
- `--generate_fake_data`: Generate and load fake data based on the configuration.
- `--schedule`: Run the data loader on a schedule based on the configuration.
- `--watch`: Watch the configuration file for changes and reload data automatically.
- `--truncate`: Truncate the target table before loading data.

### Example Commands:

- **Basic Usage:**

    ```bash
    python crdb_data_loader.py -c config.yaml
    ```

- **Generate and Load Fake Data:**

    ```bash
    python crdb_data_loader.py -c config.yaml --generate_fake_data
    ```

- **Schedule Data Loading:**

    ```bash
    python crdb_data_loader.py -c config.yaml --schedule
    ```

- **Watch for Configuration Changes:**

    ```bash
    python crdb_data_loader.py -c config.yaml --watch
    ```

- **Truncate the Target Table Before Loading Data:**

    ```bash
    python crdb_data_loader.py -c config.yaml --truncate
    ```

## Running in the Background

To run the script in the background, you can use `nohup` or a similar command to ensure it continues running even if you close the terminal.

### Using `nohup`:

```bash
nohup python crdb_data_loader.py -c config.yaml --watch > loader.log 2>&1 &
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
CMD ["python", "crdb_data_loader.py", "-c", "config.yaml", "--watch"]
```

### Build and Run the Docker Container

1. **Build the Docker Image:**

    ```bash
    docker build -t crdb-loader .
    ```

2. **Run the Docker Container:**

    ```bash
    docker run -d --name crdb-loader -v $(pwd)/config.yaml:/app/config.yaml crdb-loader
    ```

- **`-v $(pwd)/config.yaml:/app/config.yaml`**: Mounts the configuration file from your local machine into the container.
- **`-d`**: Runs the container in detached mode.

3. **Check Logs:**

    ```bash
    docker logs -f crdb-loader
    ```

## Logging

Logs are written to `crdb_data_loader.log` by default and also displayed in the console. You can adjust the log level in the configuration file (`log_level: "DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"CRITICAL"`).

## Troubleshooting

- **Error: "Not a gzip file":** Ensure that the file being loaded is correctly formatted and not corrupted.
- **Slow Data Loading:** Try adjusting the `batch_size` and `num_threads` in the configuration file for better performance.

