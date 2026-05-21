package com.bytebites.repository;

import com.bytebites.domain.jpa.ShopJpa;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface ShopJpaRepository extends JpaRepository<ShopJpa, Long> {

    Page<ShopJpa> findByTypeId(Long typeId, Pageable pageable);

    List<ShopJpa> findByTypeIdAndScoreGreaterThanEqualOrderByScoreDesc(Long typeId, Integer minScore);

    List<ShopJpa> findByMrtStation(String mrtStation);
}
