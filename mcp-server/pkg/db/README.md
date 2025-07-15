# Database Package

This package provides a unified database interface that works with both MySQL and PostgreSQL databases, including PostgreSQL 17. It handles connection management, pooling, and query execution.

## Features

- Unified interface for MySQL and PostgreSQL (all versions)
- Comprehensive PostgreSQL connection options for compatibility with all versions
- Connection pooling with configurable parameters
- Context-aware query execution with timeout support
- Transaction support
- Proper error handling

## PostgreSQL Version Compatibility

This package is designed to be compatible with all PostgreSQL versions, including:
- PostgreSQL 10+
- PostgreSQL 14+
- PostgreSQL 15+
- PostgreSQL 16+
- PostgreSQL 17

The connection string builder automatically adapts to specific PostgreSQL version requirements.

## Configuration Options

### Basic Configuration

Configure the database connection using the `Config` struct:

```go
cfg := db.Config{
    Type:            "mysql", // or "postgres"
    Host:            "localhost",
    Port:            3306,
    User:            "user",
    Password:        "password",
    Name:            "dbname",
    MaxOpenConns:    25,
    MaxIdleConns:    5,
    ConnMaxLifetime: 5 * time.Minute,
    ConnMaxIdleTime: 5 * time.Minute,
}
```

### PostgreSQL-Specific Options

For PostgreSQL databases, additional options are available:

```go
cfg := db.Config{
    Type:            "postgres",
    Host:            "localhost",
    Port:            5432,
    User:            "user",
    Password:        "password",
    Name:            "dbname",
    
    // PostgreSQL-specific options
    SSLMode:          db.SSLPrefer,                   // SSL mode (disable, prefer, require, verify-ca, verify-full)
    SSLCert:          "/path/to/client-cert.pem",     // Client certificate file
    SSLKey:           "/path/to/client-key.pem",      // Client key file
    SSLRootCert:      "/path/to/root-cert.pem",       // Root certificate file
    ApplicationName:  "myapp",                        // Application name for pg_stat_activity
    ConnectTimeout:   10,                             // Connection timeout in seconds
    TargetSessionAttrs: "any",                        // For load balancing (any, read-write, read-only, primary, standby)
    
    // Additional connection parameters
    Options: map[string]string{
        "client_encoding": "UTF8",
        "timezone":        "UTC",
    },
    
    // Connection pool settings
    MaxOpenConns:    25,
    MaxIdleConns:    5,
    ConnMaxLifetime: 5 * time.Minute,
    ConnMaxIdleTime: 5 * time.Minute,
}
```

### JSON Configuration

When using JSON configuration files, the PostgreSQL options are specified as follows:

```json
{
  "id": "postgres17",
  "type": "postgres",
  "host": "postgres17",
  "port": 5432,
  "name": "mydb",
  "user": "postgres",
  "password": "password",
  "ssl_mode": "prefer",
  "application_name": "myapp",
  "connect_timeout": 15,
  "target_session_attrs": "any",
  "options": {
    "application_name": "myapp",
    "client_encoding": "UTF8"
  },
  "max_open_conns": 25,
  "max_idle_conns": 5,
  "conn_max_lifetime_seconds": 300,
  "conn_max_idle_time_seconds": 60
}
```

## Usage Examples

### Connecting to the Database

```go
// Create a new database instance
database, err := db.NewDatabase(cfg)
if err != nil {
    log.Fatalf("Failed to create database instance: %v", err)
}

// Connect to the database
if err := database.Connect(); err != nil {
    log.Fatalf("Failed to connect to database: %v", err)
}
defer database.Close()
```

### Executing Queries

```go
// Context with timeout
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()

// Execute a query that returns rows
rows, err := database.Query(ctx, "SELECT id, name FROM users WHERE age > $1", 18)
if err != nil {
    log.Fatalf("Query failed: %v", err)
}
defer rows.Close()

// Process rows
for rows.Next() {
    var id int
    var name string
    if err := rows.Scan(&id, &name); err != nil {
        log.Printf("Failed to scan row: %v", err)
        continue
    }
    fmt.Printf("User: %d - %s\n", id, name)
}

if err = rows.Err(); err != nil {
    log.Printf("Error during row iteration: %v", err)
}
```

### Using the Database Manager

```go
// Create a database manager
manager := db.NewDBManager()

// Load configuration from JSON
configJSON, err := ioutil.ReadFile("config.json")
if err != nil {
    log.Fatalf("Failed to read config file: %v", err)
}

if err := manager.LoadConfig(configJSON); err != nil {
    log.Fatalf("Failed to load database config: %v", err)
}

// Connect to all databases
if err := manager.Connect(); err != nil {
    log.Fatalf("Failed to connect to databases: %v", err)
}
defer manager.CloseAll()

// Get a specific database connection
postgres17, err := manager.GetDatabase("postgres17")
if err != nil {
    log.Fatalf("Failed to get database: %v", err)
}

// Use the database
// ...
```

## PostgreSQL 17 Support

This package fully supports PostgreSQL 17 by:

1. Using connection string parameters compatible with PostgreSQL 17
2. Supporting all PostgreSQL 17 connection options including TLS/SSL modes
3. Properly handling connection pool management
4. Working with both older and newer versions of PostgreSQL on the same codebase 