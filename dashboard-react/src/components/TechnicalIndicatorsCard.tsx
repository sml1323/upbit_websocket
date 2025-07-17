'use client';

import { useState, useEffect } from 'react';
import { BarChart3, Activity } from 'lucide-react';

interface TechnicalIndicator {
  name: string;
  value: string;
  signal: string;
  color: string;
}

interface TechnicalIndicatorsCardProps {
  selectedCoin?: string;
  predictionData?: any;
}

export default function TechnicalIndicatorsCard({ selectedCoin = 'KRW-BTC', predictionData }: TechnicalIndicatorsCardProps) {
  const [indicators, setIndicators] = useState<TechnicalIndicator[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    setIsLoading(true);
    
    if (predictionData?.technical_analysis) {
      // Use real technical analysis data from prediction API
      const technical = predictionData.technical_analysis;
      const realIndicators: TechnicalIndicator[] = [
        {
          name: 'RSI (14)',
          value: technical.rsi ? technical.rsi.toFixed(1) : 'N/A',
          signal: technical.rsi_signal === 'bullish' ? '강세' : technical.rsi_signal === 'bearish' ? '약세' : '중립',
          color: technical.rsi_signal === 'bullish' ? 'text-green-400' : technical.rsi_signal === 'bearish' ? 'text-red-400' : 'text-yellow-400'
        },
        {
          name: '볼린저밴드',
          value: technical.bb_position ? `${technical.bb_position.toFixed(1)}%` : 'N/A',
          signal: technical.bb_signal === 'neutral_bullish' ? '중립 강세' : technical.bb_signal || '중립',
          color: technical.bb_signal?.includes('bullish') ? 'text-green-400' : technical.bb_signal?.includes('bearish') ? 'text-red-400' : 'text-yellow-400'
        },
        {
          name: 'SMA (5)',
          value: technical.sma_5 ? `${technical.sma_5.toLocaleString()}` : 'N/A',
          signal: technical.trend_signal === 'bullish' ? '상승 추세' : technical.trend_signal === 'bearish' ? '하락 추세' : '중립',
          color: technical.trend_signal === 'bullish' ? 'text-green-400' : technical.trend_signal === 'bearish' ? 'text-red-400' : 'text-yellow-400'
        },
        {
          name: 'SMA (20)',
          value: technical.sma_20 ? `${technical.sma_20.toLocaleString()}` : 'N/A',
          signal: technical.overall_signal === 'buy' ? '매수' : technical.overall_signal === 'sell' ? '매도' : '홀드',
          color: technical.overall_signal === 'buy' ? 'text-green-400' : technical.overall_signal === 'sell' ? 'text-red-400' : 'text-yellow-400'
        },
        {
          name: '현재가',
          value: technical.current_price ? `${technical.current_price.toLocaleString()}` : 'N/A',
          signal: '실시간',
          color: 'text-blue-400'
        },
        {
          name: '신뢰도',
          value: technical.confidence_score ? `${technical.confidence_score}%` : 'N/A',
          signal: technical.confidence_score > 70 ? '높음' : technical.confidence_score > 50 ? '보통' : '낮음',
          color: technical.confidence_score > 70 ? 'text-green-400' : technical.confidence_score > 50 ? 'text-yellow-400' : 'text-red-400'
        }
      ];
      
      setIndicators(realIndicators);
      setIsLoading(false);
    } else {
      // Fallback to mock data
      const mockIndicators: TechnicalIndicator[] = [
        {
          name: 'RSI (14)',
          value: '52.3',
          signal: '중립 구간',
          color: 'text-yellow-400'
        },
        {
          name: 'MACD',
          value: '235.7',
          signal: '매수 신호',
          color: 'text-green-400'
        },
        {
          name: '볼린저밴드',
          value: '중간선',
          signal: '중립',
          color: 'text-yellow-400'
        },
        {
          name: 'SMA (20)',
          value: '41,200,000',
          signal: '상승 추세',
          color: 'text-green-400'
        },
        {
          name: 'EMA (12)',
          value: '41,450,000',
          signal: '강세',
          color: 'text-green-400'
        },
        {
          name: 'Stochastic',
          value: '67.8',
          signal: '과매수 근접',
          color: 'text-orange-400'
        }
      ];

      setTimeout(() => {
        setIndicators(mockIndicators);
        setIsLoading(false);
      }, 1000);
    }
  }, [predictionData]);

  const refreshIndicators = () => {
    setIsLoading(true);
    // Simulate refresh with slight variations
    setTimeout(() => {
      const updatedIndicators = indicators.map(indicator => ({
        ...indicator,
        value: indicator.name.includes('RSI') 
          ? (Math.random() * 100).toFixed(1)
          : indicator.name.includes('Stochastic')
          ? (Math.random() * 100).toFixed(1)
          : indicator.value
      }));
      setIndicators(updatedIndicators);
      setIsLoading(false);
    }, 1000);
  };

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">
          기술적 지표 {selectedCoin && `(${selectedCoin.split('-')[1]})`}
        </h3>
        <div className="flex items-center space-x-2">
          <button
            onClick={refreshIndicators}
            className="p-1 hover:bg-gray-700 rounded"
            title="새로고침"
          >
            <Activity className="h-5 w-5 text-blue-400" />
          </button>
          <BarChart3 className="h-6 w-6 text-blue-400" />
        </div>
      </div>

      <div className="space-y-3">
        {isLoading ? (
          <div className="text-center py-4">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400 mx-auto"></div>
            <div className="mt-2 text-sm text-gray-400">지표 계산 중...</div>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3">
            {indicators.map((indicator, index) => (
              <div key={index} className="bg-gray-700 rounded p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium text-gray-200">
                      {indicator.name}
                    </div>
                    <div className="text-xs text-gray-400">
                      {indicator.signal}
                    </div>
                  </div>
                  <div className={`text-lg font-bold ${indicator.color}`}>
                    {indicator.value}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Legend */}
        <div className="mt-4 pt-3 border-t border-gray-600">
          <div className="text-xs text-gray-400 mb-2">신호 범례:</div>
          <div className="flex flex-wrap gap-3 text-xs">
            <div className="flex items-center space-x-1">
              <div className="w-2 h-2 bg-green-400 rounded-full"></div>
              <span className="text-gray-400">매수/강세</span>
            </div>
            <div className="flex items-center space-x-1">
              <div className="w-2 h-2 bg-red-400 rounded-full"></div>
              <span className="text-gray-400">매도/약세</span>
            </div>
            <div className="flex items-center space-x-1">
              <div className="w-2 h-2 bg-yellow-400 rounded-full"></div>
              <span className="text-gray-400">중립/관망</span>
            </div>
            <div className="flex items-center space-x-1">
              <div className="w-2 h-2 bg-orange-400 rounded-full"></div>
              <span className="text-gray-400">주의/경계</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}