package com.bytebites.controller;

import com.bytebites.dto.Result;
import com.bytebites.entity.jpa.BookingJpa;
import com.bytebites.repository.BookingJpaRepository;
import com.bytebites.service.DepositPolicy;
import com.bytebites.service.IShopService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.Map;
import java.util.UUID;

/**
 * 訂位 Controller。
 * 免訂金：直接 reserve → status=3(已確認)。
 * 有訂金：前端先 reserve → status=1(待付款)，TapPay 付款後 PaymentController 回寫 status=2。
 */
@Slf4j
@RequiredArgsConstructor
@RestController
@RequestMapping({"/booking", "/api/booking"})
public class BookingController {

    private final BookingJpaRepository bookingRepo;
    private final IShopService shopService;
    private final DepositPolicy depositPolicy;

    /**
     * 建立訂位記錄並寫 DB。
     * needsDeposit=true  → status=1(待付款)，等 TapPay 回寫。
     * needsDeposit=false → status=3(已確認)。
     */
    @PostMapping("/reserve")
    public Result reserve(@RequestBody Map<String, Object> body) {
        Long shopId  = Long.valueOf(body.get("shopId").toString());
        int  people  = Integer.parseInt(body.getOrDefault("people", 2).toString());
        String date  = (String) body.get("date");
        String time  = (String) body.get("time");
        String table = (String) body.getOrDefault("tableType", "normal");

        // 查訂金政策
        var shop      = shopService.getById(shopId);
        Integer typeId   = shop != null && shop.getTypeId() != null ? shop.getTypeId().intValue() : null;
        Integer score    = shop != null ? shop.getScore() : null;
        Integer avgPrice = shop != null && shop.getAvgPrice() != null ? shop.getAvgPrice().intValue() : null;
        DepositPolicy.Result pol = depositPolicy.evaluate(shopId, typeId, score, avgPrice);

        // 建 booking 記錄
        BookingJpa booking = new BookingJpa();
        booking.setBookingCode("BK-" + UUID.randomUUID().toString().substring(0, 12).toUpperCase());
        booking.setShopId(shopId);
        booking.setPeople(people);
        booking.setBookingDate(LocalDate.parse(date));
        booking.setBookingTime(time);
        booking.setTableType(table);
        booking.setNeedsDeposit(pol.isNeedsDeposit());
        booking.setDepositPerPerson(pol.getDepositPerPerson());
        booking.setDepositTotal(pol.isNeedsDeposit() ? pol.getDepositPerPerson() * people : 0);
        booking.setStatus(pol.isNeedsDeposit() ? 1 : 3);  // 1=待付款, 3=已確認

        bookingRepo.save(booking);

        log.info("[Booking] code={} shop={} people={} date={} time={} table={} needsDeposit={} status={}",
                booking.getBookingCode(), shopId, people, date, time, table,
                pol.isNeedsDeposit(), booking.getStatus());

        return Result.ok(Map.of(
                "bookingCode",       booking.getBookingCode(),
                "shopId",            shopId,
                "people",            people,
                "date",              date,
                "time",              time,
                "tableType",         table,
                "needsDeposit",      pol.isNeedsDeposit(),
                "depositTotal",      booking.getDepositTotal(),
                "status",            pol.isNeedsDeposit() ? "PENDING_PAYMENT" : "CONFIRMED"
        ));
    }
}
