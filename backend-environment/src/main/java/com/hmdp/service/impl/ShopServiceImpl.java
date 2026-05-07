package com.hmdp.service.impl;

import cn.hutool.core.util.BooleanUtil;
import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.hmdp.dto.Result;
import com.hmdp.entity.Shop;
import com.hmdp.mapper.ShopMapper;
import com.hmdp.service.IShopService;
import com.hmdp.utils.CacheClient;
import com.hmdp.utils.RedisConstants;
import com.hmdp.utils.RedisData;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import javax.annotation.Resource;

import java.time.LocalDateTime;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import static com.hmdp.utils.RedisConstants.*;

/**
 * <p>
 *  服务实现类
 * </p>
 *
 * @author 虎哥
 * @since 2021-12-22
 */
@Service
public class ShopServiceImpl extends ServiceImpl<ShopMapper, Shop> implements IShopService {


    @Resource
    private StringRedisTemplate stringRedisTemplate;

    @Resource
    private CacheClient cacheClient;

    @Override
    public Result queryById(Long id) {
        //緩存穿透
        //Shop shop = cacheClient
        //        .queryWithPassThrough(CACHE_SHOP_KEY, id, Shop.class, this::getById, CACHE_SHOP_TTL, TimeUnit.MINUTES);

        // 互斥鎖解決緩存擊穿
        //Shop shop = queryWithMutex(id);
        // 邏輯過期來解決緩存擊穿
        Shop shop = cacheClient
                .queryWithLogicalExpire(CACHE_SHOP_KEY, id, Shop.class, this::getById, CACHE_SHOP_TTL, TimeUnit.MINUTES);

        if (shop == null) {
            return Result.fail("店家不存在！");
        }
        //7.返回
        return Result.ok(shop);
    }

    private static final ExecutorService CACHE_REBUILD_EXECUTOR = Executors.newFixedThreadPool(10);

//    public Shop queryWithLogicalExpire (Long id){
//        String key = CACHE_SHOP_KEY + id;
//        //1.從redis查詢商家緩存
//        String shopJson = stringRedisTemplate.opsForValue().get(key);
//
//        //2.判斷是否存在
//        if (StrUtil.isBlank(shopJson)) {
//            //3.存在，直接返回
//            return  null;
//        }
//        //4.命中，需要先把json反序列化為對象
//        RedisData redisData = JSONUtil.toBean(shopJson, RedisData.class);
//        Shop shop = JSONUtil.toBean((JSONObject) redisData.getData(), Shop.class);
//        LocalDateTime expireTime = redisData.getExpireTime();
//        //5. 判斷是否過期
//        if (expireTime.isAfter(LocalDateTime.now())) {
//            //5.1 未過期，直接返回店家資訊
//            return shop;
//        }
//
//        //5.2 已過期，需要緩存重建
//        //6. 緩存重建
//        //6.1 獲取互斥鎖
//        String  lockKey = LOCK_SHOP_KEY + id;
//        boolean isLock = tryLock(lockKey);
//        //6.2 判斷是否獲取成功
//        if (isLock) {
//            //6.3 成功，則開啟獨立線程，實現緩存重建
//            CACHE_REBUILD_EXECUTOR.submit(() -> {
//                try {
//                    //重建緩存
//                    this.saveShop2redis(id, CACHE_SHOP_TTL);
//                } catch (Exception e) {
//                    throw new RuntimeException(e);
//                } finally {
//                    //釋放鎖
//                    unLock(lockKey);
//                }
//            });
//        }
//        //6.4 失敗，則返回過期的店家資訊
//        return shop;
//    }

//    public Shop queryWithMutex(Long id){
//        String key = CACHE_SHOP_KEY + id;
//        //1.從redis查詢商家緩存
//        String shopJson = stringRedisTemplate.opsForValue().get(key);
//
//        //2.判斷是否存在
//        if (StrUtil.isNotBlank(shopJson)) {
//            //3.存在，直接返回
//            return  JSONUtil.toBean(shopJson, Shop.class);
//        }
//
//        //判斷命中的是否是空值
//        if(shopJson != null){
//            //返回一個錯誤資訊
//            return null;
//        }
//        // 4.實現緩存重建
//        //4.1 獲取互斥鎖
//        String  lockKey = LOCK_SHOP_KEY + id;
//        Shop shop = null;
//        try {
//            boolean isLock = tryLock(lockKey);
//            //4.2 判斷是否獲取成功
//            if(!isLock){
//                //4.3 失敗，則休眠並重試
//                Thread.sleep(50);
//                return queryWithMutex(id);
//            }
//
//            //4.4 成功，根據id查詢數據庫
//            shop = getById(id);
//            //5.不存在，返回錯誤
//            if (shop == null) {
//                //將空值寫入redis
//                stringRedisTemplate.opsForValue().set(key, "", CACHE_NULL_TTL, TimeUnit.MINUTES);
//                //返回錯誤資訊
//                return null;
//            }
//            //6. 存在，寫入redis
//            stringRedisTemplate.opsForValue().set(key, JSONUtil.toJsonStr(shop), CACHE_SHOP_TTL, TimeUnit.MINUTES);
//        } catch (InterruptedException e) {
//            throw new RuntimeException(e);
//        }finally {
//            //7.釋放互斥鎖
//            unLock(lockKey);
//        }
//        //8.返回
//        return shop;
//    }

//    public Shop queryWithPassThrough(Long id){
//        String key = CACHE_SHOP_KEY + id;
//        //1.從redis查詢商家緩存
//        String shopJson = stringRedisTemplate.opsForValue().get(key);
//
//        //2.判斷是否存在
//        if (StrUtil.isNotBlank(shopJson)) {
//            //3.存在，直接返回
//            return  JSONUtil.toBean(shopJson, Shop.class);
//        }
//
//        //判斷命中的是否是空值
//        if(shopJson != null){
//            //返回一個錯誤資訊
//            return null;
//        }
//        //4.不存在，根據id查詢數據庫
//        Shop shop = getById(id);
//        //5.不存在，返回錯誤
//        if (shop == null) {
//            //將空值寫入redis
//            stringRedisTemplate.opsForValue().set(key, "", CACHE_NULL_TTL, TimeUnit.MINUTES);
//            //返回錯誤資訊
//            return null;
//        }
//        //6. 存在，寫入redis
//        stringRedisTemplate.opsForValue().set(key, JSONUtil.toJsonStr(shop), CACHE_SHOP_TTL, TimeUnit.MINUTES);
//        //7.返回
//        return shop;
//    }

//    private boolean tryLock(String key) {
//        Boolean flag = stringRedisTemplate.opsForValue().setIfAbsent(key, "1", LOCK_SHOP_TTL, TimeUnit.SECONDS);
//        return BooleanUtil.isTrue(flag);
//    }
//
//     private void unLock(String key) {
//        stringRedisTemplate.delete(key);
//    }

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
}
