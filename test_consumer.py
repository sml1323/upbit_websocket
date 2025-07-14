#!/usr/bin/env python3
"""
Test script for the 22-field consumer
"""
import os
import psycopg2
from datetime import datetime, timezone
from decimal import Decimal

# Database configuration
DB_NAME = "upbit_analytics"
DB_USER = "upbit_user"
DB_PASSWORD = "upbit_password"
DB_HOST = "localhost"
DB_PORT = "5432"

def test_database_connection():
    """Test database connection and schema"""
    try:
        # Test connection using external host
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        cursor = conn.cursor()
        
        # Test table exists
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'ticker_data'
        """)
        
        if cursor.fetchone():
            print("✅ ticker_data table exists")
        else:
            print("❌ ticker_data table not found")
            return False
        
        # Test table structure
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'ticker_data'
            ORDER BY ordinal_position
        """)
        
        columns = cursor.fetchall()
        print(f"📊 Table has {len(columns)} columns:")
        for col_name, col_type in columns[:5]:  # Show first 5 columns
            print(f"   {col_name}: {col_type}")
        print(f"   ... and {len(columns) - 5} more columns")
        
        # Test insert
        test_data = (
            datetime.now(timezone.utc),  # time
            'KRW-BTC',  # code
            'ticker',  # type
            Decimal('50000000'),  # opening_price
            Decimal('51000000'),  # high_price
            Decimal('49000000'),  # low_price
            Decimal('50500000'),  # trade_price
            Decimal('50200000'),  # prev_closing_price
            'RISE',  # change
            Decimal('300000'),  # change_price
            Decimal('300000'),  # signed_change_price
            Decimal('0.006'),  # change_rate
            Decimal('0.006'),  # signed_change_rate
            Decimal('100.5'),  # trade_volume
            Decimal('1000000'),  # acc_trade_volume
            Decimal('50000000000'),  # acc_trade_price
            'ASK',  # ask_bid
            Decimal('500000'),  # acc_ask_volume
            Decimal('500000'),  # acc_bid_volume
            Decimal('50000000000'),  # acc_trade_price_24h
            Decimal('1000000'),  # acc_trade_volume_24h
            Decimal('52000000'),  # highest_52_week_price
            '2024-01-01',  # highest_52_week_date
            Decimal('30000000'),  # lowest_52_week_price
            '2024-01-01',  # lowest_52_week_date
            'ACTIVE',  # market_state
            'NONE',  # market_warning
            False,  # is_trading_suspended
            None,  # delisting_date
            '20240101',  # trade_date
            '120000',  # trade_time
            1704067200000,  # trade_timestamp
            1704067200000,  # timestamp
            'REALTIME'  # stream_type
        )
        
        cursor.execute("""
            INSERT INTO ticker_data (
                time, code, type, opening_price, high_price, low_price, trade_price, 
                prev_closing_price, change, change_price, signed_change_price, 
                change_rate, signed_change_rate, trade_volume, acc_trade_volume, 
                acc_trade_price, ask_bid, acc_ask_volume, acc_bid_volume, 
                acc_trade_price_24h, acc_trade_volume_24h, highest_52_week_price, 
                highest_52_week_date, lowest_52_week_price, lowest_52_week_date, 
                market_state, market_warning, is_trading_suspended, delisting_date, 
                trade_date, trade_time, trade_timestamp, timestamp, stream_type
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, test_data)
        
        conn.commit()
        print("✅ Test insert successful")
        
        # Verify data
        cursor.execute("SELECT COUNT(*) FROM ticker_data")
        count = cursor.fetchone()[0]
        print(f"📊 Total records: {count}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing 22-field consumer database setup...")
    success = test_database_connection()
    if success:
        print("\n✅ All tests passed! Ready for consumer testing.")
    else:
        print("\n❌ Tests failed. Check configuration.")