package com.bytebites.entity.jpa;

import jakarta.persistence.*;
import lombok.Data;

import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "tb_booking")
public class BookingJpa {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** BK-XXXXXXXXXXXX 唯一訂位編號 */
    @Column(name = "booking_code", nullable = false, unique = true, length = 50)
    private String bookingCode;

    @Column(name = "shop_id", nullable = false)
    private Long shopId;

    @Column(name = "people", nullable = false)
    private Integer people;

    @Column(name = "booking_date", nullable = false)
    private LocalDate bookingDate;

    /** e.g. "18:30" */
    @Column(name = "booking_time", nullable = false, length = 10)
    private String bookingTime;

    /** normal / bar / private */
    @Column(name = "table_type", nullable = false, length = 20)
    private String tableType;

    /**
     * 1 = 待付款（有訂金、尚未付款）
     * 2 = 已付款（TapPay 交易成功）
     * 3 = 已確認（免訂金直接確認）
     */
    @Column(name = "status", nullable = false, columnDefinition = "tinyint")
    private Integer status;

    @Column(name = "needs_deposit", nullable = false)
    private Boolean needsDeposit;

    @Column(name = "deposit_per_person", nullable = false)
    private Integer depositPerPerson;

    @Column(name = "deposit_total", nullable = false)
    private Integer depositTotal;

    /** TapPay rec_trade_id，付款後回寫 */
    @Column(name = "payment_trans_id", length = 100)
    private String paymentTransId;

    /** Client/Agent supplied idempotency key for retry-safe reservation creation. */
    @Column(name = "idempotency_key", unique = true, length = 120)
    private String idempotencyKey;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    @PrePersist
    protected void onCreate() {
        createdAt = updatedAt = LocalDateTime.now();
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = LocalDateTime.now();
    }
}
