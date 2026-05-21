package com.hmdp.repository;

import com.hmdp.domain.jpa.VoucherJpa;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface VoucherJpaRepository extends JpaRepository<VoucherJpa, Long> {

    List<VoucherJpa> findByShopIdAndStatus(Long shopId, Integer status);
}
