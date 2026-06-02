package com.bytebites.service;

import com.bytebites.entity.jpa.BookingJpa;
import com.bytebites.repository.BookingJpaRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Slf4j
@Service
@RequiredArgsConstructor
public class BookingHoldService {
    public static final int STATUS_PENDING_PAYMENT = 1;
    public static final int STATUS_PAID = 2;
    public static final int STATUS_CONFIRMED = 3;
    public static final int STATUS_CANCELED = 4;
    public static final int STATUS_EXPIRED = 5;

    public static final int HOLD_MINUTES = 10;

    private final BookingJpaRepository bookingRepo;
    private final JdbcTemplate jdbcTemplate;

    public LocalDateTime newHoldExpiry() {
        return LocalDateTime.now().plusMinutes(HOLD_MINUTES);
    }

    public boolean isExpired(BookingJpa booking) {
        return booking.getStatus() == STATUS_PENDING_PAYMENT
                && booking.getHoldExpiresAt() != null
                && !booking.getHoldExpiresAt().isAfter(LocalDateTime.now());
    }

    /**
     * Expire a pending hold once. Safe to call from payment/cancel/list/job paths.
     */
    @Transactional
    public boolean expireIfDue(BookingJpa booking) {
        if (!isExpired(booking)) return false;

        releaseSlotCapacity(
                booking.getShopId(),
                booking.getBookingDate().toString(),
                booking.getBookingTime(),
                booking.getTableType(),
                booking.getPeople()
        );
        booking.setStatus(STATUS_EXPIRED);
        bookingRepo.saveAndFlush(booking);

        log.info("[Booking hold expired] code={} shop={} people={} date={} time={}",
                booking.getBookingCode(), booking.getShopId(), booking.getPeople(),
                booking.getBookingDate(), booking.getBookingTime());
        return true;
    }

    @Scheduled(fixedDelay = 60_000, initialDelay = 30_000)
    @Transactional
    public void expireDueHolds() {
        var expired = bookingRepo.findTop50ByStatusAndHoldExpiresAtBeforeOrderByHoldExpiresAtAsc(
                STATUS_PENDING_PAYMENT,
                LocalDateTime.now()
        );
        for (BookingJpa booking : expired) {
            expireIfDue(booking);
        }
    }

    private void releaseSlotCapacity(Long shopId, String bookingDate, String time, String tableType, int people) {
        jdbcTemplate.update(
                """
                UPDATE tb_booking_slot_inventory
                SET booked_count = GREATEST(booked_count - ?, 0)
                WHERE shop_id = ? AND booking_date = ? AND booking_time = ? AND table_type = ?
                """,
                people, shopId, bookingDate, time, tableType
        );
    }
}
