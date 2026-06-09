package com.bytebites.repository;

import com.bytebites.entity.jpa.BookingJpa;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface BookingJpaRepository extends JpaRepository<BookingJpa, Long> {

    Optional<BookingJpa> findByBookingCode(String bookingCode);

    Optional<BookingJpa> findByIdempotencyKey(String idempotencyKey);

    List<BookingJpa> findByUserIdOrderByCreatedAtDesc(Long userId);

    List<BookingJpa> findByUserIdInOrderByCreatedAtDesc(Collection<Long> userIds);

    List<BookingJpa> findTop50ByStatusAndHoldExpiresAtBeforeOrderByHoldExpiresAtAsc(
            Integer status,
            LocalDateTime cutoff
    );

    @Query(value = """
            SELECT *
            FROM tb_booking
            WHERE parking_reminder_enabled = 1
              AND parking_reminder_sent_at IS NULL
              AND status IN (2, 3)
              AND TIMESTAMP(booking_date, booking_time) BETWEEN :now AND :cutoff
            ORDER BY booking_date ASC, booking_time ASC
            LIMIT 50
            """, nativeQuery = true)
    List<BookingJpa> findUpcomingParkingReminderCandidates(
            @Param("now") LocalDateTime now,
            @Param("cutoff") LocalDateTime cutoff
    );
}
