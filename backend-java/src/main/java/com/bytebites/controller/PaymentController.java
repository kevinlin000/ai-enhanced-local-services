package com.bytebites.controller;

import com.bytebites.dto.Result;
import com.bytebites.enums.PayType;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.Arrays;
import java.util.Map;
import java.util.UUID;

@Slf4j
@RestController
@RequestMapping({"/payment", "/api/payment"})
public class PaymentController {

    /**
     * Mock TapPay callback。
     * Production: TapPay SDK POST 過來，含 prime token、status、rec_trade_id。
     * Demo: 直接回成功，生成 fake rec_trade_id。
     */
    @PostMapping("/tappay/mock-callback")
    public Result mockCallback(@RequestBody Map<String, Object> body) {
        Long orderId = Long.valueOf(body.get("orderId").toString());
        int payTypeCode = ((Number) body.getOrDefault("payType", 1)).intValue();

        PayType payType = Arrays.stream(PayType.values())
                .filter(p -> p.getCode() == payTypeCode)
                .findFirst()
                .orElse(PayType.CREDIT_CARD);

        String fakeTransId = "TPY-" + UUID.randomUUID().toString().substring(0, 12).toUpperCase();

        log.info("[Mock TapPay] order={}, payType={} ({}), trans={}",
                orderId, payTypeCode, payType.getLabel(), fakeTransId);

        return Result.ok(Map.of(
                "status", "PAID",
                "rec_trade_id", fakeTransId,
                "pay_type", payTypeCode,
                "label", payType.getLabel(),
                "amount", body.getOrDefault("amount", 0)
        ));
    }

    @GetMapping("/methods")
    public Result methods() {
        return Result.ok(Arrays.stream(PayType.values())
                .map(p -> Map.of("code", p.getCode(), "label", p.getLabel()))
                .toList());
    }
}
