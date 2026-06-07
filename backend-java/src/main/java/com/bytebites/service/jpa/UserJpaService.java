package com.bytebites.service.jpa;

import com.bytebites.domain.jpa.UserJpa;
import com.bytebites.repository.UserJpaRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.util.Optional;
import java.util.UUID;

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
    public UserJpa findOrCreateLineUser(String lineUserId) {
        String normalized = lineUserId == null ? "" : lineUserId.trim();
        if (normalized.isBlank() || normalized.length() > 128) {
            throw new IllegalArgumentException("lineUserId is required");
        }
        return repo.findByLineUserId(normalized).orElseGet(() -> {
            UserJpa user = new UserJpa();
            user.setLineUserId(normalized);
            user.setLineDisplayName("LINE Bot User");
            user.setNickName("LINE Bot User");
            user.setPhone(linePlaceholderPhone(normalized));
            return repo.save(user);
        });
    }

    public String linePlaceholderPhone(String lineUserId) {
        String normalized = lineUserId == null ? "" : lineUserId.trim();
        String hash = UUID.nameUUIDFromBytes(normalized.getBytes(StandardCharsets.UTF_8))
                .toString()
                .replace("-", "")
                .substring(0, 10);
        return "L" + hash;
    }

    public Optional<UserJpa> findById(Long id) {
        return repo.findById(id);
    }

    @Transactional
    public UserJpa save(UserJpa user) {
        return repo.save(user);
    }
}
