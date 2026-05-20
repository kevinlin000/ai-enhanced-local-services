package com.hmdp.repository;

import com.hmdp.domain.jpa.ShopTypeJpa;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface ShopTypeJpaRepository extends JpaRepository<ShopTypeJpa, Long> {

    List<ShopTypeJpa> findByIsActiveTrueOrderBySortAsc();

    Optional<ShopTypeJpa> findBySlugAndIsActiveTrue(String slug);
}
