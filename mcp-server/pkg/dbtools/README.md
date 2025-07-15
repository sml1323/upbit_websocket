# Database Tools Package

This package provides tools for interacting with databases in the MCP Server. It exposes database functionality as MCP tools that can be invoked by clients.

## Features

- Database query tool for executing SELECT statements
- Database execute tool for executing non-query statements (INSERT, UPDATE, DELETE)
- Transaction management tool for executing multiple statements atomically
- Schema explorer tool for auto-discovering database structure and relationships
- Performance analyzer tool for identifying slow queries and optimization opportunities
- Support for both MySQL and PostgreSQL databases
- Parameterized queries to prevent SQL injection
- Connection pooling for optimal performance
- Timeouts for preventing long-running queries

## Available Tools

### 1. Database Query Tool (`dbQuery`)

Executes a SQL query and returns the results.

**Parameters:**
- `query` (string, required): SQL query to execute
- `params` (array): Parameters for prepared statements
- `timeout` (integer): Query timeout in milliseconds (default: 5000)

**Example:**
```json
{
  "query": "SELECT id, name, email FROM users WHERE status = ? AND created_at > ?",
  "params": ["active", "2023-01-01T00:00:00Z"],
  "timeout": 10000
}
```

**Returns:**
```json
{
  "rows": [
    {"id": 1, "name": "John", "email": "john@example.com"},
    {"id": 2, "name": "Jane", "email": "jane@example.com"}
  ],
  "count": 2,
  "query": "SELECT id, name, email FROM users WHERE status = ? AND created_at > ?",
  "params": ["active", "2023-01-01T00:00:00Z"]
}
```

### 2. Database Execute Tool (`dbExecute`)

Executes a SQL statement that doesn't return results (INSERT, UPDATE, DELETE).

**Parameters:**
- `statement` (string, required): SQL statement to execute
- `params` (array): Parameters for prepared statements
- `timeout` (integer): Execution timeout in milliseconds (default: 5000)

**Example:**
```json
{
  "statement": "INSERT INTO users (name, email, status) VALUES (?, ?, ?)",
  "params": ["Alice", "alice@example.com", "active"],
  "timeout": 10000
}
```

**Returns:**
```json
{
  "rowsAffected": 1,
  "lastInsertId": 3,
  "statement": "INSERT INTO users (name, email, status) VALUES (?, ?, ?)",
  "params": ["Alice", "alice@example.com", "active"]
}
```

### 3. Database Transaction Tool (`dbTransaction`)

Manages database transactions for executing multiple statements atomically.

**Parameters:**
- `action` (string, required): Action to perform (begin, commit, rollback, execute)
- `transactionId` (string): Transaction ID (returned from begin, required for all other actions)
- `statement` (string): SQL statement to execute (required for execute action)
- `params` (array): Parameters for the statement
- `readOnly` (boolean): Whether the transaction is read-only (for begin action)
- `timeout` (integer): Timeout in milliseconds (default: 30000)

**Example - Begin Transaction:**
```json
{
  "action": "begin",
  "readOnly": false,
  "timeout": 60000
}
```

**Returns:**
```json
{
  "transactionId": "tx-1625135848693",
  "readOnly": false,
  "status": "active"
}
```

**Example - Execute in Transaction:**
```json
{
  "action": "execute",
  "transactionId": "tx-1625135848693",
  "statement": "UPDATE accounts SET balance = balance - ? WHERE id = ?",
  "params": [100.00, 123]
}
```

**Example - Commit Transaction:**
```json
{
  "action": "commit",
  "transactionId": "tx-1625135848693"
}
```

**Returns:**
```json
{
  "transactionId": "tx-1625135848693",
  "status": "committed"
}
```

### 4. Database Schema Explorer Tool (`dbSchema`)

Auto-discovers database structure and relationships, including tables, columns, and foreign keys.

**Parameters:**
- `component` (string, required): Schema component to explore (tables, columns, relationships, or full)
- `table` (string): Table name (required when component is 'columns' and optional for 'relationships')
- `timeout` (integer): Query timeout in milliseconds (default: 10000)

**Example - Get All Tables:**
```json
{
  "component": "tables"
}
```

**Returns:**
```json
{
  "tables": [
    {
      "name": "users",
      "type": "BASE TABLE",
      "engine": "InnoDB",
      "estimated_row_count": 1500,
      "create_time": "2023-01-15T10:30:45Z",
      "update_time": "2023-06-20T14:15:30Z"
    },
    {
      "name": "orders",
      "type": "BASE TABLE",
      "engine": "InnoDB",
      "estimated_row_count": 8750,
      "create_time": "2023-01-15T10:35:12Z",
      "update_time": "2023-06-25T09:40:18Z"
    }
  ],
  "count": 2,
  "type": "mysql"
}
```

**Example - Get Table Columns:**
```json
{
  "component": "columns",
  "table": "users"
}
```

**Returns:**
```json
{
  "table": "users",
  "columns": [
    {
      "name": "id",
      "type": "int(11)",
      "nullable": "NO",
      "key": "PRI",
      "extra": "auto_increment",
      "default": null,
      "max_length": null,
      "numeric_precision": 10,
      "numeric_scale": 0,
      "comment": "User unique identifier"
    },
    {
      "name": "email",
      "type": "varchar(255)",
      "nullable": "NO",
      "key": "UNI",
      "extra": "",
      "default": null,
      "max_length": 255,
      "numeric_precision": null,
      "numeric_scale": null,
      "comment": "User email address"
    }
  ],
  "count": 2,
  "type": "mysql"
}
```

