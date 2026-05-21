package com.bytebites.domain.jpa;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Data;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "tb_voucher")
public class VoucherJpa {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "shop_id")
    private Long shopId;

    private String title;

    @Column(name = "sub_title")
    private String subTitle;

    private String rules;

    @Column(name = "pay_value")
    private Long payValue;

    @Column(name = "actual_value")
    private Long actualValue;

    @JdbcTypeCode(SqlTypes.TINYINT)
    private Integer type;

    @JdbcTypeCode(SqlTypes.TINYINT)
    private Integer status;

    @Column(name = "create_time", insertable = false, updatable = false)
    private LocalDateTime createTime;

    @Column(name = "update_time", insertable = false, updatable = false)
    private LocalDateTime updateTime;
}
