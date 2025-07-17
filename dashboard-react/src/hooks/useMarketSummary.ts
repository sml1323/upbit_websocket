'use client';

import { useState, useEffect } from 'react';
import { useWebSocket } from './useWebSocket';

interface MarketSummaryData {
  timestamp: string;
  total_coins: number;
  rising_coins: number;
  falling_coins: number;
  rising_percentage: number;
  falling_percentage: number;
  top_gainer: {
    coin: string;
    change_rate: number;
  };
  top_loser: {
    coin: string;
    change_rate: number;
  };
  highest_volume: {
    coin: string;
    volume: number;
  };
  total_volume: number;
}

export const useMarketSummary = () => {
  const [marketData, setMarketData] = useState<MarketSummaryData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // WebSocket URL 구성 (프로덕션에서는 환경변수 사용)
  const wsUrl = process.env.NODE_ENV === 'production' 
    ? 'wss://your-domain.com/ws/market-summary'
    : 'ws://localhost:8001/ws/market-summary';

  const { lastMessage, isConnected } = useWebSocket(wsUrl, {
    onConnect: () => {
      setError(null);
      console.log('Market summary WebSocket connected');
    },
    onDisconnect: () => {
      console.log('Market summary WebSocket disconnected');
    },
    onError: (error) => {
      setError('WebSocket connection error');
      console.error('Market summary WebSocket error:', error);
    }
  });

  useEffect(() => {
    if (lastMessage) {
      try {
        // FastAPI 백엔드에서 받은 데이터 처리
        if (typeof lastMessage === 'object' && lastMessage && 'data' in lastMessage) {
          setMarketData((lastMessage as { data: MarketSummaryData }).data);
        } else if (typeof lastMessage === 'object') {
          setMarketData(lastMessage as MarketSummaryData);
        } else {
          console.warn('Unexpected message format:', lastMessage);
        }
        setIsLoading(false);
        setError(null);
      } catch (err) {
        console.error('Failed to process market data:', err);
        setError('Failed to process market data');
      }
    }
  }, [lastMessage]);

  return {
    marketData,
    isLoading,
    error,
    isConnected
  };
};