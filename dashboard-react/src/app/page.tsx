'use client';

import { useState, useEffect } from 'react';
import { Activity, TrendingUp, AlertTriangle } from 'lucide-react';
import { useMarketSummary } from '@/hooks/useMarketSummary';
import MarketSummaryCard from '@/components/MarketSummaryCard';
import CoinQACard from '@/components/CoinQACard';
import PredictionAnalysisCard from '@/components/PredictionAnalysisCard';
import TechnicalIndicatorsCard from '@/components/TechnicalIndicatorsCard';

export default function DashboardPage() {
  const { marketData, isLoading, error, isConnected } = useMarketSummary();
  const [currentTime, setCurrentTime] = useState<Date | null>(null);
  const [mockPrices, setMockPrices] = useState<number[]>([]);
  const [selectedCoin, setSelectedCoin] = useState<string>('KRW-BTC');
  const [predictionData, setPredictionData] = useState<any>(null);

  useEffect(() => {
    // 클라이언트 사이드에서만 시간 설정
    setCurrentTime(new Date());
    
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    // 클라이언트 사이드에서만 랜덤 값 생성
    setMockPrices(['BTC', 'ETH', 'XRP', 'ADA', 'DOT'].map(() => Math.random() * 5 + 1));
  }, []);

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <nav className="bg-gray-800 border-b-2 border-blue-600 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <Activity className="h-8 w-8 text-blue-400" />
            <h1 className="text-2xl font-bold text-white">
              Upbit LLM Analytics Dashboard
            </h1>
          </div>
          
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-400' : 'bg-red-400'}`} />
              <span className="text-sm">
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
            <div className="text-sm text-gray-300">
              {currentTime ? currentTime.toLocaleString('ko-KR') : '--:--:--'}
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="container mx-auto px-6 py-8">
        {/* Error Banner */}
        {error && (
          <div className="mb-6 bg-red-600 border border-red-700 rounded-lg p-4">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="h-5 w-5" />
              <span>연결 오류: {error}</span>
            </div>
          </div>
        )}

        {/* Top Row - Main Stats */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <MarketSummaryCard 
            marketData={marketData} 
            isLoading={isLoading} 
          />
          
          <CoinQACard />
          
          <div className="bg-gradient-to-br from-cyan-500 to-cyan-600 rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">이상 거래 탐지</h3>
              <AlertTriangle className="h-6 w-6" />
            </div>
            <div className="space-y-3">
              <div className="bg-white/20 rounded p-3">
                <div className="text-sm opacity-80">실시간 모니터링</div>
                <div className="text-xl font-bold">정상</div>
              </div>
              <div className="text-sm opacity-80">
                마지막 업데이트: {currentTime ? currentTime.toLocaleTimeString('ko-KR') : '--:--:--'}
              </div>
            </div>
          </div>
        </div>

        {/* Second Row - Detailed Analysis */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 mb-8">
          <PredictionAnalysisCard 
            onCoinSelect={setSelectedCoin}
            onPredictionUpdate={setPredictionData}
          />
          <TechnicalIndicatorsCard 
            selectedCoin={selectedCoin}
            predictionData={predictionData}
          />
        </div>

        {/* Third Row - Additional Features */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Top Coins Predictions */}
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4">주요 코인 예측 요약</h3>
            <div className="space-y-3">
              {['BTC', 'ETH', 'XRP', 'ADA', 'DOT'].map((coin, index) => (
                <div key={coin} className="flex items-center justify-between bg-gray-700 rounded p-3">
                  <div className="flex items-center space-x-3">
                    <span className="font-medium">KRW-{coin}</span>
                    <TrendingUp className="h-4 w-4 text-green-400" />
                  </div>
                  <span className="text-green-400 font-medium">
                    +{mockPrices[index] ? mockPrices[index].toFixed(1) : '2.5'}%
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Volume Signals */}
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4">거래량 신호 분석</h3>
            <div className="space-y-3">
              {isLoading ? (
                <div className="text-center py-4">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400 mx-auto"></div>
                  <div className="mt-2 text-sm text-gray-400">데이터 로딩 중...</div>
                </div>
              ) : (
                <div className="bg-gray-700 rounded p-3">
                  <div className="text-sm text-gray-400">정상 거래량 패턴</div>
                  <div className="text-lg font-medium">이상 신호 없음</div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
