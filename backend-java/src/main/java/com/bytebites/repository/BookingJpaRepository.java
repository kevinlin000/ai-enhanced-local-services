package com.bytebites.repository;

import com.bytebites.entity.jpa.BookingJpa;
import org.springframework.data.jpa.repository.JpaRepository;

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
}
