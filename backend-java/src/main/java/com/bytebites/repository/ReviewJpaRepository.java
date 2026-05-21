package com.bytebites.repository;

import com.bytebites.domain.jpa.ReviewJpa;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface ReviewJpaRepository extends JpaRepository<ReviewJpa, Long> {

    Page<ReviewJpa> findByShopIdOrderByCreateTimeDesc(Long shopId, Pageable pageable);

    List<ReviewJpa> findByShopIdAndAiSummaryIsNull(Long shopId);

    long countByShopId(Long shopId);
}
