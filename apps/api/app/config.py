from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LLM_BUDGET_TIERS: dict[str, dict[str, int]] = {
    "budget": {"parent_chunks": 4, "max_output_tokens": 800, "max_input_tokens": 4000},
    "balanced": {"parent_chunks": 5, "max_output_tokens": 1200, "max_input_tokens": 6000},
    "quality": {"parent_chunks": 6, "max_output_tokens": 1600, "max_input_tokens": 8000},
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://studypilot:studypilot@localhost:5433/studypilot"
    test_database_url: str = (
        "postgresql+psycopg://studypilot:studypilot@localhost:5433/studypilot_test"
    )
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dims: int = 384
    ocr_chars_per_page_threshold: int = 50

    # Hybrid retrieval (Phase 1b)
    rrf_k: int = 60
    hybrid_vector_weight: float = 1.0
    hybrid_bm25_weight: float = 1.0
    retrieval_vector_top_k: int = 40
    retrieval_bm25_top_k: int = 40
    rrf_output_top_k: int = 24

    # Rerank + gate
    rerank_model: str = "BAAI/bge-reranker-base"
    rerank_output_top_k: int = 6
    study_output_top_k: int = 5
    min_rerank_score: float = 0.35
    min_rerank_score_exam: float = 0.25

    # Context expansion stub (Phase 1c)
    context_max_tokens: int = 4000

    # OpenRouter generation (Path A — chat only, no embeddings)
    openrouter_api_key: str = ""
    environment: str = "development"
    openrouter_dev_chat_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    openrouter_chat_model: str = "deepseek/deepseek-chat"
    studypilot_llm_budget: str = "budget"
    studypilot_retrieval_timeout_s: float = 0.0
    llm_temperature: float = 0.05

    clerk_jwks_url: str = ""
    clerk_issuer: str = ""
    studypilot_auth_disabled: bool = False

    @field_validator("studypilot_auth_disabled", mode="before")
    @classmethod
    def parse_auth_disabled(cls, value: object) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def auth_disabled(self) -> bool:
        return self.environment == "development" and self.studypilot_auth_disabled

    def resolved_chat_model(self) -> str:
        if self.environment == "production":
            return self.openrouter_chat_model
        return self.openrouter_dev_chat_model

    def llm_budget_tier(self) -> dict[str, int]:
        tier = LLM_BUDGET_TIERS.get(self.studypilot_llm_budget)
        if tier is None:
            return LLM_BUDGET_TIERS["budget"]
        return tier

    def retrieval_timeout_enabled(self) -> bool:
        return self.studypilot_retrieval_timeout_s > 0


settings = Settings()
