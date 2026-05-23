package com.bytebites.domain.jpa;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Data;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "tb_voucher_order")
public class VoucherOrderJpa {
    @Id
    private Long id;

    @Column(name = "user_id")
    private Long userId;

    @Column(name = "voucher_id")
    private Long voucherId;

    @Column(name = "pay_type")
    @JdbcTypeCode(SqlTypes.TINYINT)
    private Integer payType = 1;

    @JdbcTypeCode(SqlTypes.TINYINT)
    private Integer status = 1;

    @Column(name = "create_time", insertable = false, updatable = false)
    private LocalDateTime createTime;

    @Column(name = "pay_time")
    private LocalDateTime payTime;

    @Column(name = "use_time")
    private LocalDateTime useTime;

    @Column(name = "refund_time")
    private LocalDateTime refundTime;

    @Column(name = "update_time", insertable = false, updatable = false)
    private LocalDateTime updateTime;
}
