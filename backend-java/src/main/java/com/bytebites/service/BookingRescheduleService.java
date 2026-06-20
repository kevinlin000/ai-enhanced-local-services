package com.bytebites.service;

import com.bytebites.entity.jpa.BookingJpa;
import com.bytebites.repository.BookingJpaRepository;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;

@Service
public class BookingRescheduleService {
    private final BookingJpaRepository bookingRepo;
    private final BookingSlotInventory bookingSlotInventory;
    private final AvailabilityNotificationService availabilityNotificationService;
    private final BookingLineNotificationService bookingLineNotificationService;

    public BookingRescheduleService(
            BookingJpaRepository bookingRepo,
            BookingSlotInventory bookingSlotInventory,
            AvailabilityNotificationService availabilityNotificationService,
            BookingLineNotificationService bookingLineNotificationService
    ) {
        this.bookingRepo = bookingRepo;
        this.bookingSlotInventory = bookingSlotInventory;
        this.availabilityNotificationService = availabilityNotificationService;
        this.bookingLineNotificationService = bookingLineNotificationService;
    }

    public RescheduleResult reschedule(
            BookingJpa booking,
            LocalDate newDate,
            String newTime,
            String newTableType,
            int newPeople
    ) {
        return reschedule(booking, newDate, newTime, newTableType, newPeople, false);
    }

    public RescheduleResult rescheduleAfterManualDepositHandling(
            BookingJpa booking,
            LocalDate newDate,
            String newTime,
            String newTableType,
            int newPeople
    ) {
        return reschedule(booking, newDate, newTime, newTableType, newPeople, true);
    }

    private RescheduleResult reschedule(
            BookingJpa booking,
            LocalDate newDate,
            String newTime,
            String newTableType,
            int newPeople,
            boolean manualDepositHandled
    ) {
        if (booking == null) {
            return RescheduleResult.fail("訂位不存在", null);
        }
        if (booking.getStatus() == BookingHoldService.STATUS_CANCELED
                || booking.getStatus() == BookingHoldService.STATUS_EXPIRED) {
            return RescheduleResult.fail("此訂位已取消或逾期，無法改期", booking);
        }

        LocalDate oldDate = booking.getBookingDate();
        String oldTime = booking.getBookingTime();
        String oldTableType = normalizeTableType(booking.getTableType());
        int oldPeople = booking.getPeople() != null ? booking.getPeople() : 0;
        String targetTableType = normalizeTableType(newTableType);

        boolean slotChanged = !Objects.equals(oldDate, newDate)
                || !Objects.equals(oldTime, newTime)
                || !Objects.equals(oldTableType, targetTableType);
        int peopleDelta = newPeople - oldPeople;
        DepositAdjustment depositAdjustment = evaluateDepositAdjustment(booking, newPeople, manualDepositHandled);
        if (!depositAdjustment.allowed()) {
            return RescheduleResult.fail(depositAdjustment.message(), booking, depositAdjustment);
        }
        if (!slotChanged && peopleDelta == 0) {
            return RescheduleResult.ok(booking, false, depositAdjustment);
        }

        if (slotChanged) {
            if (!bookingSlotInventory.reserve(booking.getShopId(), newDate, newTime, targetTableType, newPeople)) {
                return RescheduleResult.fail("新時段目前已額滿，原訂位已保留不變", booking);
            }
            releaseOldSlot(booking.getShopId(), oldDate, oldTime, oldTableType, oldPeople);
        } else if (peopleDelta > 0) {
            if (!bookingSlotInventory.reserve(booking.getShopId(), oldDate, oldTime, oldTableType, peopleDelta)) {
                return RescheduleResult.fail("此時段剩餘座位不足，原訂位已保留不變", booking);
            }
        } else {
            bookingSlotInventory.release(booking.getShopId(), oldDate, oldTime, oldTableType, -peopleDelta);
            availabilityNotificationService.triggerIfAvailable(
                    booking.getShopId(),
                    oldDate,
                    oldTime,
                    oldTableType
            );
        }

        booking.setBookingDate(newDate);
        booking.setBookingTime(newTime);
        booking.setTableType(targetTableType);
        booking.setPeople(newPeople);
        if (Boolean.TRUE.equals(booking.getNeedsDeposit()) && booking.getDepositPerPerson() != null) {
            booking.setDepositTotal(booking.getDepositPerPerson() * newPeople);
        }
        if (Boolean.TRUE.equals(booking.getParkingReminderEnabled())) {
            booking.setParkingReminderSentAt(null);
        }

        bookingRepo.saveAndFlush(booking);
        bookingLineNotificationService.pushBookingUpdated(booking, "rescheduled");
        return RescheduleResult.ok(booking, true, depositAdjustment);
    }

