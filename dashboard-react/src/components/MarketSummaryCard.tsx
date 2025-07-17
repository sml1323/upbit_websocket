'use client';

import { TrendingUp, TrendingDown } from 'lucide-react';

interface MarketSummaryData {
  timestamp?: string;
  total_coins?: number;
  rising_coins?: number;
  falling_coins?: number;
  rising_percentage?: number;
  falling_percentage?: number;
  top_gainer?: {
    coin: string;
    change_rate: number;
  };
  top_loser?: {
    coin: string;
    change_rate: number;
  };
  highest_volume?: {
    coin: string;
    volume: number;
  };
  total_volume?: number;
}

interface MarketSummaryCardProps {
  marketData: MarketSummaryData | null;
  isLoading: boolean;
}

export default function MarketSummaryCard({ marketData, isLoading }: MarketSummaryCardProps) {
  if (isLoading) {
    return (
      <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">실시간 시장 요약</h3>
          <TrendingUp className="h-6 w-6" />
        </div>
        <div className="text-center py-4">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white mx-auto"></div>
          <div className="mt-2 text-sm opacity-80">데이터 로딩 중...</div>
        </div>
      </div>
    );
  }

  const risingCoins = marketData?.rising_coins || 0;
  const fallingCoins = marketData?.falling_coins || 0;
  const totalCoins = marketData?.total_coins || risingCoins + fallingCoins;
  const risingPercentage = totalCoins > 0 ? (risingCoins / totalCoins * 100).toFixed(1) : '0';

  return (
    <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">실시간 시장 요약</h3>
        <TrendingUp className="h-6 w-6" />
      </div>
      
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-white/20 rounded p-3">
            <div className="flex items-center space-x-2">
              <TrendingUp className="h-4 w-4 text-green-300" />
              <span className="text-sm opacity-80">상승</span>
            </div>
            <div className="text-xl font-bold">{risingCoins}</div>
          </div>
          
          <div className="bg-white/20 rounded p-3">
            <div className="flex items-center space-x-2">
              <TrendingDown className="h-4 w-4 text-red-300" />
              <span className="text-sm opacity-80">하락</span>
            </div>
            <div className="text-xl font-bold">{fallingCoins}</div>
          </div>
        </div>
        
        <div className="bg-white/20 rounded p-3">
          <div className="text-sm opacity-80">상승률</div>
          <div className="text-xl font-bold">{risingPercentage}%</div>
        </div>
        
        {marketData?.top_gainer && (
          <div className="bg-white/20 rounded p-3">
            <div className="text-sm opacity-80">최고 상승</div>
            <div className="text-lg font-bold">
              {marketData.top_gainer.coin} (+{marketData.top_gainer.change_rate?.toFixed(2) || '0.00'}%)
            </div>
          </div>
        )}
      </div>
    </div>
  );
}