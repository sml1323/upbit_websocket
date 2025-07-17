import { NextResponse } from 'next/server';

const FASTAPI_BASE_URL = process.env.FASTAPI_BASE_URL || 'http://localhost:8001';

export async function GET() {
  try {
    const response = await fetch(`${FASTAPI_BASE_URL}/health`, {
      method: 'GET',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Market summary API error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch market summary' },
      { status: 500 }
    );
  }
}