    private DepositAdjustment evaluateDepositAdjustment(BookingJpa booking, int newPeople, boolean manualDepositHandled) {
        boolean needsDeposit = Boolean.TRUE.equals(booking.getNeedsDeposit());
        int currentTotal = intOrZero(booking.getDepositTotal());
        int depositPerPerson = intOrZero(booking.getDepositPerPerson());
        int proposedTotal = needsDeposit ? depositPerPerson * newPeople : 0;
        int delta = proposedTotal - currentTotal;
        boolean paid = booking.getStatus() != null && booking.getStatus() == BookingHoldService.STATUS_PAID;

        if (paid && delta != 0 && manualDepositHandled) {
            String adjustmentText = delta > 0
                    ? "已由店家人工處理加收訂金 NT$ " + delta
                    : "已由店家人工處理退款 NT$ " + Math.abs(delta);
            return DepositAdjustment.allowedAfterManualHandling(
                    currentTotal,
                    proposedTotal,
                    delta,
                    adjustmentText
            );
        }
        if (paid && delta > 0) {
            return DepositAdjustment.blocked(
                    currentTotal,
                    proposedTotal,
                    delta,
                    "改單會增加訂金 NT$ " + delta + "，需由店家人工處理後再確認。原訂位已保留不變。"
            );
        }
        if (paid && delta < 0) {
            return DepositAdjustment.blocked(
                    currentTotal,
                    proposedTotal,
                    delta,
                    "改單會產生訂金退款 NT$ " + Math.abs(delta) + "，需由店家人工處理後再確認。原訂位已保留不變。"
            );
        }

        String message;
        if (delta == 0) {
            message = "訂金不變";
        } else if (booking.getStatus() != null && booking.getStatus() == BookingHoldService.STATUS_PENDING_PAYMENT) {
            message = "待付款訂金會從 NT$ " + currentTotal + " 調整為 NT$ " + proposedTotal;
        } else {
            message = "訂金會從 NT$ " + currentTotal + " 調整為 NT$ " + proposedTotal;
        }
        return DepositAdjustment.allowed(currentTotal, proposedTotal, delta, message);
    }

    private int intOrZero(Integer value) {
        return value != null ? value : 0;
    }

    private void releaseOldSlot(Long shopId, LocalDate oldDate, String oldTime, String oldTableType, int oldPeople) {
        bookingSlotInventory.release(shopId, oldDate, oldTime, oldTableType, oldPeople);
        availabilityNotificationService.triggerIfAvailable(shopId, oldDate, oldTime, oldTableType);
    }

    private String normalizeTableType(String tableType) {
        if (tableType == null || tableType.isBlank()) {
            return "normal";
        }
        return tableType;
    }

    public record DepositAdjustment(
            boolean allowed,
            boolean manualHandlingRequired,
            int currentDepositTotal,
            int proposedDepositTotal,
            int delta,
            String message
    ) {
        static DepositAdjustment allowed(int currentDepositTotal, int proposedDepositTotal, int delta, String message) {
            return new DepositAdjustment(true, false, currentDepositTotal, proposedDepositTotal, delta, message);
        }

        static DepositAdjustment allowedAfterManualHandling(
                int currentDepositTotal,
                int proposedDepositTotal,
                int delta,
                String message
        ) {
            return new DepositAdjustment(true, true, currentDepositTotal, proposedDepositTotal, delta, message);
        }

        static DepositAdjustment blocked(int currentDepositTotal, int proposedDepositTotal, int delta, String message) {
            return new DepositAdjustment(false, true, currentDepositTotal, proposedDepositTotal, delta, message);
        }

        public Map<String, Object> toPayload() {
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("allowed", allowed);
            out.put("manualHandlingRequired", manualHandlingRequired);
            out.put("currentDepositTotal", currentDepositTotal);
            out.put("proposedDepositTotal", proposedDepositTotal);
            out.put("delta", delta);
            out.put("message", message);
            return out;
        }
    }

    public record RescheduleResult(
            boolean success,
            String error,
            BookingJpa booking,
            boolean changed,
            DepositAdjustment depositPolicy
    ) {
        public static RescheduleResult ok(BookingJpa booking, boolean changed) {
            return ok(booking, changed, null);
        }

        public static RescheduleResult ok(BookingJpa booking, boolean changed, DepositAdjustment depositPolicy) {
            return new RescheduleResult(true, null, booking, changed, depositPolicy);
        }

        public static RescheduleResult fail(String error, BookingJpa booking) {
            return fail(error, booking, null);
        }

        public static RescheduleResult fail(String error, BookingJpa booking, DepositAdjustment depositPolicy) {
            return new RescheduleResult(false, error, booking, false, depositPolicy);
        }
    }
}
