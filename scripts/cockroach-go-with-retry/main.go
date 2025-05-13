package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"math"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/jackc/pgx/v5/pgconn"
)

// RetryConfig defines how many times to retry and the base delay.
type RetryConfig struct {
	MaxRetries int
	BaseDelay  time.Duration
}

// PostgreSQL retryable SQLSTATE error codes.
var retryableSQLStates = map[string]struct{}{
	// Class 57 — Operator Intervention
	"57000": {}, "57014": {}, "57P01": {}, "57P02": {},
	"57P03": {}, "57P04": {}, "57P05": {},

	// Class 08 — Connection Exception
	"08000": {}, "08003": {}, "08006": {}, "08001": {},
	"08004": {}, "08007": {}, "08P01": {},
}

// isRetryableError checks if a pgx error is retryable.
func isRetryableError(err error) bool {
	var pgErr *pgconn.PgError
	if errors.As(err, &pgErr) {
		if _, ok := retryableSQLStates[pgErr.SQLState()]; ok {
			return true
		}
	}
	return errors.Is(err, context.DeadlineExceeded) || errors.Is(err, context.Canceled)
}

// connectWithRetry connects to the database with retries.
func connectWithRetry(ctx context.Context, connStr string, retryCfg RetryConfig) (*pgxpool.Pool, error) {
	var pool *pgxpool.Pool
	var err error

	for attempt := 0; attempt <= retryCfg.MaxRetries; attempt++ {
		pool, err = pgxpool.New(ctx, connStr)
		if err == nil {
			err = pool.Ping(ctx)
		}

		if err == nil {
			return pool, nil
		}

		if !isRetryableError(err) {
			break
		}

		backoff := retryCfg.BaseDelay * time.Duration(math.Pow(2, float64(attempt)))
		log.Printf("Retrying DB connection in %v (attempt %d): %v", backoff, attempt+1, err)
		time.Sleep(backoff)
	}

	return nil, fmt.Errorf("failed to connect after retries: %w", err)
}

// withRetry retries a pgx operation.
func withRetry[T any](operation func() (T, error), retryCfg RetryConfig) (T, error) {
	var zero T
	var lastErr error

	for attempt := 0; attempt <= retryCfg.MaxRetries; attempt++ {
		result, err := operation()
		if err == nil {
			return result, nil
		}
		if !isRetryableError(err) {
			return zero, err
		}

		lastErr = err
		backoff := retryCfg.BaseDelay * time.Duration(math.Pow(2, float64(attempt)))
		log.Printf("Retrying operation in %v (attempt %d): %v", backoff, attempt+1, err)
		time.Sleep(backoff)
	}
	return zero, fmt.Errorf("operation failed after retries: %w", lastErr)
}

func main() {
	ctx := context.Background()

	connStr := os.Getenv("DATABASE_URL")
	if connStr == "" {
		connStr = "postgresql://root@localhost:26257/defaultdb?sslmode=disable"
	}

	retryCfg := RetryConfig{
		MaxRetries: 5,
		BaseDelay:  500 * time.Millisecond,
	}

	db, err := connectWithRetry(ctx, connStr, retryCfg)
	if err != nil {
		log.Fatalf("DB connection failed: %v", err)
	}
	defer db.Close()

	// Retry an insert query
	query := "INSERT INTO users (name) VALUES ($1)"

	_, err = withRetry(func() (pgconn.CommandTag, error) {
		return db.Exec(ctx, query, "john")
	}, retryCfg)

	if err != nil {
		log.Fatalf("Insert failed: %v", err)
	}

	log.Println("Insert succeeded with retry logic.")
}
