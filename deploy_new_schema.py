#!/usr/bin/env python3
"""
Deployment script for new Upbit ticker schema (22 fields)
Handles schema migration from trade_data (4 fields) to ticker_data (22 fields)
"""

import os
import sys
import logging
import psycopg2
from psycopg2.extensions import connection as Connection
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DB_NAME = os.getenv("TIMESCALEDB_DBNAME", "coin")
DB_USER = os.getenv("TIMESCALEDB_USER", "postgres")
DB_PASSWORD = os.getenv("TIMESCALEDB_PASSWORD", "postgres")
DB_HOST = os.getenv("TIMESCALEDB_HOST", "localhost")
DB_PORT = os.getenv("TIMESCALEDB_PORT", "5432")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def connect_db() -> Connection:
    """Create database connection."""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        logging.info(f"Connected to database: {DB_NAME}")
        return conn
    except Exception as e:
        logging.error(f"Failed to connect to database: {e}")
        raise

def execute_sql_file(conn: Connection, file_path: str) -> None:
    """Execute SQL commands from file."""
    try:
        with open(file_path, 'r') as f:
            sql_commands = f.read()
        
        with conn.cursor() as cur:
            cur.execute(sql_commands)
            conn.commit()
        
        logging.info(f"Successfully executed: {file_path}")
    except Exception as e:
        logging.error(f"Failed to execute {file_path}: {e}")
        conn.rollback()
        raise

def check_existing_data(conn: Connection) -> dict:
    """Check existing data in trade_data table."""
    try:
        with conn.cursor() as cur:
            # Check if trade_data table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'trade_data'
                );
            """)
            table_exists = cur.fetchone()[0]
            
            if not table_exists:
                return {"exists": False, "count": 0, "unique_codes": 0}
            
            # Get table statistics
            cur.execute("SELECT COUNT(*) FROM trade_data;")
            total_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(DISTINCT code) FROM trade_data;")
            unique_codes = cur.fetchone()[0]
            
            cur.execute("SELECT MIN(time), MAX(time) FROM trade_data;")
            time_range = cur.fetchone()
            
            return {
                "exists": True,
                "count": total_count,
                "unique_codes": unique_codes,
                "earliest": time_range[0],
                "latest": time_range[1]
            }
    except Exception as e:
        logging.error(f"Failed to check existing data: {e}")
        return {"exists": False, "count": 0, "unique_codes": 0}

def verify_new_schema(conn: Connection) -> bool:
    """Verify the new ticker_data schema is properly set up."""
    try:
        with conn.cursor() as cur:
            # Check if ticker_data table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'ticker_data'
                );
            """)
            table_exists = cur.fetchone()[0]
            
            if not table_exists:
                logging.error("ticker_data table does not exist")
                return False
            
            # Check if required ENUM types exist
            cur.execute("""
                SELECT COUNT(*) FROM pg_type 
                WHERE typname IN (
                    'market_change_type', 'market_ask_bid_type', 
                    'market_state_type', 'market_warning_type', 'stream_type_enum'
                );
            """)
            enum_count = cur.fetchone()[0]
            
            if enum_count != 5:
                logging.error(f"Expected 5 ENUM types, found {enum_count}")
                return False
            
            # Check if hypertable exists
            cur.execute("""
                SELECT COUNT(*) FROM timescaledb_information.hypertables 
                WHERE table_name = 'ticker_data';
            """)
            hypertable_count = cur.fetchone()[0]
            
            if hypertable_count != 1:
                logging.error("ticker_data hypertable not found")
                return False
            
            logging.info("✅ New schema validation passed")
            return True
            
    except Exception as e:
        logging.error(f"Schema verification failed: {e}")
        return False

def main():
    """Main deployment process."""
    print("🚀 Starting Upbit Ticker Schema Deployment")
    print("=" * 50)
    
    # Connect to database
    conn = connect_db()
    
    try:
        # Step 1: Check existing data
        print("\n📊 Checking existing data...")
        existing_data = check_existing_data(conn)
        
        if existing_data["exists"]:
            print(f"   Found existing trade_data table:")
            print(f"   - Total records: {existing_data['count']:,}")
            print(f"   - Unique codes: {existing_data['unique_codes']}")
            print(f"   - Time range: {existing_data['earliest']} to {existing_data['latest']}")
            
            # Ask for confirmation
            response = input("\n⚠️  Proceeding will create new schema. Continue? (y/N): ")
            if response.lower() != 'y':
                print("❌ Deployment cancelled")
                return
        else:
            print("   No existing trade_data table found")
        
        # Step 2: Deploy new schema
        print("\n🗄️  Deploying new ticker_data schema...")
        schema_file = "schema/ticker_data_schema.sql"
        
        if not os.path.exists(schema_file):
            print(f"❌ Schema file not found: {schema_file}")
            return
        
        execute_sql_file(conn, schema_file)
        print("   ✅ Schema deployed successfully")
        
        # Step 3: Set up TimescaleDB configurations
        print("\n⚙️  Setting up TimescaleDB configurations...")
        timescale_file = "schema/timescale_setup.sql"
        
        if os.path.exists(timescale_file):
            execute_sql_file(conn, timescale_file)
            print("   ✅ TimescaleDB setup completed")
        else:
            print(f"   ⚠️  TimescaleDB setup file not found: {timescale_file}")
        
        # Step 3.5: Set up MCP functions
        print("\n🔧 Setting up MCP functions for LLM integration...")
        mcp_functions_file = "schema/mcp_functions.sql"
        
        if os.path.exists(mcp_functions_file):
            execute_sql_file(conn, mcp_functions_file)
            print("   ✅ MCP functions installed successfully")
        else:
            print(f"   ⚠️  MCP functions file not found: {mcp_functions_file}")
        
        # Step 4: Verify new schema
        print("\n🔍 Verifying new schema...")
        if verify_new_schema(conn):
            print("   ✅ Schema verification passed")
        else:
            print("   ❌ Schema verification failed")
            return
        
        # Step 5: Display next steps
        print("\n🎯 Deployment completed successfully!")
        print("\nNext steps:")
        print("1. Update consumer.py to use new schema (already done)")
        print("2. Restart Kafka consumer: python upbit-kafka/consumer.py")
        print("3. Monitor data ingestion and verify all 22 fields are populated")
        print("4. Set up MCP server for LLM integration")
        
        print("\n📋 Key tables created:")
        print("   - ticker_data (main table with 22 fields)")
        print("   - ohlcv_1m (1-minute OHLCV aggregates)")
        print("   - market_summary_5m (5-minute market summaries)")
        print("   - volume_anomalies_1h (hourly volume anomaly detection)")
        
    except Exception as e:
        logging.error(f"Deployment failed: {e}")
        print(f"\n❌ Deployment failed: {e}")
        return
    
    finally:
        conn.close()

if __name__ == "__main__":
    main()