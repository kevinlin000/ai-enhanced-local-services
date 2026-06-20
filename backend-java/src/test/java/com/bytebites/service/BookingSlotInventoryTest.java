package com.bytebites.service;

import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class BookingSlotInventoryTest {
    private static final Long SHOP_ID = 10009L;
    private static final LocalDate BOOKING_DATE = LocalDate.of(2026, 6, 20);

    @Test
    void reserveCreatesSlotWithDefaultCapacityAndAtomicallyReserves() {
        RecordingJdbcTemplate jdbcTemplate = new RecordingJdbcTemplate(1);
        BookingSlotInventory inventory = new BookingSlotInventory(jdbcTemplate);

        boolean reserved = inventory.reserve(SHOP_ID, BOOKING_DATE, "19:00", "normal", 4);

        assertThat(reserved).isTrue();
        assertThat(jdbcTemplate.calls).hasSize(2);
        assertThat(jdbcTemplate.calls.get(0).sql()).contains("INSERT IGNORE INTO tb_booking_slot_inventory");
        assertThat(jdbcTemplate.calls.get(0).args())
                .containsExactly(SHOP_ID, BOOKING_DATE, "19:00", "normal", 8);
        assertThat(jdbcTemplate.calls.get(1).sql()).contains("UPDATE tb_booking_slot_inventory");
        assertThat(jdbcTemplate.calls.get(1).args())
                .containsExactly(4, SHOP_ID, BOOKING_DATE, "19:00", "normal", 4);
    }

    @Test
    void reserveNormalizesBlankTableType() {
        RecordingJdbcTemplate jdbcTemplate = new RecordingJdbcTemplate(1);
        BookingSlotInventory inventory = new BookingSlotInventory(jdbcTemplate);

        boolean reserved = inventory.reserve(SHOP_ID, BOOKING_DATE, "20:00", " ", 2);

        assertThat(reserved).isTrue();
        assertThat(jdbcTemplate.calls.get(0).args())
                .containsExactly(SHOP_ID, BOOKING_DATE, "20:00", "normal", 8);
        assertThat(jdbcTemplate.calls.get(1).args())
                .containsExactly(2, SHOP_ID, BOOKING_DATE, "20:00", "normal", 2);
    }

    @Test
    void reserveReturnsFalseWhenAtomicUpdateMissesCapacity() {
        RecordingJdbcTemplate jdbcTemplate = new RecordingJdbcTemplate(0);
        BookingSlotInventory inventory = new BookingSlotInventory(jdbcTemplate);

        boolean reserved = inventory.reserve(SHOP_ID, BOOKING_DATE, "19:00", "private", 5);

        assertThat(reserved).isFalse();
        assertThat(jdbcTemplate.calls.get(0).args())
                .containsExactly(SHOP_ID, BOOKING_DATE, "19:00", "private", 4);
        assertThat(jdbcTemplate.calls.get(1).args())
                .containsExactly(5, SHOP_ID, BOOKING_DATE, "19:00", "private", 5);
    }

    @Test
    void releaseNeverDropsBookedCountBelowZeroAndNormalizesTableType() {
        RecordingJdbcTemplate jdbcTemplate = new RecordingJdbcTemplate(1);
        BookingSlotInventory inventory = new BookingSlotInventory(jdbcTemplate);

        inventory.release(SHOP_ID, BOOKING_DATE, "21:00", null, 3);

        assertThat(jdbcTemplate.calls).hasSize(1);
        assertThat(jdbcTemplate.calls.get(0).sql()).contains("GREATEST(booked_count - ?, 0)");
        assertThat(jdbcTemplate.calls.get(0).args())
                .containsExactly(3, SHOP_ID, BOOKING_DATE, "21:00", "normal");
    }

    private static class RecordingJdbcTemplate extends JdbcTemplate {
        private final int updateResult;
        private final List<SqlCall> calls = new ArrayList<>();

        private RecordingJdbcTemplate(int updateResult) {
            this.updateResult = updateResult;
        }

        @Override
        public int update(String sql, Object... args) {
            calls.add(new SqlCall(sql, Arrays.asList(args)));
            return sql.contains("UPDATE tb_booking_slot_inventory") ? updateResult : 1;
        }
    }

    private record SqlCall(String sql, List<Object> args) {
    }
}
