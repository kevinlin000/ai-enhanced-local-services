package com.bytebites.service;

import com.bytebites.config.TapPayProperties;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.Map;

/**
 * 串接 TapPay Pay by Prime API。
 * Sandbox endpoint: https://sandbox.tappaysdk.com/tpc/payment/pay-by-prime
 */
@Service
@Slf4j
@RequiredArgsConstructor
public class TapPayService {

    private final TapPayProperties props;
    private final RestTemplate restTemplate = new RestTemplate();

    /**
     * 呼叫 TapPay pay-by-prime，回傳 TapPay 原始 response map。
     * status=0 代表成功；非零代表失敗，msg 含錯誤說明。
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> payByPrime(String prime, long amount, Long orderId) {
        Map<String, Object> body = new HashMap<>();
        body.put("prime", prime);
        body.put("partner_key", props.getPartnerKey());
        body.put("merchant_id", props.getMerchantCreditCard());
        body.put("amount", amount);
        body.put("currency", "TWD");
        body.put("order_number", "BB-" + orderId);
        body.put("details", "ByteBites voucher #" + orderId);
        body.put("cardholder", Map.of(
                "phone_number", "+886900000000",
                "name", "Demo User",
                "email", "demo@bytebites.tw"
        ));
        body.put("remember", false);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("x-api-key", props.getPartnerKey());

        try {
            ResponseEntity<Map> response = restTemplate.exchange(
                    props.getApiBase() + "/tpc/payment/pay-by-prime",
                    HttpMethod.POST,
                    new HttpEntity<>(body, headers),
                    Map.class
            );
            log.info("[TapPay] pay-by-prime response: {}", response.getBody());
            return response.getBody() != null ? response.getBody() : Map.of("status", -999, "msg", "empty response");
        } catch (Exception e) {
            log.error("[TapPay] pay-by-prime error", e);
            return Map.of("status", -998, "msg", e.getMessage());
        }
    }
}
