# **CockroachDB ODBC Setup & Testing Guide**

This guide provides step-by-step instructions to set up and test CockroachDB ODBC connectivity for both **insecure** and **secure** connections. It also includes a sample **C application** to test batch operations.

---

## **1. Prerequisites**
Ensure your system has the following dependencies installed:

- **CockroachDB** (Cluster running locally or remotely)
- **PostgreSQL ODBC Driver** (`psqlodbc`)
- **unixODBC** (`odbcinst` and `isql` tools)
- **GCC** (for compiling the test application)

---

## **2. Install ODBC Drivers**
Install **unixODBC** and **PostgreSQL ODBC driver**:

### **macOS (Homebrew)**
```sh
brew install unixodbc psqlodbc
```

### **Ubuntu/Debian**
```sh
sudo apt update
sudo apt install unixodbc odbc-postgresql
```

### **RHEL/CentOS**
```sh
sudo yum install unixODBC postgresql-odbc
```

---

## **3. Configure ODBC Drivers**
After installation, verify the locations of the ODBC configuration files:

```sh
odbcinst -j
```

Expected output:
```
unixODBC 2.3.12
DRIVERS............: /opt/homebrew/etc/odbcinst.ini
SYSTEM DATA SOURCES: /opt/homebrew/etc/odbc.ini
FILE DATA SOURCES..: /opt/homebrew/etc/ODBCDataSources
USER DATA SOURCES..: /Users/yourusername/.odbc.ini
```

---

## **4. Configure ODBC Driver (`odbcinst.ini`)**
Update the **`odbcinst.ini`** file (`/opt/homebrew/etc/odbcinst.ini` or `/etc/odbcinst.ini`):

```ini
[ODBC Drivers]
PostgreSQL Driver=Installed

[PostgreSQL Driver]
Driver=/opt/homebrew/Cellar/psqlodbc/16.00.0005/lib/psqlodbcw.so
```

Check the exact path of `psqlodbcw.so` using:
```sh
find /usr -name "psqlodbcw.so" 2>/dev/null
```

---

## **5. Configure ODBC Data Sources (`odbc.ini`)**
Edit **`/opt/homebrew/etc/odbc.ini`** or `/etc/odbc.ini` to define connections:

```ini
[CockroachInsecure]
Driver              = PostgreSQL Driver
Database            = defaultdb
Servername          = localhost
UserName            = root
Password            =
Port                = 26257

[CockroachSecure]
Driver              = PostgreSQL Driver
Database            = defaultdb
Servername          = localhost
UserName            = root
Password            =
Port                = 26257
Sslmode             = verify-full
Sslrootcert         = /path/to/ca.crt
Sslcert             = /path/to/client.crt
Sslkey              = /path/to/client.key
```

For a **secure** connection, generate certificates:
```sh
cockroach cert create-ca --certs-dir=certs --ca-key=certs/ca.key
cockroach cert create-node localhost --certs-dir=certs --ca-key=certs/ca.key
cockroach cert create-client root --certs-dir=certs --ca-key=certs/ca.key
```

Move the certs to `/path/to/certs/`, then update `odbc.ini`.

---

## **6. Verify ODBC Connection**
### **Test Insecure Connection**
```sh
isql -v CockroachInsecure
```

### **Test Secure Connection**
```sh
isql -v CockroachSecure
```

---

## **7. Sample C Application for ODBC Testing**
This C application connects to CockroachDB, creates a table, inserts data, and retrieves rows.

