package com.bytebites.controller;

import com.bytebites.dto.Result;
import com.bytebites.service.ShopFavoriteService;
import lombok.RequiredArgsConstructor;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

@RequiredArgsConstructor
@RestController
@RequestMapping({"/favorites", "/api/favorites"})
public class FavoriteController {
    private final ShopFavoriteService favorites;

    @GetMapping("/shops")
    public Result myFavorites() {
        return favorites.myFavorites();
    }

    @GetMapping("/shops/{shopId}")
    public Result status(@PathVariable Long shopId) {
        return favorites.status(shopId);
    }

    @PostMapping("/shops/{shopId}")
    @Transactional
    public Result save(@PathVariable Long shopId) {
        return favorites.save(shopId);
    }

    @DeleteMapping("/shops/{shopId}")
    @Transactional
    public Result remove(@PathVariable Long shopId) {
        return favorites.remove(shopId);
    }
}
