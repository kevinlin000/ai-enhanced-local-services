package com.hmdp.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.hmdp.dto.Result;
import com.hmdp.entity.Shop;
import com.hmdp.service.IShopService;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Collections;
import java.util.List;

@RestController
@RequestMapping("/api/category")
public class CategoryController {

    private final JdbcTemplate jdbcTemplate;
    private final IShopService shopService;

    public CategoryController(JdbcTemplate jdbcTemplate, IShopService shopService) {
        this.jdbcTemplate = jdbcTemplate;
        this.shopService = shopService;
    }

    @GetMapping("/list")
    public Result listCategories() {
        List<CategoryView> categories = jdbcTemplate.query(
                """
                SELECT id, name, icon, slug, sort
                FROM tb_shop_type
                WHERE is_active = 1 AND id BETWEEN 1001 AND 1012
                ORDER BY sort, id
                """,
                (rs, rowNum) -> new CategoryView(
                        rs.getLong("id"),
                        rs.getString("name"),
                        rs.getString("icon"),
                        rs.getString("slug"),
                        rs.getInt("sort")
                )
        );
        return Result.ok(categories);
    }

    @GetMapping("/{slug}/shops")
    public Result listCategoryShops(
            @PathVariable String slug,
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "10") long size
    ) {
        Long typeId = findTypeIdBySlug(slug);
        if (typeId == null) {
            return Result.ok(Collections.emptyList(), 0L);
        }
        Page<Shop> result = shopService.query()
                .eq("type_id", typeId)
                .page(new Page<>(page, size));
        return Result.ok(result.getRecords(), result.getTotal());
    }

    @GetMapping("/{slug}/shops/popular")
    public Result listPopularCategoryShops(@PathVariable String slug) {
        Long typeId = findTypeIdBySlug(slug);
        if (typeId == null) {
            return Result.ok(Collections.emptyList());
        }
        List<Shop> shops = shopService.query()
                .eq("type_id", typeId)
                .ge("score", 45)
                .orderByDesc("score")
                .orderByDesc("comments")
                .last("LIMIT 5")
                .list();
        return Result.ok(shops);
    }

    private Long findTypeIdBySlug(String slug) {
        List<Long> ids = jdbcTemplate.query(
                "SELECT id FROM tb_shop_type WHERE slug = ? AND is_active = 1 LIMIT 1",
                (rs, rowNum) -> rs.getLong("id"),
                slug
        );
        return ids.isEmpty() ? null : ids.get(0);
    }

    public static class CategoryView {
        private final Long id;
        private final String name;
        private final String icon;
        private final String slug;
        private final Integer sort;

        public CategoryView(Long id, String name, String icon, String slug, Integer sort) {
            this.id = id;
            this.name = name;
            this.icon = icon;
            this.slug = slug;
            this.sort = sort;
        }

        public Long getId() {
            return id;
        }

        public String getName() {
            return name;
        }

        public String getIcon() {
            return icon;
        }

        public String getSlug() {
            return slug;
        }

        public Integer getSort() {
            return sort;
        }
    }
}
