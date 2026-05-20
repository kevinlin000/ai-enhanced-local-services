package com.hmdp;

import com.hmdp.entity.Shop;
import com.hmdp.service.impl.ShopServiceImpl;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.geo.Point;
import org.springframework.data.redis.connection.RedisGeoCommands;
import org.springframework.data.redis.core.StringRedisTemplate;

import jakarta.annotation.Resource;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@SpringBootTest
class HmDianPingApplicationTests {

    @Resource
    private ShopServiceImpl shopService;
    @Autowired
    private StringRedisTemplate stringRedisTemplate;

    @Test
    void testSaveShop() {
        // 1. 查詢資料庫中所有的店鋪資料
        List<Shop> shopList = shopService.list();

        // 2. 遍歷每一間店鋪，將它們逐一寫入 Redis 進行預熱
        // 這裡設定邏輯過期時間為 30 分鐘 (1800秒) 作為範例，你可以依需求調整
        for (Shop shop : shopList) {
            shopService.saveShop2redis(shop.getId(), 1800L);
        }

        System.out.println("全部店家快取預熱完成！共預熱了 " + shopList.size() + " 間店鋪。");
    }

    @Test
    void loadShopData(){
        // 1.查詢店家資訊
        List<Shop> list = shopService.list();
        // 2. 把店家分組，按雜後typeID分組
        Map<Long, List<Shop>> map = list.stream().collect(Collectors.groupingBy(Shop::getTypeId));
        //3.分批完成寫入redis
        for (Map.Entry<Long, List<Shop>> entry : map.entrySet()) {
            //3.1 獲取類型ID
            Long typeId = entry.getKey();
            String key = "shop:geo:" + typeId;
           //3.2 獲取同類型的店家的集合
            List<Shop> value = entry.getValue();
            List<RedisGeoCommands.GeoLocation<String>> locations = new ArrayList<>(value.size());
            //3.3 寫入redis GEOADD key  經度 緯度 member
            for (Shop shop : value) {
                //stringRedisTemplate.opsForGeo().add(key, new Point(shop.getX(), shop.getY()), shop.getId().toString());
                locations.add(new RedisGeoCommands.GeoLocation<>(
                        shop.getId().toString(),
                        new Point(shop.getX(), shop.getY())
                ));
            }
            stringRedisTemplate.opsForGeo().add(key,locations);

        }
    }

    @Test
    void testHyperLogLog(){
        String[] values = new String[1000];
        int j = 0;
        for (int i = 0; i < 1000000; i++) {
            j = i %1000;
            values[j] = "user_" + i;
            if(j == 999){
                stringRedisTemplate.opsForHyperLogLog().add("hl2", values);
            }
        }
        // 統計數量
        long count = stringRedisTemplate.opsForHyperLogLog().size("hl2");
        System.out.println("count =  " + count);
     }
}