package com.bytebites.service.jpa;

import com.bytebites.domain.jpa.UserJpa;
import com.bytebites.repository.UserJpaRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Optional;

@Service
public class UserJpaService {

    private final UserJpaRepository repo;

    public UserJpaService(UserJpaRepository repo) {
        this.repo = repo;
    }

    public Optional<UserJpa> findByLineId(String lineUserId) {
        return repo.findByLineUserId(lineUserId);
    }

    @Transactional
    public UserJpa save(UserJpa user) {
        return repo.save(user);
    }
}