**Example - Get Relationships:**
```json
{
  "component": "relationships",
  "table": "orders"
}
```

**Returns:**
```json
{
  "relationships": [
    {
      "constraint_name": "fk_orders_users",
      "table_name": "orders",
      "column_name": "user_id",
      "referenced_table_name": "users",
      "referenced_column_name": "id",
      "update_rule": "CASCADE",
      "delete_rule": "RESTRICT"
    }
  ],
  "count": 1,
  "type": "mysql",
  "table": "orders"
}
```

**Example - Get Full Schema:**
```json
{
  "component": "full"
}
```

**Returns:**
A comprehensive schema including tables, columns, and relationships in a structured format.

### 5. Database Performance Analyzer Tool (`dbPerformanceAnalyzer`)

Identifies slow queries and provides optimization suggestions for better performance.

**Parameters:**
- `action` (string, required): Action to perform (getSlowQueries, getMetrics, analyzeQuery, reset, setThreshold)
- `query` (string): SQL query to analyze (required for analyzeQuery action)
- `threshold` (integer): Threshold in milliseconds for identifying slow queries (required for setThreshold action)
- `limit` (integer): Maximum number of results to return (default: 10)

**Example - Get Slow Queries:**
```json
{
  "action": "getSlowQueries",
  "limit": 5
}
```

**Returns:**
```json
{
  "queries": [
    {
      "query": "SELECT * FROM orders JOIN order_items ON orders.id = order_items.order_id WHERE orders.status = 'pending'",
      "count": 15,
      "avgDuration": "750.25ms",
      "minDuration": "520.50ms",
      "maxDuration": "1250.75ms",
      "totalDuration": "11253.75ms",
      "lastExecuted": "2023-06-25T14:30:45Z"
    },
    {
      "query": "SELECT * FROM users WHERE last_login > '2023-01-01'",
      "count": 25,
      "avgDuration": "650.30ms",
      "minDuration": "450.20ms",
      "maxDuration": "980.15ms",
      "totalDuration": "16257.50ms",
      "lastExecuted": "2023-06-25T14:15:22Z"
    }
  ],
  "count": 2
}
```

**Example - Analyze Query:**
```json
{
  "action": "analyzeQuery",
  "query": "SELECT * FROM users JOIN orders ON users.id = orders.user_id WHERE orders.total > 100 ORDER BY users.name"
}
```

**Returns:**
```json
{
  "query": "SELECT * FROM users JOIN orders ON users.id = orders.user_id WHERE orders.total > 100 ORDER BY users.name",
  "suggestions": [
    "Avoid using SELECT * - specify only the columns you need",
    "Verify that ORDER BY columns are properly indexed"
  ]
}
```

**Example - Set Slow Query Threshold:**
```json
{
  "action": "setThreshold",
  "threshold": 300
}
```

**Returns:**
```json
{
  "success": true,
  "message": "Slow query threshold updated",
  "threshold": "300ms"
}
```

**Example - Reset Performance Metrics:**
```json
{
  "action": "reset"
}
```

**Returns:**
```json
{
  "success": true,
  "message": "Performance metrics have been reset"
}
```

**Example - Get All Query Metrics:**
```json
{
  "action": "getMetrics",
  "limit": 3
}
```

**Returns:**
```json
{
  "queries": [
    {
      "query": "SELECT id, name, email FROM users WHERE status = ?",
      "count": 45,
      "avgDuration": "12.35ms",
      "minDuration": "5.20ms",
      "maxDuration": "28.75ms",
      "totalDuration": "555.75ms",
      "lastExecuted": "2023-06-25T14:45:12Z"
    },
    {
      "query": "SELECT * FROM orders WHERE user_id = ? AND created_at > ?",
      "count": 30,
      "avgDuration": "25.45ms",
      "minDuration": "15.30ms",
      "maxDuration": "45.80ms",
      "totalDuration": "763.50ms",
      "lastExecuted": "2023-06-25T14:40:18Z"
    },
    {
      "query": "UPDATE users SET last_login = ? WHERE id = ?",
      "count": 15,
      "avgDuration": "18.25ms",
      "minDuration": "10.50ms",
      "maxDuration": "35.40ms",
      "totalDuration": "273.75ms",
      "lastExecuted": "2023-06-25T14:35:30Z"
    }
  ],
  "count": 3
}
```

## Setup

To use these tools, initialize the database connection and register the tools:

```go
// Initialize database
err := dbtools.InitDatabase(config)
if err != nil {
    log.Fatalf("Failed to initialize database: %v", err)
}

// Register database tools
dbtools.RegisterDatabaseTools(toolRegistry)
```

## Error Handling

All tools return detailed error messages that indicate the specific issue. Common errors include:

- Database connection issues
- Invalid SQL syntax
- Transaction not found
- Timeout errors
- Permission errors

For transactions, always ensure you commit or rollback to avoid leaving transactions open. 