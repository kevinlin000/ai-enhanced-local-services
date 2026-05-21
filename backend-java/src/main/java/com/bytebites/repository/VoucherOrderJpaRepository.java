package com.bytebites.repository;

import com.bytebites.domain.jpa.VoucherOrderJpa;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface VoucherOrderJpaRepository extends JpaRepository<VoucherOrderJpa, Long> {
    Page<VoucherOrderJpa> findByUserIdOrderByCreateTimeDesc(Long userId, Pageable pageable);

    List<VoucherOrderJpa> findByUserIdAndStatus(Long userId, Integer status);

    Optional<VoucherOrderJpa> findByUserIdAndVoucherId(Long userId, Long voucherId);
}
