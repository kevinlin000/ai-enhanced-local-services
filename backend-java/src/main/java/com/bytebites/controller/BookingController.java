package com.bytebites.controller;

import com.bytebites.dto.Result;
import com.bytebites.dto.UserDTO;
import com.bytebites.entity.jpa.BookingJpa;
import com.bytebites.repository.BookingJpaRepository;
import com.bytebites.service.AvailabilityNotificationService;
import com.bytebites.service.BookingDepositAdjustmentService;
import com.bytebites.service.BookingHoldService;
import com.bytebites.service.BookingIncidentService;
import com.bytebites.service.BookingLineNotificationService;
import com.bytebites.service.BookingPayloadMapper;
import com.bytebites.service.BookingRescheduleService;
import com.bytebites.service.BookingSlotInventory;
import com.bytebites.service.DepositPolicy;
import com.bytebites.service.IShopService;
import com.bytebites.service.LineActionTokenService;
import com.bytebites.service.ParkingService;
import com.bytebites.service.jpa.UserJpaService;
import com.bytebites.utils.UserHolder;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.CannotAcquireLockException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.DefaultTransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.List;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * 訂位 Controller。
 * 免訂金：直接 reserve → status=3(已確認)。
 * 有訂金：前端先 reserve → status=1(待付款)，TapPay 付款後回寫 status=2。
 * pay-test：供 AI agent 直接以 sandbox test card 完成付款。
 */
@Slf4j
@RequiredArgsConstructor
@RestController
@RequestMapping({"/booking", "/api/booking"})
public class BookingController {
    private static final ZoneId BUSINESS_ZONE = ZoneId.of("Asia/Taipei");

    private final BookingJpaRepository bookingRepo;
    private final IShopService shopService;
    private final DepositPolicy depositPolicy;
    private final BookingPayloadMapper bookingPayloadMapper;
    private final BookingRescheduleService bookingRescheduleService;
    private final BookingDepositAdjustmentService bookingDepositAdjustmentService;
    private final BookingIncidentService bookingIncidentService;
    private final BookingHoldService bookingHoldService;
    private final BookingSlotInventory bookingSlotInventory;
    private final AvailabilityNotificationService availabilityNotificationService;
    private final BookingLineNotificationService bookingLineNotificationService;
    private final ParkingService parkingService;
    private final UserJpaService userJpaService;
    private final LineActionTokenService lineActionTokenService;
    private final JdbcTemplate jdbcTemplate;
    private final PlatformTransactionManager transactionManager;

    /**
     * 建立訂位記錄並寫 DB。
     * needsDeposit=true  → status=1(待付款)，等 TapPay 回寫。
     * needsDeposit=false → status=3(已確認)。
     */
    @PostMapping("/reserve")
    public Result reserve(@RequestBody Map<String, Object> body) {
        for (int attempt = 1; attempt <= 2; attempt++) {
            try {
                return reserveTransactionTemplate().execute(status -> reserveInTransaction(body));
            } catch (CannotAcquireLockException ex) {
                if (attempt == 2) {
                    log.warn("[Booking] slot lock contention after retry body={}", body, ex);
                    return Result.fail("該時段目前忙碌，請稍後再試");
                }
                try {
                    Thread.sleep(30);
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    return Result.fail("訂位處理中斷，請再試一次");
                }
            }
        }
        return Result.fail("訂位失敗，請再試一次");
    }

