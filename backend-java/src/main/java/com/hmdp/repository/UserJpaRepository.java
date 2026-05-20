package com.hmdp.repository;

import com.hmdp.domain.jpa.UserJpa;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface UserJpaRepository extends JpaRepository<UserJpa, Long> {

    Optional<UserJpa> findByLineUserId(String lineUserId);

    Optional<UserJpa> findByPhone(String phone);
}
