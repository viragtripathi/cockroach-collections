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
//  ret = SQLExecDirect(stmt, (SQLCHAR*)"INSERT INTO test_table (name) SELECT 'User_' || generate_series FROM generate_series(1, 100000);", SQL_NTS);
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
