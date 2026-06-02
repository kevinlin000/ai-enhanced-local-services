package com.bytebites.service;

import com.bytebites.dto.Result;
import com.bytebites.dto.UserDTO;
import com.bytebites.utils.UserHolder;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.Map;

@Service
@RequiredArgsConstructor
public class ShopFavoriteService {
    private static final String STATUS_ACTIVE = "ACTIVE";
    private static final String STATUS_REMOVED = "REMOVED";

    private final JdbcTemplate jdbcTemplate;

    public Result myFavorites() {
        Long userId = currentUserIdOrNull();
        if (userId == null) return Result.fail("請先登入或使用 demo mode");
        return Result.ok(jdbcTemplate.queryForList(
                """
                SELECT f.id, f.shop_id AS shopId, f.updated_at AS favoritedAt,
                       s.name, s.type_id AS typeId, s.images, s.area, s.address,
                       s.avg_price AS avgPrice, s.score, s.comments, s.district,
                       s.mrt_station AS mrtStation, s.price_range AS priceRange,
                       s.business_hours AS businessHours
                FROM tb_shop_favorite f
                JOIN tb_shop s ON s.id = f.shop_id
                WHERE f.user_id = ? AND f.status = ?
                ORDER BY f.updated_at DESC
                LIMIT 100
                """,
                userId,
                STATUS_ACTIVE
        ));
    }

    public Result status(Long shopId) {
        Long userId = currentUserIdOrNull();
        if (userId == null) return Result.fail("請先登入或使用 demo mode");
        if (shopId == null) return Result.fail("shopId 必填");
        Integer count = jdbcTemplate.queryForObject(
                """
                SELECT COUNT(*)
                FROM tb_shop_favorite
                WHERE user_id = ? AND shop_id = ? AND status = ?
                """,
                Integer.class,
                userId,
                shopId,
                STATUS_ACTIVE
        );
        return Result.ok(Map.of(
                "shopId", shopId,
                "favorited", count != null && count > 0
        ));
    }

    public Result save(Long shopId) {
        Long userId = currentUserIdOrNull();
        if (userId == null) return Result.fail("請先登入或使用 demo mode");
        if (shopId == null) return Result.fail("shopId 必填");
        if (!shopExists(shopId)) return Result.fail("店家不存在");
        jdbcTemplate.update(
                """
                INSERT INTO tb_shop_favorite (user_id, shop_id, status)
                VALUES (?, ?, ?)
                ON DUPLICATE KEY UPDATE
                    status = VALUES(status),
                    updated_at = CURRENT_TIMESTAMP
                """,
                userId,
                shopId,
                STATUS_ACTIVE
        );
        return Result.ok(Map.of("shopId", shopId, "favorited", true));
    }

    public Result remove(Long shopId) {
        Long userId = currentUserIdOrNull();
        if (userId == null) return Result.fail("請先登入或使用 demo mode");
        if (shopId == null) return Result.fail("shopId 必填");
        int updated = jdbcTemplate.update(
                """
                UPDATE tb_shop_favorite
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND shop_id = ? AND status = ?
                """,
                STATUS_REMOVED,
                userId,
                shopId,
                STATUS_ACTIVE
        );
        if (updated == 0) {
            return Result.ok(Map.of("shopId", shopId, "favorited", false));
        }
        return Result.ok(Map.of("shopId", shopId, "favorited", false));
    }

    private boolean shopExists(Long shopId) {
        Integer count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM tb_shop WHERE id = ?",
                Integer.class,
                shopId
        );
        return count != null && count > 0;
    }

    private Long currentUserIdOrNull() {
        UserDTO user = UserHolder.getUser();
        return user != null ? user.getId() : null;
    }
}
