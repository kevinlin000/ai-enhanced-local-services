package com.bytebites.controller;

import com.bytebites.dto.Result;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.util.UUID;

/**
 * 純訂位（免訂金流程）。
 * 有訂金的流程走 PaymentController → TapPay pay-by-prime。
 * 後續可擴充：寫進 tb_booking、發 RabbitMQ 通知。
 */
@Slf4j
@RestController
@RequestMapping({"/booking", "/api/booking"})
public class BookingController {

    /**
     * 純訂位、不走金流。
     * 回傳 booking_id，前端顯示訂位完成。
     */
    @PostMapping("/reserve")
    public Result reserve(@RequestBody Map<String, Object> body) {
        Long shopId = Long.valueOf(body.get("shopId").toString());
        Integer people = Integer.valueOf(body.getOrDefault("people", 2).toString());
        String date = (String) body.get("date");
        String time = (String) body.get("time");
        String tableType = (String) body.getOrDefault("tableType", "normal");

        String bookingId = "BK-" + UUID.randomUUID().toString().substring(0, 12).toUpperCase();

        log.info("[Booking] shop={} people={} date={} time={} table={} id={}",
                shopId, people, date, time, tableType, bookingId);

        // TODO: 寫進 tb_booking + 發 RabbitMQ 通知

        return Result.ok(Map.of(
                "bookingId", bookingId,
                "shopId", shopId,
                "people", people,
                "date", date,
                "time", time,
                "tableType", tableType,
                "status", "CONFIRMED"
        ));
    }
}
