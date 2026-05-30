package com.bytebites.entity.jpa;

import jakarta.persistence.*;
import lombok.Data;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "tb_shop_absa")
public class ShopAbsaJpa {

    @Id
    @Column(name = "shop_id")
    private Long shopId;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "aspects", columnDefinition = "json")
    private String aspects;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "meta", columnDefinition = "json")
    private String meta;

    @Column(name = "char_hit_rate")
    private Float charHitRate;

    @Column(name = "semantic_hit_rate")
    private Float semanticHitRate;

    @Column(name = "synonym_recovered")
    private Integer synonymRecovered;

    @Column(name = "unverified_count")
    private Integer unverifiedCount;

    @Column(name = "prompt_version")
    private String promptVersion;

    @Column(name = "model")
    private String model;

    @Column(name = "generated_at")
    private LocalDateTime generatedAt;
}
