package com.bytebites.entity.jpa;

import jakarta.persistence.*;
import lombok.Data;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "tb_shop_ai_metadata")
public class ShopAiMetadataJpa {

    @Id
    @Column(name = "shop_id")
    private Long shopId;

    @Column(name = "ai_summary", columnDefinition = "TEXT")
    private String aiSummary;

    @Column(name = "highlight_review")
    private String highlightReview;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "signature_dishes", columnDefinition = "json")
    private String signatureDishes;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "atmosphere_tags", columnDefinition = "json")
    private String atmosphereTags;

    @Column(name = "booking_difficulty")
    private String bookingDifficulty;

    @Column(name = "price_per_person")
    private String pricePerPerson;

    @Column(name = "phone")
    private String phone;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "opening_hours", columnDefinition = "json")
    private String openingHours;

    @Column(name = "extracted_at")
    private LocalDateTime extractedAt;

    @Column(name = "model_version")
    private String modelVersion;
}
