"""Typed 스키마 — 에이전트 출력(LLM 강제)과 도구 반환(코드 검증)을 구조화한다."""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


# ── 뉴스 검색 도구 반환 계약 (R1) ─────────────────────────────
# LLM 출력 스키마가 아니라 도구 결과를 코드가 검증하는 계약이다.
# 설계: docs/agent-improvement/ROADMAP.md §4

MAX_NEWS_ARTICLES = 5

NewsSearchStatus = Literal["ok", "empty", "error", "unavailable"]
NewsProvider = Literal["cryptopanic", "serpapi"]
NewsErrorCode = Literal["timeout", "http_error", "invalid_response", "request_error"]


class NewsArticle(BaseModel):
    """검색 공급자가 준 기사 1건. 링크한 페이지는 요청하지 않는다."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, description="기사 제목")
    url: str = Field(min_length=1, description="공급자가 준 기사 링크. 앞뒤 공백 외에는 원래 문자열 그대로")
    source: str = Field(default="", description="매체명. 모르면 빈 문자열")

    @field_validator("url")
    @classmethod
    def _require_http_url(cls, url: str) -> str:
        # HttpUrl 은 '/' 추가·퍼센트 인코딩·호스트 소문자화로 문자열을 바꾼다 → 형식만 검사하고 원문을 돌려준다.
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("http(s)://호스트 형식의 URL이 아님")
        return url


class NewsProviderAttempt(BaseModel):
    """공급자 1곳을 확인한 결과. 앞선 성공으로 확인하지 않은 공급자는 기록하지 않는다."""

    provider: NewsProvider
    status: NewsSearchStatus
    error_code: NewsErrorCode | None = None

    @model_validator(mode="after")
    def _error_code_only_on_error(self) -> NewsProviderAttempt:
        if (self.status == "error") != (self.error_code is not None):
            raise ValueError("error_code 는 status 가 error 일 때만 있어야 한다")
        return self


class NewsSearchResult(BaseModel):
    """search_news 도구의 반환값."""

    status: NewsSearchStatus
    articles: list[NewsArticle] = Field(default_factory=list, max_length=MAX_NEWS_ARTICLES)
    attempts: list[NewsProviderAttempt] = Field(default_factory=list)

    @model_validator(mode="after")
    def _articles_only_on_ok(self) -> NewsSearchResult:
        if (self.status == "ok") != bool(self.articles):
            raise ValueError("ok 면 기사가 1건 이상, 그 외 상태는 빈 목록이어야 한다")
        return self
