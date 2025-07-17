'use client';

import { useState } from 'react';
import { TrendingUp } from 'lucide-react';

interface PredictionData {
  coin_code?: string;
  prediction?: {
    predicted_price_5m?: number;
    predicted_price_15m?: number;
    predicted_price_1h?: number;
    current_price?: number;
    overall_signal?: string;
    confidence_score?: number;
    risk_level?: string;
    recommendation?: string;
  };
  technical_analysis?: {
    overall_signal?: string;
    confidence_score?: number;
  };
}

interface PredictionAnalysisCardProps {
  onCoinSelect?: (coin: string) => void;
  onPredictionUpdate?: (data: PredictionData | null) => void;
}

export default function PredictionAnalysisCard({ onCoinSelect, onPredictionUpdate }: PredictionAnalysisCardProps) {
  const [selectedCoin, setSelectedCoin] = useState('KRW-BTC');
  const [predictionData, setPredictionData] = useState<PredictionData | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const popularCoins = ['KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-ADA', 'KRW-DOT'];

  const fetchPrediction = async (coinCode: string) => {
    setIsLoading(true);
    setPredictionData(null);

    try {
      const response = await fetch(`/api/prediction/${coinCode}`);
      
      if (!response.ok) {
        throw new Error('Failed to fetch prediction');
      }

      const data = await response.json();
      setPredictionData(data);
      onPredictionUpdate?.(data);
    } catch (error) {
      console.error('Prediction fetch error:', error);
      // Mock data fallback
      setPredictionData({
        coin_code: coinCode,
        prediction_5min: Math.random() * 2 - 1,
        prediction_15min: Math.random() * 4 - 2,
        prediction_1hour: Math.random() * 6 - 3,
        signal: ['buy', 'sell', 'hold'][Math.floor(Math.random() * 3)],
        confidence: Math.random() * 40 + 60,
        risk_level: ['low', 'medium', 'high'][Math.floor(Math.random() * 3)],
        recommendation: '현재 데이터 분석 중입니다.'
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleCoinSelect = (coinCode: string) => {
    setSelectedCoin(coinCode);
    onCoinSelect?.(coinCode);
    fetchPrediction(coinCode);
  };

  const getSignalColor = (signal?: string) => {
    switch (signal) {
      case 'buy':
      case 'strong_buy':
        return 'text-green-400';
      case 'sell':
      case 'strong_sell':
        return 'text-red-400';
      default:
        return 'text-yellow-400';
    }
  };

  const getRiskColor = (risk?: string) => {
    switch (risk) {
      case 'low':
        return 'text-green-400';
      case 'high':
        return 'text-red-400';
      default:
        return 'text-yellow-400';
    }
  };

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">예측 분석</h3>
        <TrendingUp className="h-6 w-6 text-blue-400" />
      </div>
      
      {/* Coin Selection */}
      <div className="mb-4">
        <label className="block text-sm font-medium mb-2">코인 선택</label>
        <div className="flex flex-wrap gap-2">
          {popularCoins.map((coin) => (
            <button
              key={coin}
              onClick={() => handleCoinSelect(coin)}
              className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                selectedCoin === coin
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              {coin.split('-')[1]}
            </button>
          ))}
        </div>
      </div>

      {/* Prediction Results */}
      <div className="space-y-3">
        {isLoading ? (
          <div className="text-center py-4">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400 mx-auto"></div>
            <div className="mt-2 text-sm text-gray-400">예측 분석 중...</div>
          </div>
        ) : predictionData ? (
          <>
            {/* Time-based Predictions */}
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-gray-700 rounded p-3 text-center">
                <div className="text-xs text-gray-400">5분 후</div>
                <div className={`text-lg font-bold ${
                  predictionData.prediction?.predicted_price_5m && predictionData.prediction?.current_price 
                    ? (predictionData.prediction.predicted_price_5m > predictionData.prediction.current_price ? 'text-green-400' : 'text-red-400')
                    : 'text-gray-400'
                }`}>
                  {predictionData.prediction?.predicted_price_5m && predictionData.prediction?.current_price ? 
                    `${((predictionData.prediction.predicted_price_5m - predictionData.prediction.current_price) / predictionData.prediction.current_price * 100) > 0 ? '+' : ''}${((predictionData.prediction.predicted_price_5m - predictionData.prediction.current_price) / predictionData.prediction.current_price * 100).toFixed(2)}%` : 
                    'N/A'
                  }
                </div>
              </div>
              
              <div className="bg-gray-700 rounded p-3 text-center">
                <div className="text-xs text-gray-400">15분 후</div>
                <div className={`text-lg font-bold ${
                  predictionData.prediction?.predicted_price_15m && predictionData.prediction?.current_price 
                    ? (predictionData.prediction.predicted_price_15m > predictionData.prediction.current_price ? 'text-green-400' : 'text-red-400')
                    : 'text-gray-400'
                }`}>
                  {predictionData.prediction?.predicted_price_15m && predictionData.prediction?.current_price ? 
                    `${((predictionData.prediction.predicted_price_15m - predictionData.prediction.current_price) / predictionData.prediction.current_price * 100) > 0 ? '+' : ''}${((predictionData.prediction.predicted_price_15m - predictionData.prediction.current_price) / predictionData.prediction.current_price * 100).toFixed(2)}%` : 
                    'N/A'
                  }
                </div>
              </div>
              
              <div className="bg-gray-700 rounded p-3 text-center">
                <div className="text-xs text-gray-400">1시간 후</div>
                <div className={`text-lg font-bold ${
                  predictionData.prediction?.predicted_price_1h && predictionData.prediction?.current_price 
                    ? (predictionData.prediction.predicted_price_1h > predictionData.prediction.current_price ? 'text-green-400' : 'text-red-400')
                    : 'text-gray-400'
                }`}>
                  {predictionData.prediction?.predicted_price_1h && predictionData.prediction?.current_price ? 
                    `${((predictionData.prediction.predicted_price_1h - predictionData.prediction.current_price) / predictionData.prediction.current_price * 100) > 0 ? '+' : ''}${((predictionData.prediction.predicted_price_1h - predictionData.prediction.current_price) / predictionData.prediction.current_price * 100).toFixed(2)}%` : 
                    'N/A'
                  }
                </div>
              </div>
            </div>

            {/* Signal and Confidence */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-gray-700 rounded p-3">
                <div className="text-xs text-gray-400">매매 신호</div>
                <div className={`text-lg font-bold uppercase ${getSignalColor(predictionData.prediction?.overall_signal)}`}>
                  {predictionData.prediction?.overall_signal || 'HOLD'}
                </div>
              </div>
              
              <div className="bg-gray-700 rounded p-3">
                <div className="text-xs text-gray-400">신뢰도</div>
                <div className="text-lg font-bold text-blue-400">
                  {predictionData.prediction?.confidence_score ? `${predictionData.prediction.confidence_score.toFixed(1)}%` : 'N/A'}
                </div>
              </div>
            </div>

            {/* Risk Level */}
            {predictionData.prediction?.risk_level && (
              <div className="bg-gray-700 rounded p-3">
                <div className="text-xs text-gray-400">위험도 레벨</div>
                <div className={`text-lg font-bold uppercase ${getRiskColor(predictionData.prediction.risk_level)}`}>
                  {predictionData.prediction.risk_level}
                </div>
              </div>
            )}

            {/* Recommendation */}
            {predictionData.prediction?.recommendation && (
              <div className="bg-gray-700 rounded p-3">
                <div className="text-xs text-gray-400">추천 사항</div>
                <div className="text-sm text-gray-200">
                  {predictionData.prediction.recommendation}
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="text-center py-4 text-gray-400">
            코인을 선택하여 예측 분석을 확인하세요.
          </div>
        )}
      </div>
    </div>
  );
}