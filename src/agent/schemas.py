"""Typed Evidence 스키마 — 에이전트 출력을 구조화된 JSON으로 강제."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MarketEvidence(BaseModel):
    """Market Analyst 출력 스키마."""

    claim: str = Field(description="핵심 분석 결론 1문장")
    evidence: list[str] = Field(description="근거 데이터 포인트")
    confidence: float = Field(ge=0.0, le=1.0, description="신뢰도 0.0-1.0")
    missing_data: list[str] = Field(
        default_factory=list, description="분석에 부족한 데이터"
    )


class NewsEvidence(BaseModel):
    """News Analyst 출력 스키마."""

    headlines: list[str] = Field(description="관련 뉴스 제목")
    sentiment: Literal["BULLISH", "BEARISH", "NEUTRAL"] = Field(
        description="뉴스 감성"
    )
    relevance_score: float = Field(ge=0.0, le=1.0, description="이상치와의 관련성")
    source_quality: Literal["official", "major_media", "community", "unknown"] = Field(
        description="뉴스 소스 품질"
    )


class IncidentAssessment(BaseModel):
    """Report Writer 출력 스키마."""

    root_cause: str = Field(description="최유력 원인 추정")
    confidence: float = Field(ge=0.0, le=1.0, description="신뢰도 0.0-1.0")
    supporting_evidence: list[str] = Field(
        description="근거 (upstream 분석에서 인용)"
    )
    alternative_hypotheses: list[str] = Field(
        default_factory=list, description="대안 가설 + 왜 아닌지"
    )
    recommended_action: Literal["MONITOR", "ALERT", "ESCALATE"] = Field(
        description="권장 조치"
    )
    summary: str = Field(description="인시던트 요약 리포트 (한국어, 3-5문장)")
