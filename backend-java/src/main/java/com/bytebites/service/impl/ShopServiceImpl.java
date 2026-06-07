package com.bytebites.service.impl;

import cn.hutool.core.util.StrUtil;
import com.github.benmanes.caffeine.cache.Cache;
import cn.hutool.json.JSONUtil;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bytebites.annotation.DistributedLock;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.bytebites.dto.Result;
import com.bytebites.entity.Shop;
import com.bytebites.enums.LockType;
import com.bytebites.mapper.ShopMapper;
import com.bytebites.service.IShopService;
import com.bytebites.utils.CacheClient;
import com.bytebites.utils.RedisConstants;
import com.bytebites.utils.RedisData;
import com.bytebites.utils.SystemConstants;
import org.redisson.api.RBloomFilter;
import org.springframework.data.geo.Distance;
import org.springframework.data.geo.GeoResult;
import org.springframework.data.geo.GeoResults;
import org.springframework.data.redis.connection.RedisGeoCommands;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.domain.geo.GeoReference;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;

import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import static com.bytebites.utils.RedisConstants.*;

/**
 * <p>
 *  服务实现类
 * </p>
 *
 * @author 虎哥
 * @since 2021-12-22
 */
@Slf4j
@Service
public class ShopServiceImpl extends ServiceImpl<ShopMapper, Shop> implements IShopService {

    private static final String NULL_CACHE_VALUE = "__NULL__";
    private static final long NULL_CACHE_TTL_SECONDS = 60L;

    @Resource
    private StringRedisTemplate stringRedisTemplate;

    @Resource
    private CacheClient cacheClient;

    @Resource
    private Cache<Long, Shop> shopLocalCache;

    @Resource
    private RBloomFilter<Long> shopBloomFilter;

    @Override
    @DistributedLock(key = "shop:#id", type = LockType.READ, waitSeconds = 3, leaseSeconds = 10)
    public Result queryById(Long id) {
        Shop localShop = shopLocalCache.getIfPresent(id);
        if (localShop != null) {
            log.debug("cache path: caffeine hit, id={}", id);
            return Result.ok(localShop);
        }

        if (!shopBloomFilter.contains(id)) {
            log.debug("cache path: bloom missed, fallback db, id={}", id);
            Shop fallbackShop = getById(id);
            if (fallbackShop == null) {
                return Result.fail("店家不存在！");
            }
            shopBloomFilter.add(id);
            String fallbackKey = CACHE_SHOP_KEY + id;
            stringRedisTemplate.opsForValue().set(fallbackKey, JSONUtil.toJsonStr(fallbackShop), CACHE_SHOP_TTL, TimeUnit.MINUTES);
            shopLocalCache.put(id, fallbackShop);
            return Result.ok(fallbackShop);
        }

        String key = CACHE_SHOP_KEY + id;
        String cacheValue = stringRedisTemplate.opsForValue().get(key);
        if (NULL_CACHE_VALUE.equals(cacheValue) || (cacheValue != null && cacheValue.isBlank())) {
            log.debug("cache path: redis null cached, id={}", id);
            return Result.fail("店家不存在！");
        }
        if (StrUtil.isNotBlank(cacheValue)) {
            log.debug("cache path: redis hit, id={}", id);
            Shop cachedShop = decodeCachedShop(cacheValue);
            if (cachedShop != null && cachedShop.getId() != null) {
                shopLocalCache.put(id, cachedShop);
                return Result.ok(cachedShop);
            }
            log.warn("cache path: invalid shop cache, delete and fallback db, id={}", id);
            stringRedisTemplate.delete(key);
        }

        Shop shop = getById(id);
        if (shop == null) {
            log.debug("cache path: db miss, cache null, id={}", id);
            stringRedisTemplate.opsForValue().set(key, NULL_CACHE_VALUE, NULL_CACHE_TTL_SECONDS, TimeUnit.SECONDS);
            return Result.fail("店家不存在！");
        }

        log.debug("cache path: db hit, id={}", id);
        stringRedisTemplate.opsForValue().set(key, JSONUtil.toJsonStr(shop), CACHE_SHOP_TTL, TimeUnit.MINUTES);
        shopLocalCache.put(id, shop);
        return Result.ok(shop);
    }

