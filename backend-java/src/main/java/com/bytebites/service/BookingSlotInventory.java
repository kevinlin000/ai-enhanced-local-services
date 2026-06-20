package com.bytebites.service;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.time.LocalDate;

@Component
public class BookingSlotInventory {
    private final JdbcTemplate jdbcTemplate;

    public BookingSlotInventory(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public boolean reserve(Long shopId, LocalDate bookingDate, String time, String tableType, int people) {
        String normalizedTableType = normalizeTableType(tableType);
        ensure(shopId, bookingDate, time, normalizedTableType);
        int updated = jdbcTemplate.update(
                """
                UPDATE tb_booking_slot_inventory
                SET booked_count = booked_count + ?
                WHERE shop_id = ? AND booking_date = ? AND booking_time = ? AND table_type = ?
                  AND booked_count + ? <= capacity
                """,
                people, shopId, bookingDate, time, normalizedTableType, people
        );
        return updated == 1;
    }

    public void release(Long shopId, LocalDate bookingDate, String time, String tableType, int people) {
        String normalizedTableType = normalizeTableType(tableType);
        jdbcTemplate.update(
                """
                UPDATE tb_booking_slot_inventory
                SET booked_count = GREATEST(booked_count - ?, 0)
                WHERE shop_id = ? AND booking_date = ? AND booking_time = ? AND table_type = ?
                """,
                people, shopId, bookingDate, time, normalizedTableType
        );
    }

    private void ensure(Long shopId, LocalDate bookingDate, String time, String tableType) {
        jdbcTemplate.update(
                """
                INSERT IGNORE INTO tb_booking_slot_inventory
                    (shop_id, booking_date, booking_time, table_type, capacity, booked_count)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                shopId,
                bookingDate,
                time,
                tableType,
                defaultSlotCapacity(tableType)
        );
    }

    private int defaultSlotCapacity(String tableType) {
        return switch (tableType) {
            case "private" -> 4;
            case "bar" -> 6;
            default -> 8;
        };
    }

    private String normalizeTableType(String tableType) {
        if (tableType == null || tableType.isBlank()) {
            return "normal";
        }
        return tableType;
    }
}
