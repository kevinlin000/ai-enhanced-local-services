package com.hmdp;

import com.hmdp.entity.Shop;
import com.hmdp.service.impl.ShopServiceImpl;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

import javax.annotation.Resource;
import java.util.List;

@SpringBootTest
class HmDianPingApplicationTests {

    @Resource
    private ShopServiceImpl shopService;

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
}