    private TransactionTemplate reserveTransactionTemplate() {
        DefaultTransactionDefinition definition = new DefaultTransactionDefinition();
        definition.setIsolationLevel(TransactionDefinition.ISOLATION_READ_COMMITTED);
        definition.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRED);
        return new TransactionTemplate(transactionManager, definition);
    }

    private LocalDate today() {
        return LocalDate.now(BUSINESS_ZONE);
    }

    private Result reserveInTransaction(Map<String, Object> body) {
        if (body.get("shopId") == null) return Result.fail("shopId 必填");
        if (body.get("date") == null)   return Result.fail("date 必填");
        if (body.get("time") == null)   return Result.fail("time 必填");

        Long shopId;
        int people;
        LocalDate bookingDate;
        LocalTime bookingTime;
        try {
            shopId = Long.valueOf(body.get("shopId").toString());
            people = Integer.parseInt(body.getOrDefault("people", 2).toString());
            bookingDate = LocalDate.parse(body.get("date").toString());
            bookingTime = LocalTime.parse(body.get("time").toString());
        } catch (NumberFormatException | DateTimeParseException ex) {
            return Result.fail("訂位格式錯誤，請確認 shopId、people、date(YYYY-MM-DD)、time(HH:mm)");
        }

        if (people < 1 || people > 12) return Result.fail("訂位人數需介於 1-12 人");
        if (!bookingDate.isAfter(today())) return Result.fail("訂位日期需為明天或之後");
        Long ownerUserId = resolveBookingOwnerId(body);
        if (ownerUserId == null) return Result.fail("請先用 LINE 登入網頁，再回來完成訂位");

        String time = bookingTime.toString();
        String table = body.getOrDefault("tableType", "normal").toString();
        if (!table.equals("normal") && !table.equals("bar") && !table.equals("private")) {
            return Result.fail("tableType 僅支援 normal/bar/private");
        }
        String idempotencyKey = body.get("idempotencyKey") != null
                ? body.get("idempotencyKey").toString().trim()
                : null;
        if (idempotencyKey != null && idempotencyKey.isBlank()) idempotencyKey = null;
        if (idempotencyKey != null && idempotencyKey.length() > 120) {
            return Result.fail("idempotencyKey 長度不可超過 120");
        }
        if (idempotencyKey != null) {
            var existing = bookingRepo.findByIdempotencyKey(idempotencyKey).orElse(null);
            if (existing != null) {
                bookingHoldService.expireIfDue(existing);
                var existingShop = shopService.getById(existing.getShopId());
                String existingShopName = existingShop != null ? existingShop.getName() : null;
                return Result.ok(bookingResponse(existing, existingShopName, true));
            }
            lockIdempotencyKey(idempotencyKey);
            existing = bookingRepo.findByIdempotencyKey(idempotencyKey).orElse(null);
            if (existing != null) {
                bookingHoldService.expireIfDue(existing);
                var existingShop = shopService.getById(existing.getShopId());
                String existingShopName = existingShop != null ? existingShop.getName() : null;
                return Result.ok(bookingResponse(existing, existingShopName, true));
            }
        }

        // 查訂金政策
        var shop     = shopService.getById(shopId);
        if (shop == null) return Result.fail("店家不存在");
        Integer typeId   = shop != null && shop.getTypeId() != null ? shop.getTypeId().intValue() : null;
        Integer score    = shop != null ? shop.getScore() : null;
        Integer avgPrice = shop != null && shop.getAvgPrice() != null ? shop.getAvgPrice().intValue() : null;
        String  shopName = shop != null ? shop.getName() : null;
        DepositPolicy.Result pol = depositPolicy.evaluate(shopId, shopName, typeId, score, avgPrice);

        if (!bookingSlotInventory.reserve(shopId, bookingDate, time, table, people)) {
            return Result.fail("該時段目前已額滿，請選擇其他時間");
        }

        // 建 booking 記錄
        BookingJpa booking = new BookingJpa();
        booking.setUserId(ownerUserId);
        booking.setBookingCode("BK-" + UUID.randomUUID().toString().substring(0, 12).toUpperCase());
        booking.setShopId(shopId);
        booking.setPeople(people);
        booking.setBookingDate(bookingDate);
        booking.setBookingTime(time);
        booking.setTableType(table);
        booking.setNeedsDeposit(pol.isNeedsDeposit());
        booking.setDepositPerPerson(pol.getDepositPerPerson());
        booking.setDepositTotal(pol.isNeedsDeposit() ? pol.getDepositPerPerson() * people : 0);
        booking.setStatus(pol.isNeedsDeposit()
                ? BookingHoldService.STATUS_PENDING_PAYMENT
                : BookingHoldService.STATUS_CONFIRMED);
        booking.setHoldExpiresAt(pol.isNeedsDeposit() ? bookingHoldService.newHoldExpiry() : null);
        booking.setIdempotencyKey(idempotencyKey);
        boolean drivingToBooking = truthy(body.get("drivingToBooking"));
        booking.setDrivingToBooking(drivingToBooking);
        booking.setParkingReminderEnabled(drivingToBooking && truthy(body.getOrDefault("parkingReminderEnabled", true)));

        bookingRepo.saveAndFlush(booking);
        bookingLineNotificationService.pushBookingUpdated(booking, "reserved");
        pushParkingReminderNow(booking);

        log.info("[Booking] code={} shop={} people={} date={} time={} table={} needsDeposit={} status={}",
                booking.getBookingCode(), shopId, people, bookingDate, time, table,
                pol.isNeedsDeposit(), booking.getStatus());

        return Result.ok(bookingResponse(booking, shopName, false));
    }

    private void lockIdempotencyKey(String idempotencyKey) {
        jdbcTemplate.update(
                """
                INSERT IGNORE INTO tb_booking_idempotency_lock (idempotency_key)
                VALUES (?)
                """,
                idempotencyKey
        );
        jdbcTemplate.queryForObject(
                """
                SELECT idempotency_key
                FROM tb_booking_idempotency_lock
                WHERE idempotency_key = ?
                FOR UPDATE
                """,
                String.class,
                idempotencyKey
        );
    }

    /**
     * AI Agent / Demo 專用：模擬訂金付款、不打真實 TapPay。
     * TapPay prime 為 one-time token 需 JS SDK 產生，server-side 無法靜態複用。
     * 此 endpoint 直接寫入 demo trans_id，僅供 agent demo 展示全流程。
     *
     * @param body { "bookingCode": "BK-XXXXXXXXXXXX" }
     */
    @PostMapping("/pay-test")
    public Result payTest(@RequestBody Map<String, Object> body) {
        String bookingCode = (String) body.get("bookingCode");
        if (bookingCode == null || bookingCode.isBlank()) return Result.fail("bookingCode 必填");

        BookingJpa b = bookingRepo.findByBookingCode(bookingCode).orElse(null);
        if (b == null)            return Result.fail("訂位不存在");
        if (!canAccessBooking(b, body)) return Result.fail("無權操作此訂位");
        if (b.getStatus() == BookingHoldService.STATUS_CANCELED) return Result.fail("訂位已取消，無法付款");
        if (b.getStatus() == BookingHoldService.STATUS_EXPIRED) return Result.fail("此保留已逾期，請重新建立訂位");
        if (bookingHoldService.expireIfDue(b)) return Result.fail("此保留已逾期，請重新建立訂位");
        if (!b.getNeedsDeposit()) return Result.fail("此訂位免訂金、無需付款");
        if (b.getStatus() == BookingHoldService.STATUS_PAID) {
            return Result.ok(Map.of(
                    "bookingCode",  bookingCode,
                    "rec_trade_id", b.getPaymentTransId(),
                    "amount",       b.getDepositTotal(),
                    "status",       "PAID",
                    "note",         "訂位已付款，回傳既有交易編號"
            ));
        }

        // Demo transaction ID（格式仿 TapPay）
        String demoTransId = "DEMO-" + UUID.randomUUID().toString().substring(0, 12).toUpperCase();
        b.setPaymentTransId(demoTransId);
        b.setStatus(BookingHoldService.STATUS_PAID);
        bookingRepo.save(b);
        bookingLineNotificationService.pushBookingUpdated(b, "paid");

        log.info("[Booking pay-test] {} demo-paid via agent, trans={}", bookingCode, demoTransId);

        return Result.ok(Map.of(
                "bookingCode",  bookingCode,
                "rec_trade_id", demoTransId,
                "amount",       b.getDepositTotal(),
                "status",       "PAID",
                "note",         "agent demo 付款，非真實 TapPay"
        ));
    }

    @GetMapping("/my")
    public Result myBookings(
            @RequestParam(required = false) String lineUserId,
            @RequestParam(required = false) String lineActionToken
    ) {
        UserDTO current = UserHolder.getUser();
        Set<Long> userIds = new LinkedHashSet<>();
        String currentLineUserId = current != null ? current.getLineUserId() : null;
        if (current != null && current.getId() != null) {
            userIds.add(current.getId());
            currentLineUserId = userJpaService.findById(current.getId())
                    .map(user -> user.getLineUserId() == null ? "" : user.getLineUserId().trim())
                    .filter(value -> !value.isBlank())
                    .orElse(currentLineUserId);
        }

        String requestedLineUserId = lineUserId != null && !lineUserId.isBlank() ? lineUserId.trim() : null;
        if (current != null && current.getId() != null && requestedLineUserId != null) {
            if (currentLineUserId == null || !requestedLineUserId.equals(currentLineUserId.trim())) {
                return Result.fail("LINE 身分不符，請重新登入");
            }
        }

        if (current == null && requestedLineUserId != null) {
            lineActionTokenService.resolveOwnerId(requestedLineUserId, lineActionToken, null)
                    .ifPresent(userIds::add);
        } else {
            String effectiveLineUserId = requestedLineUserId != null ? requestedLineUserId : currentLineUserId;
            if (effectiveLineUserId != null && !effectiveLineUserId.isBlank()) {
                userIds.add(userJpaService.resolveLineIdentity(effectiveLineUserId, null).getId());
            }
        }
        if (userIds.isEmpty()) return Result.fail("請先登入");

        List<Map<String, Object>> bookings = bookingRepo.findByUserIdInOrderByCreatedAtDesc(new ArrayList<>(userIds))
                .stream()
                .map(booking -> {
                    bookingHoldService.expireIfDue(booking);
                    var shop = shopService.getById(booking.getShopId());
                    String shopName = shop != null ? shop.getName() : null;
                    return bookingResponse(booking, shopName, false);
                })
                .collect(Collectors.collectingAndThen(
                        Collectors.toMap(
                                item -> String.valueOf(item.get("bookingCode")),
                                item -> item,
                                (first, ignored) -> first,
                                LinkedHashMap::new
                        ),
                        map -> new ArrayList<>(map.values())
                ));
        return Result.ok(bookings);
    }

    @PostMapping("/{bookingCode}/parking-preference")
    public Result updateParkingPreference(
            @PathVariable String bookingCode,
            @RequestBody(required = false) Map<String, Object> body
    ) {
        Map<String, Object> requestBody = body != null ? body : Map.of();
        if (bookingCode == null || bookingCode.isBlank()) return Result.fail("bookingCode 必填");

        BookingJpa booking = bookingRepo.findByBookingCode(bookingCode).orElse(null);
        if (booking == null) return Result.fail("訂位不存在");
        if (!canAccessBooking(booking, requestBody)) return Result.fail("無權操作此訂位");
        if (booking.getStatus() == BookingHoldService.STATUS_CANCELED
                || booking.getStatus() == BookingHoldService.STATUS_EXPIRED) {
            return Result.fail("此訂位已取消或逾期，無法設定停車提醒");
        }

        boolean drivingToBooking = truthy(requestBody.get("drivingToBooking"));
        boolean reminderEnabled = drivingToBooking
                && truthy(requestBody.getOrDefault("parkingReminderEnabled", true));
        booking.setDrivingToBooking(drivingToBooking);
        booking.setParkingReminderEnabled(reminderEnabled);
        if (reminderEnabled) {
            booking.setParkingReminderSentAt(null);
        }
        if (reminderEnabled) {
            pushParkingReminderNow(booking);
        } else {
            bookingRepo.save(booking);
        }
        var shop = shopService.getById(booking.getShopId());
        String shopName = shop != null ? shop.getName() : null;
        return Result.ok(bookingResponse(booking, shopName, false));
    }

    @PostMapping("/{bookingCode}/cancel")
    public Result cancel(@PathVariable String bookingCode, @RequestBody(required = false) Map<String, Object> body) {
        Map<String, Object> requestBody = body != null ? body : Map.of();
        return reserveTransactionTemplate().execute(status -> cancelInTransaction(bookingCode, requestBody));
    }

    @PostMapping("/{bookingCode}/reschedule")
    public Result reschedule(
            @PathVariable String bookingCode,
            @RequestBody(required = false) Map<String, Object> body
    ) {
        Map<String, Object> requestBody = body != null ? body : Map.of();
        for (int attempt = 1; attempt <= 2; attempt++) {
            try {
                return reserveTransactionTemplate().execute(status -> rescheduleInTransaction(bookingCode, requestBody));
            } catch (CannotAcquireLockException ex) {
                if (attempt == 2) {
                    log.warn("[Booking reschedule] slot lock contention after retry bookingCode={} body={}", bookingCode, body, ex);
                    return Result.fail("該時段目前忙碌，請稍後再試");
                }
                try {
                    Thread.sleep(30);
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    return Result.fail("改單處理中斷，請再試一次");
                }
            }
        }
        return Result.fail("改單失敗，請再試一次");
    }

    @GetMapping("/{bookingCode}/incidents")
    public Result bookingIncidents(
            @PathVariable String bookingCode,
            @RequestParam(required = false) String lineUserId,
            @RequestParam(required = false) String lineActionToken
    ) {
        Map<String, Object> body = new LinkedHashMap<>();
        if (lineUserId != null) body.put("lineUserId", lineUserId);
        if (lineActionToken != null) body.put("lineActionToken", lineActionToken);
        return bookingIncidentService.listIncidents(bookingCode, body);
    }

    @PostMapping("/{bookingCode}/incidents")
    public Result createBookingIncident(
            @PathVariable String bookingCode,
            @RequestBody(required = false) Map<String, Object> body
    ) {
        return bookingIncidentService.createIncident(bookingCode, body != null ? body : Map.of());
    }

    @PostMapping("/{bookingCode}/incidents/{incidentId}/resolve")
    public Result resolveBookingIncident(
            @PathVariable String bookingCode,
            @PathVariable Long incidentId,
            @RequestBody(required = false) Map<String, Object> body
    ) {
        return bookingIncidentService.resolveIncident(bookingCode, incidentId, body != null ? body : Map.of());
    }

    @PostMapping("/{bookingCode}/incidents/{incidentId}/proposal/accept")
    public Result acceptIncidentProposal(
            @PathVariable String bookingCode,
            @PathVariable Long incidentId,
            @RequestBody(required = false) Map<String, Object> body
    ) {
        Map<String, Object> requestBody = body != null ? body : Map.of();
        for (int attempt = 1; attempt <= 2; attempt++) {
            try {
                return reserveTransactionTemplate().execute(status ->
                        acceptIncidentProposalInTransaction(bookingCode, incidentId, requestBody)
                );
            } catch (CannotAcquireLockException ex) {
                if (attempt == 2) {
                    log.warn("[Booking incident proposal] slot lock contention after retry bookingCode={} incidentId={}",
                            bookingCode, incidentId, ex);
                    return Result.fail("該時段目前忙碌，請稍後再試");
                }
                try {
                    Thread.sleep(30);
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    return Result.fail("提案確認中斷，請再試一次");
                }
            }
        }
        return Result.fail("提案確認失敗，請再試一次");
    }

    @PostMapping("/{bookingCode}/incidents/{incidentId}/proposal/decline")
    public Result declineIncidentProposal(
            @PathVariable String bookingCode,
            @PathVariable Long incidentId,
            @RequestBody(required = false) Map<String, Object> body
    ) {
        Map<String, Object> requestBody = body != null ? body : Map.of();
        try {
            return reserveTransactionTemplate().execute(status ->
                    declineIncidentProposalInTransaction(bookingCode, incidentId, requestBody)
            );
        } catch (CannotAcquireLockException ex) {
            log.warn("[Booking incident proposal] decline lock contention bookingCode={} incidentId={}",
                    bookingCode, incidentId, ex);
            return Result.fail("提案回覆中忙碌，請稍後再試");
        }
    }

    private Result rescheduleInTransaction(String bookingCode, Map<String, Object> body) {
        if (bookingCode == null || bookingCode.isBlank()) return Result.fail("bookingCode 必填");

        BookingJpa booking = bookingRepo.findByBookingCode(bookingCode).orElse(null);
        if (booking == null) return Result.fail("訂位不存在");
        if (!canAccessBooking(booking, body)) return Result.fail("無權操作此訂位");
        if (booking.getStatus() == BookingHoldService.STATUS_CANCELED
                || booking.getStatus() == BookingHoldService.STATUS_EXPIRED) {
            return Result.fail("此訂位已取消或逾期，無法改期");
        }
        if (bookingHoldService.expireIfDue(booking)) {
            return Result.fail("此保留已逾期，請重新建立訂位");
        }

        ParsedRescheduleRequest request = parseRescheduleRequest(booking, body);
        if (!request.valid()) {
            return Result.fail(request.error());
        }

        BookingRescheduleService.RescheduleResult result = bookingRescheduleService.reschedule(
                booking,
                request.date(),
                request.time(),
                request.tableType(),
                request.people()
        );
        if (!result.success()) {
            recordDepositAdjustmentIfRequired(
                    booking,
                    null,
                    request.date(),
                    request.time(),
                    request.tableType(),
                    request.people(),
                    result.depositPolicy(),
                    "CUSTOMER_RESCHEDULE"
            );
            return Result.fail(result.error());
        }

        var shop = shopService.getById(booking.getShopId());
        String shopName = shop != null ? shop.getName() : null;
        Map<String, Object> response = bookingResponse(result.booking(), shopName, false);
        response.put("changed", result.changed());
        if (result.depositPolicy() != null) {
            response.put("depositPolicy", result.depositPolicy().toPayload());
        }
        log.info("[Booking reschedule] code={} shop={} people={} date={} time={} table={} changed={}",
                booking.getBookingCode(), booking.getShopId(), booking.getPeople(),
                booking.getBookingDate(), booking.getBookingTime(), booking.getTableType(), result.changed());
        return Result.ok(response);
    }

    private Result acceptIncidentProposalInTransaction(String bookingCode, Long incidentId, Map<String, Object> body) {
        if (bookingCode == null || bookingCode.isBlank()) return Result.fail("bookingCode 必填");
        if (incidentId == null) return Result.fail("incidentId 必填");

        BookingJpa booking = bookingRepo.findByBookingCode(bookingCode).orElse(null);
        if (booking == null) return Result.fail("訂位不存在");
        if (!canAccessBooking(booking, body)) return Result.fail("無權確認此救場提案");
        if (booking.getStatus() == BookingHoldService.STATUS_CANCELED
                || booking.getStatus() == BookingHoldService.STATUS_EXPIRED) {
            return Result.fail("此訂位已取消或逾期，無法確認提案");
        }
        if (bookingHoldService.expireIfDue(booking)) {
            return Result.fail("此保留已逾期，請重新建立訂位");
        }

        List<Map<String, Object>> rows = pendingIncidentProposalRows(incidentId, booking.getBookingCode());
        if (rows.isEmpty()) return Result.fail("救場提案不存在或已處理");
        Map<String, Object> proposal = rows.get(0);
        if (isProposalExpired(proposal)) {
            expireIncidentProposal(incidentId, booking.getBookingCode());
            return Result.fail("救場提案已逾期，請等店家重新提出");
        }

        ParsedProposal parsedProposal = parseProposal(proposal);
        if (!parsedProposal.valid()) return Result.fail(parsedProposal.error());

        BookingRescheduleService.RescheduleResult result = bookingRescheduleService.reschedule(
                booking,
                parsedProposal.date(),
                parsedProposal.time(),
                parsedProposal.tableType(),
                parsedProposal.people()
        );
        if (!result.success()) {
            recordDepositAdjustmentIfRequired(
                    booking,
                    incidentId,
                    parsedProposal.date(),
                    parsedProposal.time(),
                    parsedProposal.tableType(),
                    parsedProposal.people(),
                    result.depositPolicy(),
                    "INCIDENT_PROPOSAL"
            );
            return Result.fail(result.error());
        }

        jdbcTemplate.update(
                """
                UPDATE tb_booking_incident
                SET proposal_status = 'ACCEPTED',
                    proposal_accepted_at = CURRENT_TIMESTAMP,
                    status = 'RESOLVED',
                    resolved_at = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND booking_code = ?
                  AND proposal_status = 'PENDING'
                """,
                incidentId,
                booking.getBookingCode()
        );

        var shop = shopService.getById(booking.getShopId());
        String shopName = shop != null ? shop.getName() : null;
        Map<String, Object> response = bookingResponse(result.booking(), shopName, false);
        response.put("changed", result.changed());
        if (result.depositPolicy() != null) {
            response.put("depositPolicy", result.depositPolicy().toPayload());
        }
        response.put("acceptedProposal", Map.of(
                "incidentId", incidentId,
                "date", parsedProposal.date().toString(),
                "time", parsedProposal.time(),
                "tableType", parsedProposal.tableType(),
                "people", parsedProposal.people()
        ));
        log.info("[Booking incident proposal] accepted bookingCode={} incidentId={} date={} time={} people={}",
                booking.getBookingCode(), incidentId, parsedProposal.date(), parsedProposal.time(), parsedProposal.people());
        return Result.ok(response);
    }

    private Result declineIncidentProposalInTransaction(String bookingCode, Long incidentId, Map<String, Object> body) {
        if (bookingCode == null || bookingCode.isBlank()) return Result.fail("bookingCode 必填");
        if (incidentId == null) return Result.fail("incidentId 必填");

        BookingJpa booking = bookingRepo.findByBookingCode(bookingCode).orElse(null);
        if (booking == null) return Result.fail("訂位不存在");
        if (!canAccessBooking(booking, body)) return Result.fail("無權回覆此救場提案");
        if (booking.getStatus() == BookingHoldService.STATUS_CANCELED
                || booking.getStatus() == BookingHoldService.STATUS_EXPIRED) {
            return Result.fail("此訂位已取消或逾期，無法回覆提案");
        }
        if (bookingHoldService.expireIfDue(booking)) {
            return Result.fail("此保留已逾期，請重新建立訂位");
        }

        List<Map<String, Object>> rows = pendingIncidentProposalRows(incidentId, booking.getBookingCode());
        if (rows.isEmpty()) return Result.fail("救場提案不存在或已處理");
        Map<String, Object> proposal = rows.get(0);
        if (isProposalExpired(proposal)) {
            expireIncidentProposal(incidentId, booking.getBookingCode());
            return Result.fail("救場提案已逾期，請等店家重新提出");
        }

        int updated = jdbcTemplate.update(
                """
                UPDATE tb_booking_incident
                SET proposal_status = 'DECLINED',
                    proposal_declined_at = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND booking_code = ?
                  AND status = 'OPEN'
                  AND proposal_status = 'PENDING'
                """,
                incidentId,
                booking.getBookingCode()
        );
        if (updated == 0) return Result.fail("救場提案不存在或已處理");

        var shop = shopService.getById(booking.getShopId());
        String shopName = shop != null ? shop.getName() : null;
        Map<String, Object> response = bookingResponse(booking, shopName, false);
        response.put("declinedProposal", Map.of("incidentId", incidentId));
        log.info("[Booking incident proposal] declined bookingCode={} incidentId={}",
                booking.getBookingCode(), incidentId);
        return Result.ok(response);
    }

    private List<Map<String, Object>> pendingIncidentProposalRows(Long incidentId, String bookingCode) {
        return jdbcTemplate.queryForList(
                """
                SELECT proposal_status AS proposalStatus,
                       proposed_date AS proposedDate,
                       proposed_time AS proposedTime,
                       proposed_table_type AS proposedTableType,
                       proposed_people AS proposedPeople,
                       proposal_message AS proposalMessage,
                       proposal_expires_at AS proposalExpiresAt
                FROM tb_booking_incident
                WHERE id = ?
                  AND booking_code = ?
                  AND status = 'OPEN'
                  AND proposal_status = 'PENDING'
                FOR UPDATE
                """,
                incidentId,
                bookingCode
        );
    }

    private void expireIncidentProposal(Long incidentId, String bookingCode) {
        jdbcTemplate.update(
                """
                UPDATE tb_booking_incident
                SET proposal_status = 'EXPIRED'
                WHERE id = ?
                  AND booking_code = ?
                  AND proposal_status = 'PENDING'
                """,
                incidentId,
                bookingCode
        );
    }

    private Result cancelInTransaction(String bookingCode, Map<String, Object> body) {
        if (bookingCode == null || bookingCode.isBlank()) return Result.fail("bookingCode 必填");

        BookingJpa booking = bookingRepo.findByBookingCode(bookingCode).orElse(null);
        if (booking == null) return Result.fail("訂位不存在");
        if (!canAccessBooking(booking, body)) return Result.fail("無權操作此訂位");

        var shop = shopService.getById(booking.getShopId());
        String shopName = shop != null ? shop.getName() : null;
        if (booking.getStatus() == BookingHoldService.STATUS_CANCELED
                || booking.getStatus() == BookingHoldService.STATUS_EXPIRED) {
            return Result.ok(bookingResponse(booking, shopName, true));
        }
        if (bookingHoldService.expireIfDue(booking)) {
            return Result.ok(bookingResponse(booking, shopName, true));
        }

        bookingSlotInventory.release(
                booking.getShopId(),
                booking.getBookingDate(),
                booking.getBookingTime(),
                booking.getTableType(),
                booking.getPeople()
        );
        availabilityNotificationService.triggerIfAvailable(
                booking.getShopId(),
                booking.getBookingDate(),
                booking.getBookingTime(),
                booking.getTableType()
        );
        booking.setStatus(BookingHoldService.STATUS_CANCELED);
        bookingRepo.saveAndFlush(booking);
        Map<String, Object> response = bookingResponse(booking, shopName, false);
        bookingLineNotificationService.pushBookingUpdated(booking, "canceled");

        log.info("[Booking cancel] code={} shop={} people={} date={} time={}",
                booking.getBookingCode(), booking.getShopId(), booking.getPeople(),
                booking.getBookingDate(), booking.getBookingTime());

        return Result.ok(response);
    }

    private Map<String, Object> bookingResponse(BookingJpa booking, String shopName, boolean idempotentReplay) {
        Map<String, Object> payload = bookingPayloadMapper.toPayload(booking, shopName, idempotentReplay);
        bookingIncidentService.latestIncidentForBookingCode(booking.getBookingCode())
                .ifPresent(incident -> payload.put("latestIncident", incident));
        return payload;
    }

    private void recordDepositAdjustmentIfRequired(
            BookingJpa booking,
            Long incidentId,
            LocalDate proposedDate,
            String proposedTime,
            String proposedTableType,
            int proposedPeople,
            BookingRescheduleService.DepositAdjustment depositPolicy,
            String source
    ) {
        bookingDepositAdjustmentService.recordRequired(
                booking,
                incidentId,
                proposedDate,
                proposedTime,
                proposedTableType,
                proposedPeople,
                depositPolicy,
                source
        );
    }

    private ParsedRescheduleRequest parseRescheduleRequest(BookingJpa booking, Map<String, Object> body) {
        try {
            LocalDate date = booking.getBookingDate();
            Object dateValue = body.get("date");
            if (dateValue != null && !dateValue.toString().isBlank()) {
                date = LocalDate.parse(dateValue.toString().trim());
            }

            String time = booking.getBookingTime();
            Object timeValue = body.get("time");
            if (timeValue != null && !timeValue.toString().isBlank()) {
                time = LocalTime.parse(timeValue.toString().trim()).toString();
            }

            int people = booking.getPeople() != null ? booking.getPeople() : 2;
            Object peopleValue = body.get("people");
            if (peopleValue != null && !peopleValue.toString().isBlank()) {
                people = Integer.parseInt(peopleValue.toString());
            }

            String tableType = normalizeTableType(booking.getTableType());
            Object tableValue = body.get("tableType");
            if (tableValue != null && !tableValue.toString().isBlank()) {
                tableType = normalizeTableType(tableValue.toString());
            }

            if (people < 1 || people > 12) {
                return ParsedRescheduleRequest.fail("訂位人數需介於 1-12 人");
            }
            if (!date.isAfter(today())) {
                return ParsedRescheduleRequest.fail("訂位日期需為明天或之後");
            }
            if (!tableType.equals("normal") && !tableType.equals("bar") && !tableType.equals("private")) {
                return ParsedRescheduleRequest.fail("tableType 僅支援 normal/bar/private");
            }

            return ParsedRescheduleRequest.ok(date, time, tableType, people);
        } catch (NumberFormatException | DateTimeParseException ex) {
            return ParsedRescheduleRequest.fail("改單格式錯誤，請確認 people、date(YYYY-MM-DD)、time(HH:mm)");
        }
    }

    private ParsedProposal parseProposal(Map<String, Object> proposal) {
        try {
            LocalDate date = LocalDate.parse(text(proposal.get("proposedDate")));
            String time = LocalTime.parse(text(proposal.get("proposedTime"))).toString();
            String tableType = normalizeTableType(text(proposal.get("proposedTableType")));
            int people = Integer.parseInt(text(proposal.get("proposedPeople")));
            if (people < 1 || people > 12) return ParsedProposal.fail("提案人數需介於 1-12 人");
            if (!date.isAfter(today())) return ParsedProposal.fail("提案日期需為明天或之後");
            if (!tableType.equals("normal") && !tableType.equals("bar") && !tableType.equals("private")) {
                return ParsedProposal.fail("提案桌型僅支援 normal/bar/private");
            }
            return ParsedProposal.ok(date, time, tableType, people);
        } catch (NumberFormatException | DateTimeParseException ex) {
            return ParsedProposal.fail("救場提案格式錯誤");
        }
    }

    private boolean isProposalExpired(Map<String, Object> proposal) {
        LocalDateTime expiresAt = toLocalDateTime(proposal.get("proposalExpiresAt"));
        return expiresAt != null && !expiresAt.isAfter(LocalDateTime.now(BUSINESS_ZONE));
    }

    private LocalDateTime toLocalDateTime(Object value) {
        if (value == null) return null;
        if (value instanceof LocalDateTime dateTime) return dateTime;
        if (value instanceof java.sql.Timestamp timestamp) return timestamp.toLocalDateTime();
        String raw = text(value);
        if (raw.isBlank()) return null;
        try {
            return LocalDateTime.parse(raw.replace(" ", "T"));
        } catch (DateTimeParseException ignored) {
            return null;
        }
    }

    private String normalizeTableType(String tableType) {
        if (tableType == null || tableType.isBlank()) {
            return "normal";
        }
        return tableType.trim();
    }

    private void pushParkingReminderNow(BookingJpa booking) {
        if (booking == null || !Boolean.TRUE.equals(booking.getParkingReminderEnabled())) {
            return;
        }
        var shop = booking.getShopId() == null ? null : shopService.getById(booking.getShopId());
        List<ParkingService.NearbyParkingLotView> parkingLots = List.of();
        if (shop != null && shop.getX() != null && shop.getY() != null) {
            parkingLots = parkingService.nearby(shop.getX(), shop.getY(), 900, 3);
        }
        bookingLineNotificationService.pushParkingReminder(booking, parkingLots);
        booking.setParkingReminderSentAt(LocalDateTime.now(BUSINESS_ZONE));
        bookingRepo.save(booking);
    }

    private Long currentUserIdOrNull() {
        UserDTO user = UserHolder.getUser();
        return user != null ? user.getId() : null;
    }

    private boolean canAccessBooking(BookingJpa booking) {
        return canAccessBooking(booking, Map.of());
    }

    private boolean canAccessBooking(BookingJpa booking, Map<String, Object> body) {
        Long ownerId = booking.getUserId();
        Long currentUserId = currentUserIdOrNull();
        if (ownerId != null && currentUserId != null && ownerId.equals(currentUserId)) {
            return true;
        }
        Long lineUserOwnerId = resolveLineUserOwnerId(body);
        return ownerId != null && lineUserOwnerId != null && ownerId.equals(lineUserOwnerId);
    }

    private Long resolveBookingOwnerId(Map<String, Object> body) {
        Long currentUserId = currentUserIdOrNull();
        if (currentUserId != null) return currentUserId;
        return resolveLineUserOwnerId(body);
    }

    private Long resolveLineUserOwnerId(Map<String, Object> body) {
        return lineActionTokenService.resolveOwnerId(body).orElse(null);
    }

    private boolean truthy(Object value) {
        if (value == null) return false;
        if (value instanceof Boolean bool) return bool;
        String text = value.toString().trim();
        return text.equalsIgnoreCase("true")
                || text.equalsIgnoreCase("yes")
                || text.equals("1")
                || text.equals("會開車")
                || text.equals("我會開車，提醒停車");
    }

    private String text(Object value) {
        return value == null ? "" : value.toString().trim();
    }

    private record ParsedRescheduleRequest(
            LocalDate date,
            String time,
            String tableType,
            int people,
            String error
    ) {
        static ParsedRescheduleRequest ok(LocalDate date, String time, String tableType, int people) {
            return new ParsedRescheduleRequest(date, time, tableType, people, null);
        }

        static ParsedRescheduleRequest fail(String error) {
            return new ParsedRescheduleRequest(null, null, null, 0, error);
        }

        boolean valid() {
            return error == null;
        }
    }

    private record ParsedProposal(
            boolean valid,
            String error,
            LocalDate date,
            String time,
            String tableType,
            int people
    ) {
        static ParsedProposal ok(LocalDate date, String time, String tableType, int people) {
            return new ParsedProposal(true, null, date, time, tableType, people);
        }

        static ParsedProposal fail(String error) {
            return new ParsedProposal(false, error, null, null, null, 0);
        }
    }

}
