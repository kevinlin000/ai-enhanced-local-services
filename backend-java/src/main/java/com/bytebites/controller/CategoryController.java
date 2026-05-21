package com.bytebites.controller;

import com.bytebites.domain.jpa.ShopJpa;
import com.bytebites.domain.jpa.ShopTypeJpa;
import com.bytebites.dto.Result;
import com.bytebites.repository.ShopJpaRepository;
import com.bytebites.repository.ShopTypeJpaRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

@RestController
@RequestMapping("/api/category")
public class CategoryController {

    private final ShopTypeJpaRepository shopTypeJpaRepository;
    private final ShopJpaRepository shopJpaRepository;

    public CategoryController(ShopTypeJpaRepository shopTypeJpaRepository, ShopJpaRepository shopJpaRepository) {
        this.shopTypeJpaRepository = shopTypeJpaRepository;
        this.shopJpaRepository = shopJpaRepository;
    }

    @GetMapping("/list")
    public Result listCategories() {
        List<ShopTypeJpa> activeTypes = shopTypeJpaRepository.findByIsActiveTrueOrderBySortAsc();
        List<CategoryView> categories = new ArrayList<>(activeTypes.size());
        for (ShopTypeJpa type : activeTypes) {
            categories.add(new CategoryView(
                    type.getId(),
                    type.getName(),
                    type.getIcon(),
                    type.getSlug(),
                    type.getSort()
            ));
        }
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
        Page<ShopJpa> result = shopJpaRepository.findByTypeId(typeId, PageRequest.of((int) page - 1, (int) size));
        return Result.ok(result.getContent(), result.getTotalElements());
    }

    @GetMapping("/{slug}/shops/popular")
    public Result listPopularCategoryShops(@PathVariable String slug) {
        Long typeId = findTypeIdBySlug(slug);
        if (typeId == null) {
            return Result.ok(Collections.emptyList());
        }
        List<ShopJpa> shops = shopJpaRepository.findByTypeIdAndScoreGreaterThanEqualOrderByScoreDesc(typeId, 45)
                .stream()
                .limit(5)
                .toList();
        return Result.ok(shops);
    }

    private Long findTypeIdBySlug(String slug) {
        return shopTypeJpaRepository.findBySlugAndIsActiveTrue(slug)
                .map(ShopTypeJpa::getId)
                .orElse(null);
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