    private Shop decodeCachedShop(String cacheValue) {
        try {
            Shop direct = JSONUtil.toBean(cacheValue, Shop.class);
            if (direct != null && direct.getId() != null) {
                return direct;
            }

            Object data = JSONUtil.parseObj(cacheValue).get("data");
            if (data != null) {
                Shop nested = JSONUtil.toBean(JSONUtil.toJsonStr(data), Shop.class);
                if (nested != null && nested.getId() != null) {
                    return nested;
                }
            }
        } catch (Exception e) {
            log.warn("failed to decode shop cache", e);
        }
        return null;
    }

    /**
     * @deprecated TODO C1 後續清理：舊版邏輯過期 / 穿透回退流程保留作為對照，不再作為主查詢路徑。
     */
    @Deprecated
    private Shop queryByIdWithLegacyCache(Long id) {
        Shop shop = cacheClient
                .queryWithLogicalExpire(CACHE_SHOP_KEY, id, Shop.class, this::getById, CACHE_SHOP_TTL, TimeUnit.MINUTES);
        if (shop == null) {
            shop = cacheClient
                    .queryWithPassThrough(CACHE_SHOP_KEY, id, Shop.class, this::getById, CACHE_SHOP_TTL, TimeUnit.MINUTES);
        }
        return shop;
    }

    private static final ExecutorService CACHE_REBUILD_EXECUTOR = Executors.newFixedThreadPool(10);

    public void saveShop2redis(Long id, Long expireSeconds){
        //1.查詢店家數據
        Shop shop = getById(id);
        //2.封裝成邏輯過期時間
        RedisData redisData = new RedisData();
        redisData.setData(shop);
        redisData.setExpireTime(LocalDateTime.now().plusSeconds(expireSeconds));
        //3.寫入redis
        stringRedisTemplate.opsForValue().set(CACHE_SHOP_KEY + id, JSONUtil.toJsonStr(redisData));
    }

    @Override
    @Transactional
    @DistributedLock(key = "shop:#shop.id", type = LockType.WRITE, waitSeconds = 3, leaseSeconds = 10)
    public Result update(Shop shop) {
        Long id =shop.getId();
        if (id == null) {
            return Result.fail("店家id不能為空！");
        }
        //1. 更新資料庫
        updateById(shop);
        //2. 刪除緩存
        stringRedisTemplate.delete(CACHE_SHOP_KEY + shop.getId());
        return Result.ok();
    }

    @Override
    public Result queryShopByType(Integer typeId, Integer current, Double x, Double y) {
        // 1. 判斷是否需要根據座標查詢
        if (x == null || y == null) {
            // 不需要座標查詢，按照資料庫查
            Page<Shop> page = query()
                    .eq("type_id", typeId)
                    .page(new Page<>(current, SystemConstants.DEFAULT_PAGE_SIZE));
            // 返回數據
            return Result.ok(page.getRecords());
        }
        // 2. 計算分頁參數
            int from = (current - 1) * SystemConstants.DEFAULT_PAGE_SIZE;
            int end = current * SystemConstants.DEFAULT_PAGE_SIZE;
        // 3. 根據typeId和分頁參數查詢redis，結果按照距離排序
        String key = SHOP_GEO_KEY + typeId;
        GeoResults<RedisGeoCommands.GeoLocation<String>> results = stringRedisTemplate.opsForGeo()
                .search(
                        key, GeoReference.fromCoordinate(x, y),
                        new Distance(5000),   // 查詢半徑5公里;
                        RedisGeoCommands.GeoSearchCommandArgs.newGeoSearchArgs().includeDistance().limit(end));
        // 4. 解析出id，距離等資訊
        if (results == null ) {
            // 沒有查詢到任何店鋪
            return Result.ok(Collections.emptyList());
        }
        List<GeoResult<RedisGeoCommands.GeoLocation<String>>> list = results.getContent();

        if (list.size() <= from) {
            return Result.ok(Collections.emptyList());
        }
        // 4.1 截取from 到 end 的部分
        List<Long> ids = new ArrayList<>(list.size());
        Map<String, Distance> distanceMap = new HashMap<>(list.size());
        list.stream().skip(from).forEach(result -> {
                    String shopIdStr = result.getContent().getName();
                    ids.add(Long.valueOf(shopIdStr));
                    // 獲取距離
                    Distance distance = result.getDistance();
                    distanceMap.put(shopIdStr, distance);
                });
        // 5. 根據id從資料庫查詢店家資訊
        String idStr = StrUtil.join(",", ids);
        List<Shop> shops = query().in("id", ids).last("ORDER BY FIELD(id," + idStr + ")").list();
        for (Shop shop : shops) {
            shop.setDistance(distanceMap.get(shop.getId().toString()).getValue());
        }
            // 6. 返回
            return Result.ok(shops);
    }
}
