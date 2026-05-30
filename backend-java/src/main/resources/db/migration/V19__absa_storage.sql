-- V19: ABSA (Aspect-Based Sentiment Analysis) result storage
-- Python AI service writes here after each ABSA batch run.
-- 1:1 with tb_shop — one row = most recent ABSA result for that shop.
-- History tracking (if ever needed) belongs in a separate audit table.

CREATE TABLE IF NOT EXISTS tb_shop_absa (
    shop_id           BIGINT UNSIGNED  NOT NULL                                          COMMENT 'tb_shop.id 1:1',
    aspects           JSON             NOT NULL                                          COMMENT 'ABSA aspects array: dishes/service/environment/price, each with summary/sentiment/confidence/positive_evidence/negative_evidence',
    meta              JSON             NULL                                              COMMENT 'LLM meta: model, prompt_version, review_count_total, review_count_analyzed',
    char_hit_rate     FLOAT            NULL                                              COMMENT 'v1 char-level verifier hit rate [0.0, 1.0]',
    semantic_hit_rate FLOAT            NULL                                              COMMENT 'v2 semantic verifier hit rate [0.0, 1.0]',
    synonym_recovered INT UNSIGNED     NULL DEFAULT 0                                   COMMENT 'evidence claims rescued by semantic rescue layer',
    unverified_count  INT UNSIGNED     NULL DEFAULT 0                                   COMMENT 'evidence claims still unverified after v2 semantic pass',
    prompt_version    VARCHAR(20)      NULL                                              COMMENT 'ABSA prompt version, e.g. v2.0',
    model             VARCHAR(100)     NULL                                              COMMENT 'LLM model, e.g. gemini-3.1-flash-lite',
    generated_at      TIMESTAMP        NOT NULL DEFAULT CURRENT_TIMESTAMP               COMMENT 'when Python AI service generated this row; set by caller, falls back to insert time',
    create_time       TIMESTAMP        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time       TIMESTAMP        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (shop_id),
    INDEX idx_absa_generated_at (generated_at),

    CONSTRAINT fk_shop_absa_shop
        FOREIGN KEY (shop_id) REFERENCES tb_shop (id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci
  COMMENT = 'LLM aspect-based sentiment analysis results, one row per shop (latest run)';
