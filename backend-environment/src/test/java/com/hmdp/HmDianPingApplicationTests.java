package com.hmdp;

import com.hmdp.service.impl.ShopServiceImpl;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import javax.annotation.Resource;

@SpringBootTest
class HmDianPingApplicationTests {

    @Resource
    private ShopServiceImpl shopService;

    @Test
    void testSaveShop() {
        // 手動把 ID 為 1 的店鋪資料寫入 Redis，並設定邏輯過期時間為 10 秒
        // (你可以把 1 改成你在前端點擊的那個店鋪 ID)
        shopService.saveShop2redis(1L, 10L);
        System.out.println("快取預熱完成！");
    }
}