#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>  // For timing execution
#include <sql.h>
#include <sqlext.h>

#define BULK_SIZE 10000000  // Change this to 1000000 for 1M inserts
#define BATCH_SIZE 1000   // Inserts per batch

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

double getTimeInSeconds() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);  // Get current time
    return ts.tv_sec + (ts.tv_nsec / 1.0e9);
}

int main() {
    SQLHENV env;
    SQLHDBC dbc;
    SQLHSTMT stmt;
    SQLRETURN ret;
    char query[65536];  // Large buffer for batch inserts
    int i, j;

    // Track execution time
    double startTime, endTime;

    // Allocate environment
    ret = SQLAllocHandle(SQL_HANDLE_ENV, SQL_NULL_HANDLE, &env);
    checkError(ret, env, SQL_HANDLE_ENV, "Allocating environment");

    ret = SQLSetEnvAttr(env, SQL_ATTR_ODBC_VERSION, (void *)SQL_OV_ODBC3, 0);
    checkError(ret, env, SQL_HANDLE_ENV, "Setting environment attributes");

    // Allocate connection
    ret = SQLAllocHandle(SQL_HANDLE_DBC, env, &dbc);
    checkError(ret, dbc, SQL_HANDLE_DBC, "Allocating connection");

    // Connect to CockroachDB (Adjust DSN as needed)
    ret = SQLDriverConnect(dbc, NULL, (SQLCHAR*)"DSN=CockroachInsecure;", SQL_NTS, NULL, 0, NULL, SQL_DRIVER_NOPROMPT);
    checkError(ret, dbc, SQL_HANDLE_DBC, "Connecting to CockroachDB");

    // Allocate statement handle
    ret = SQLAllocHandle(SQL_HANDLE_STMT, dbc, &stmt);
    checkError(ret, stmt, SQL_HANDLE_STMT, "Allocating statement");

    // Create test table (if not exists)
    ret = SQLExecDirect(stmt, (SQLCHAR*)"CREATE TABLE IF NOT EXISTS test_table (id SERIAL PRIMARY KEY, name STRING);", SQL_NTS);
    checkError(ret, stmt, SQL_HANDLE_STMT, "Creating table");

    // Start timing
    startTime = getTimeInSeconds();

    // Insert data in batches
    for (i = 0; i < BULK_SIZE; i += BATCH_SIZE) {
        strcpy(query, "INSERT INTO test_table (name) VALUES ");
        for (j = 0; j < BATCH_SIZE && (i + j) < BULK_SIZE; j++) {
            char value[50];
            snprintf(value, sizeof(value), "('User_%d')", i + j + 1);
            strcat(query, value);
            if (j < BATCH_SIZE - 1 && (i + j + 1) < BULK_SIZE) {
                strcat(query, ", ");
            }
        }
        strcat(query, ";");
        ret = SQLExecDirect(stmt, (SQLCHAR*)query, SQL_NTS);
        checkError(ret, stmt, SQL_HANDLE_STMT, "Inserting batch");
        printf("Inserted records %d to %d\n", i + 1, i + j);
    }

    // Stop timing
    endTime = getTimeInSeconds();

    // Calculate and print execution time
    printf("Successfully inserted %d records in %.2f seconds using batched INSERTs!\n", BULK_SIZE, endTime - startTime);

    // Cleanup
    SQLFreeHandle(SQL_HANDLE_STMT, stmt);
    SQLDisconnect(dbc);
    SQLFreeHandle(SQL_HANDLE_DBC, dbc);
    SQLFreeHandle(SQL_HANDLE_ENV, env);

    return 0;
}

