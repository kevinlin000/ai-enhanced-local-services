package com.bytebites.controller;

import com.bytebites.annotation.RateLimit;
import com.bytebites.dto.Result;
import com.bytebites.service.IVoucherOrderService;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/flash-deals")
public class FlashDealController {

    private final IVoucherOrderService voucherOrderService;

    public FlashDealController(IVoucherOrderService voucherOrderService) {
        this.voucherOrderService = voucherOrderService;
    }

    @PostMapping("/{id}/claim")
    @RateLimit(key = "flashDeal:#voucherId", capacity = 100, refillPerSecond = 10)
    public Result claim(@PathVariable("id") Long voucherId) {
        Result seckillResult = voucherOrderService.seckillVoucher(voucherId);
        if (!Boolean.TRUE.equals(seckillResult.getSuccess())) {
            return Result.fail(seckillResult.getErrorMsg());
        }

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("dealId", voucherId);
        data.put("orderId", seckillResult.getData());
        data.put("status", "QUEUED");
        data.put("message", "限時餐券已搶到，訂單建立中");
        return Result.ok(data);
    }
}
