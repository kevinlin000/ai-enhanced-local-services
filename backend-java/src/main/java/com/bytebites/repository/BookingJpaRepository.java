package com.bytebites.repository;

import com.bytebites.entity.jpa.BookingJpa;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface BookingJpaRepository extends JpaRepository<BookingJpa, Long> {

    Optional<BookingJpa> findByBookingCode(String bookingCode);
}
