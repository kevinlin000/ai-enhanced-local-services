package com.bytebites.service.jpa;

import com.bytebites.domain.jpa.UserJpa;
import com.bytebites.repository.UserJpaRepository;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Service
public class UserJpaService {

    private final UserJpaRepository repo;
    private final JdbcTemplate jdbcTemplate;

    public UserJpaService(UserJpaRepository repo, JdbcTemplate jdbcTemplate) {
        this.repo = repo;
        this.jdbcTemplate = jdbcTemplate;
    }

    public Optional<UserJpa> findByLineId(String lineUserId) {
        return repo.findByLineUserId(lineUserId);
    }

    @Transactional
    public UserJpa findOrCreateLineUser(String lineUserId) {
        return resolveLineIdentity(lineUserId, null);
    }

    @Transactional
    public UserJpa resolveLineIdentity(String lineUserId, String displayName) {
        return resolveLineIdentity(lineUserId, displayName, "line_bot");
    }

    @Transactional
    public UserJpa resolveLineLoginIdentity(String lineUserId, String displayName) {
        return resolveLineIdentity(lineUserId, displayName, "line_direct");
    }

    private UserJpa resolveLineIdentity(String lineUserId, String displayName, String source) {
        String normalized = lineUserId == null ? "" : lineUserId.trim();
        if (normalized.isBlank() || normalized.length() > 128) {
            throw new IllegalArgumentException("lineUserId is required");
        }

        Optional<UserJpa> linked = findLinkedUser(normalized);
        if (linked.isPresent()) {
            return linked.get();
        }

        UserJpa direct = repo.findByLineUserId(normalized).orElse(null);
        if ("line_direct".equals(source) && direct != null) {
            upsertLineIdentityLink(normalized, direct.getId(), displayName, source);
            updateDisplayNameIfPresent(direct, displayName);
            return direct;
        }

        Optional<UserJpa> displayMatched = findSingleDisplayNameMatch(displayName, direct == null ? null : direct.getId());
        if (displayMatched.isPresent()) {
            UserJpa matched = displayMatched.get();
            upsertLineIdentityLink(normalized, matched.getId(), displayName, source);
            if (direct != null && !direct.getId().equals(matched.getId()) && isLineBotPlaceholder(direct)) {
                migrateLineOwnedRows(direct.getId(), matched.getId());
            }
            return matched;
        }

        if (direct != null) {
            upsertLineIdentityLink(normalized, direct.getId(), displayName, source);
            updateDisplayNameIfPresent(direct, displayName);
            return direct;
        }

        UserJpa created = repo.findByLineUserId(normalized).orElseGet(() -> {
            UserJpa user = new UserJpa();
            user.setLineUserId(normalized);
            String name = normalizeDisplayName(displayName).orElse("LINE Bot User");
            user.setLineDisplayName(name);
            user.setNickName(name);
            user.setPhone(linePlaceholderPhone(normalized));
            return repo.save(user);
        });
        upsertLineIdentityLink(normalized, created.getId(), displayName, source);
        return created;
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

    public Optional<String> findLineNotificationUserId(Long userId) {
        if (userId == null) {
            return Optional.empty();
        }
        List<String> linkedLineUserIds = jdbcTemplate.queryForList(
                """
                SELECT line_user_id
                FROM tb_line_identity_link
                WHERE user_id = ?
                ORDER BY
                    CASE
                        WHEN source = 'line_bot' THEN 0
                        WHEN source = 'line_direct' THEN 1
                        ELSE 2
                    END,
                    update_time DESC,
                    id DESC
                LIMIT 1
                """,
                String.class,
                userId
        );
        if (!linkedLineUserIds.isEmpty()) {
            String lineUserId = linkedLineUserIds.get(0);
            if (lineUserId != null && !lineUserId.isBlank()) {
                return Optional.of(lineUserId.trim());
            }
        }
        return repo.findById(userId)
                .map(UserJpa::getLineUserId)
                .map(String::trim)
                .filter(lineUserId -> !lineUserId.isBlank());
    }

    @Transactional
    public UserJpa save(UserJpa user) {
        return repo.save(user);
    }

    private Optional<UserJpa> findLinkedUser(String lineUserId) {
        try {
            Long userId = jdbcTemplate.queryForObject(
                    "SELECT user_id FROM tb_line_identity_link WHERE line_user_id = ?",
                    Long.class,
                    lineUserId
            );
            return userId == null ? Optional.empty() : repo.findById(userId);
        } catch (EmptyResultDataAccessException ignored) {
            return Optional.empty();
        }
    }

    private Optional<UserJpa> findSingleDisplayNameMatch(String displayName, Long excludedUserId) {
        Optional<String> normalized = normalizeDisplayName(displayName);
        if (normalized.isEmpty()) {
            return Optional.empty();
        }
        List<Long> ids = jdbcTemplate.queryForList(
                """
                SELECT id
                FROM tb_user
                WHERE (line_display_name = ? OR nick_name = ?)
                  AND (? IS NULL OR id <> ?)
                ORDER BY update_time DESC, id DESC
                LIMIT 2
                """,
                Long.class,
                normalized.get(),
                normalized.get(),
                excludedUserId,
                excludedUserId
        );
        if (ids.size() != 1) {
            return Optional.empty();
        }
        return repo.findById(ids.get(0));
    }

    private void updateDisplayNameIfPresent(UserJpa user, String displayName) {
        normalizeDisplayName(displayName).ifPresent(name -> {
            user.setLineDisplayName(name);
            if (user.getNickName() == null || user.getNickName().isBlank() || isLineBotPlaceholder(user)) {
                user.setNickName(name);
            }
            repo.save(user);
        });
    }

    private Optional<String> normalizeDisplayName(String displayName) {
        String normalized = displayName == null ? "" : displayName.trim();
        if (normalized.isBlank() || "LINE Bot User".equals(normalized)) {
            return Optional.empty();
        }
        return Optional.of(normalized);
    }

    private boolean isLineBotPlaceholder(UserJpa user) {
        return "LINE Bot User".equals(user.getNickName()) || "LINE Bot User".equals(user.getLineDisplayName());
    }

    private void upsertLineIdentityLink(String lineUserId, Long userId, String displayName, String source) {
        jdbcTemplate.update(
                """
                INSERT INTO tb_line_identity_link (line_user_id, user_id, display_name, source)
                VALUES (?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE
                    user_id = VALUES(user_id),
                    display_name = VALUES(display_name),
                    source = VALUES(source),
                    update_time = CURRENT_TIMESTAMP
                """,
                lineUserId,
                userId,
                normalizeDisplayName(displayName).orElse(null),
                source
        );
    }

    private void migrateLineOwnedRows(Long fromUserId, Long toUserId) {
        jdbcTemplate.update("UPDATE tb_booking SET user_id = ? WHERE user_id = ?", toUserId, fromUserId);
        jdbcTemplate.update("UPDATE tb_availability_watch SET user_id = ? WHERE user_id = ?", toUserId, fromUserId);
    }
}
