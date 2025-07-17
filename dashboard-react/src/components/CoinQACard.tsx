'use client';

import { useState } from 'react';
import { MessageCircle, Send } from 'lucide-react';

export default function CoinQACard() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    setIsLoading(true);
    setAnswer('');

    try {
      const response = await fetch('/api/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question: question.trim() }),
      });

      if (!response.ok) {
        throw new Error('Failed to get answer');
      }

      const data = await response.json();
      setAnswer(data.answer || '응답을 받을 수 없습니다.');
    } catch (error) {
      console.error('Q&A error:', error);
      setAnswer('오류가 발생했습니다. 다시 시도해주세요.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-gradient-to-br from-pink-500 to-pink-600 rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">코인 Q&A</h3>
        <MessageCircle className="h-6 w-6" />
      </div>
      
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="relative">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="코인에 대해 궁금한 것을 물어보세요 (예: BTC 어때?)"
            className="w-full bg-white/20 rounded px-3 py-2 pr-10 placeholder-white/70 text-white"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !question.trim()}
            className="absolute right-2 top-1/2 transform -translate-y-1/2 p-1 hover:bg-white/20 rounded disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
        
        <div className="bg-white/20 rounded p-3 min-h-[80px]">
          {isLoading ? (
            <div className="flex items-center space-x-2">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              <span className="text-sm opacity-80">분석 중...</span>
            </div>
          ) : answer ? (
            <div className="text-sm whitespace-pre-wrap">{answer}</div>
          ) : (
            <div className="text-sm opacity-70 italic">
              질문을 입력하면 AI가 실시간 데이터를 바탕으로 답변합니다.
            </div>
          )}
        </div>
      </form>
    </div>
  );
}