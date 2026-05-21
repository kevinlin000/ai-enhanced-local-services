package com.bytebites.domain.jpa;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import jakarta.persistence.Transient;
import lombok.Data;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "tb_shop")
public class ShopJpa {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String name;

    @Column(name = "type_id")
    private Long typeId;

    private String images;
    private String area;
    private String address;

    private Double x;
    private Double y;

    @Column(name = "avg_price")
    private Long avgPrice;

    private Integer sold;
    private Integer comments;
    private Integer score;

    @Column(name = "open_hours")
    private String openHours;

    @Column(name = "mrt_station")
    private String mrtStation;

    @Column(name = "mrt_distance_meters")
    private Integer mrtDistanceMeters;

    private String district;

    @Column(name = "price_range")
    @JdbcTypeCode(SqlTypes.TINYINT)
    private Integer priceRange;

    @Column(name = "business_hours")
    private String businessHours;

    @Column(name = "create_time", updatable = false)
    private LocalDateTime createTime;

    @Column(name = "update_time")
    private LocalDateTime updateTime;

    @Transient
    private Double distance;

    @PrePersist
    void onCreate() {
        createTime = LocalDateTime.now();
        updateTime = createTime;
    }

    @PreUpdate
    void onUpdate() {
        updateTime = LocalDateTime.now();
    }
}