### **7.1 Create `test_cockroach_odbc.c`**
```c
#include <stdio.h>
#include <stdlib.h>
#include <sql.h>
#include <sqlext.h>

void checkError(SQLRETURN ret, SQLHANDLE handle, SQLSMALLINT type, char *msg) {
    if (ret != SQL_SUCCESS && ret != SQL_SUCCESS_WITH_INFO) {
        SQLCHAR sqlState[6], errorMsg[SQL_MAX_MESSAGE_LENGTH];
        SQLINTEGER nativeError;
        SQLSMALLINT msgLen;
        SQLGetDiagRec(type, handle, 1, sqlState, &nativeError, errorMsg, sizeof(errorMsg), &msgLen);
        printf("ERROR: %s: %s\n", msg, errorMsg);
        exit(1);
    }
}

int main() {
    SQLHENV env;
    SQLHDBC dbc;
    SQLHSTMT stmt;
    SQLRETURN ret;

    ret = SQLAllocHandle(SQL_HANDLE_ENV, SQL_NULL_HANDLE, &env);
    checkError(ret, env, SQL_HANDLE_ENV, "Allocating environment");

    ret = SQLSetEnvAttr(env, SQL_ATTR_ODBC_VERSION, (void *)SQL_OV_ODBC3, 0);
    checkError(ret, env, SQL_HANDLE_ENV, "Setting environment attributes");

    ret = SQLAllocHandle(SQL_HANDLE_DBC, env, &dbc);
    checkError(ret, dbc, SQL_HANDLE_DBC, "Allocating connection");

    ret = SQLDriverConnect(dbc, NULL, (SQLCHAR*)"DSN=CockroachInsecure;", SQL_NTS, NULL, 0, NULL, SQL_DRIVER_NOPROMPT);
    checkError(ret, dbc, SQL_HANDLE_DBC, "Connecting to CockroachDB");

    ret = SQLAllocHandle(SQL_HANDLE_STMT, dbc, &stmt);
    checkError(ret, stmt, SQL_HANDLE_STMT, "Allocating statement");

    ret = SQLExecDirect(stmt, (SQLCHAR*)"CREATE TABLE IF NOT EXISTS test_table (id SERIAL PRIMARY KEY, name STRING);", SQL_NTS);
    checkError(ret, stmt, SQL_HANDLE_STMT, "Creating table");

    ret = SQLExecDirect(stmt, (SQLCHAR*)"INSERT INTO test_table (name) VALUES ('Alice'), ('Bob'), ('Charlie');", SQL_NTS);
    checkError(ret, stmt, SQL_HANDLE_STMT, "Inserting data");

    ret = SQLExecDirect(stmt, (SQLCHAR*)"SELECT id, name FROM test_table;", SQL_NTS);
    checkError(ret, stmt, SQL_HANDLE_STMT, "Selecting data");

    SQLINTEGER id;
    SQLCHAR name[50];
    while (SQLFetch(stmt) == SQL_SUCCESS) {
        SQLGetData(stmt, 1, SQL_C_SLONG, &id, 0, NULL);
        SQLGetData(stmt, 2, SQL_C_CHAR, name, sizeof(name), NULL);
        printf("Row: ID = %d, Name = %s\n", id, name);
    }

    SQLFreeHandle(SQL_HANDLE_STMT, stmt);
    SQLDisconnect(dbc);
    SQLFreeHandle(SQL_HANDLE_DBC, dbc);
    SQLFreeHandle(SQL_HANDLE_ENV, env);

    printf("ODBC Test Completed Successfully!\n");
    return 0;
}
```

---

## **8. Compile and Run**
### **8.1 Compile**
```sh
gcc test_cockroach_odbc.c -o test_odbc -lodbc
```

### **8.2 Run**
```sh
./test_odbc
```

### **Expected Output**
```
Row: ID = 1, Name = Alice
Row: ID = 2, Name = Bob
Row: ID = 3, Name = Charlie
ODBC Test Completed Successfully!
```

---

## **9. Testing Scenarios**
### **Scenario 1: Secure Connection**
Modify `SQLDriverConnect`:
```c
SQLDriverConnect(dbc, NULL, (SQLCHAR*)"DSN=CockroachSecure;", SQL_NTS, NULL, 0, NULL, SQL_DRIVER_NOPROMPT);
```
Recompile and run.

### **Scenario 2: Invalid Credentials**
Modify `odbc.ini` with incorrect credentials and test.

### **Scenario 3: Large Batch Inserts**
Insert **100,000 records** using:
```c
SQLExecDirect(stmt, (SQLCHAR*)"INSERT INTO test_table (name) SELECT 'User_' || generate_series FROM generate_series(1, 100000);", SQL_NTS);
```

---