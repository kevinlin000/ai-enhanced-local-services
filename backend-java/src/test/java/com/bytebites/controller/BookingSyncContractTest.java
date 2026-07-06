package com.bytebites.controller;

import com.bytebites.dto.Result;
import com.bytebites.dto.UserDTO;
import com.bytebites.domain.jpa.UserJpa;
import com.bytebites.entity.Shop;
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
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.AbstractPlatformTransactionManager;
import org.springframework.transaction.support.DefaultTransactionStatus;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.isNull;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class BookingSyncContractTest {
    private static final Long USER_ID = 1012L;
    private static final Long SHOP_ID = 10009L;
    private static final String LINE_USER_ID = "Udemo-sync";
    private static final ZoneId BUSINESS_ZONE = ZoneId.of("Asia/Taipei");

    @Mock
    private BookingJpaRepository bookingRepo;
    @Mock
    private IShopService shopService;
    @Mock
    private DepositPolicy depositPolicy;
    @Mock
    private BookingHoldService bookingHoldService;
    @Mock
    private BookingSlotInventory bookingSlotInventory;
    @Mock
    private AvailabilityNotificationService availabilityNotificationService;
    @Mock
    private BookingLineNotificationService bookingLineNotificationService;
    @Mock
    private BookingDepositAdjustmentService bookingDepositAdjustmentService;
    @Mock
    private BookingIncidentService bookingIncidentService;
    @Mock
    private ParkingService parkingService;
    @Mock
    private UserJpaService userJpaService;
    @Mock
    private LineActionTokenService lineActionTokenService;
    @Mock
    private JdbcTemplate jdbcTemplate;

    private BookingController controller;
    private BookingRescheduleService bookingRescheduleService;

    @BeforeEach
    void setUp() {
        bookingRescheduleService = new BookingRescheduleService(
                bookingRepo,
                bookingSlotInventory,
                availabilityNotificationService,
                bookingLineNotificationService
        );
        controller = new BookingController(
                bookingRepo,
                shopService,
                depositPolicy,
                new BookingPayloadMapper(),
                bookingRescheduleService,
                bookingDepositAdjustmentService,
                bookingIncidentService,
                bookingHoldService,
                bookingSlotInventory,
                availabilityNotificationService,
                bookingLineNotificationService,
                parkingService,
                userJpaService,
                lineActionTokenService,
                jdbcTemplate,
                new NoopTransactionManager()
        );
        lenient().when(bookingIncidentService.latestIncidentForBookingCode(anyString())).thenReturn(Optional.empty());
    }

    @AfterEach
    void tearDown() {
        UserHolder.removeUser();
    }

    @Test
    void webPaymentSuccessPushesLineAndRefreshesMyBookingsAsPaid() {
        UserHolder.saveUser(webUser());
        BookingJpa booking = pendingBooking();
        when(bookingRepo.findByBookingCode("BK-SYNC-001")).thenReturn(Optional.of(booking));
        when(bookingHoldService.expireIfDue(booking)).thenReturn(false);
        when(bookingRepo.findByUserIdInOrderByCreatedAtDesc(any(Collection.class))).thenReturn(List.of(booking));
        when(shopService.getById(SHOP_ID)).thenReturn(shop());
        when(userJpaService.findById(USER_ID)).thenReturn(Optional.empty());
        when(userJpaService.resolveLineIdentity(LINE_USER_ID, null)).thenReturn(linkedLineUser());

        Result payment = controller.payTest(Map.of("bookingCode", "BK-SYNC-001"));

        assertThat(payment.getSuccess()).isTrue();
        assertThat(booking.getStatus()).isEqualTo(BookingHoldService.STATUS_PAID);
        assertThat(booking.getPaymentTransId()).startsWith("DEMO-");
        verify(bookingRepo).save(booking);
        verify(bookingLineNotificationService).pushBookingUpdated(booking, "paid");

        Result refreshed = controller.myBookings(null, null);
        List<Map<String, Object>> rows = resultList(refreshed);
        assertThat(rows).hasSize(1);
        assertThat(rows.get(0))
                .containsEntry("bookingCode", "BK-SYNC-001")
                .containsEntry("status", "PAID")
                .containsEntry("paymentTransId", booking.getPaymentTransId());
    }

    @Test
    void webCancelPushesLineReleasesCapacityAndTriggersAvailabilityNotification() {
        UserHolder.saveUser(webUser());
        BookingJpa booking = paidBooking("BK-SYNC-002");
        when(bookingRepo.findByBookingCode("BK-SYNC-002")).thenReturn(Optional.of(booking));
        when(bookingHoldService.expireIfDue(booking)).thenReturn(false);
        when(bookingRepo.findByUserIdInOrderByCreatedAtDesc(any(Collection.class))).thenReturn(List.of(booking));
        when(shopService.getById(SHOP_ID)).thenReturn(shop());
        when(userJpaService.findById(USER_ID)).thenReturn(Optional.empty());
        when(userJpaService.resolveLineIdentity(LINE_USER_ID, null)).thenReturn(linkedLineUser());

        Result canceled = controller.cancel("BK-SYNC-002", Map.of());

        assertThat(canceled.getSuccess()).isTrue();
        assertThat(booking.getStatus()).isEqualTo(BookingHoldService.STATUS_CANCELED);
        verify(bookingSlotInventory).release(
                booking.getShopId(),
                booking.getBookingDate(),
                booking.getBookingTime(),
                booking.getTableType(),
                booking.getPeople()
        );
        verify(availabilityNotificationService).triggerIfAvailable(
                SHOP_ID,
                booking.getBookingDate(),
                booking.getBookingTime(),
                booking.getTableType()
        );
        verify(bookingRepo).saveAndFlush(booking);
        verify(bookingLineNotificationService).pushBookingUpdated(booking, "canceled");

        Result refreshed = controller.myBookings(null, null);
        assertThat(resultList(refreshed).get(0))
                .containsEntry("bookingCode", "BK-SYNC-002")
                .containsEntry("status", "CANCELED");
    }

    @Test
    void lineCancelIsVisibleWhenWebMyBookingsRefreshesSameOwner() {
        BookingJpa booking = paidBooking("BK-SYNC-003");
        Map<String, Object> lineBody = Map.of(
                "lineUserId", LINE_USER_ID,
                "lineActionToken", "valid-token"
        );
        when(bookingRepo.findByBookingCode("BK-SYNC-003")).thenReturn(Optional.of(booking));
        when(lineActionTokenService.resolveOwnerId(lineBody)).thenReturn(Optional.of(USER_ID));
        when(bookingHoldService.expireIfDue(booking)).thenReturn(false);
        when(shopService.getById(SHOP_ID)).thenReturn(shop());

        Result lineCanceled = controller.cancel("BK-SYNC-003", lineBody);

        assertThat(lineCanceled.getSuccess()).isTrue();
        assertThat(booking.getStatus()).isEqualTo(BookingHoldService.STATUS_CANCELED);
        verify(bookingLineNotificationService).pushBookingUpdated(booking, "canceled");

        UserHolder.saveUser(webUser());
        when(bookingRepo.findByUserIdInOrderByCreatedAtDesc(any(Collection.class))).thenReturn(List.of(booking));
        when(userJpaService.findById(USER_ID)).thenReturn(Optional.empty());
        when(userJpaService.resolveLineIdentity(LINE_USER_ID, null)).thenReturn(linkedLineUser());

        Result refreshed = controller.myBookings(null, null);

        assertThat(resultList(refreshed).get(0))
                .containsEntry("bookingCode", "BK-SYNC-003")
                .containsEntry("status", "CANCELED");
    }

    @Test
    void lineCanOptIntoDrivingParkingReminderForUpcomingBooking() {
        BookingJpa booking = paidBooking("BK-SYNC-PARK");
        booking.setDrivingToBooking(false);
        booking.setParkingReminderEnabled(false);
        booking.setParkingReminderSentAt(LocalDateTime.now().minusHours(1));
        Map<String, Object> lineBody = Map.of(
                "lineUserId", LINE_USER_ID,
                "lineActionToken", "valid-token",
                "drivingToBooking", true,
                "parkingReminderEnabled", true
        );
        when(bookingRepo.findByBookingCode("BK-SYNC-PARK")).thenReturn(Optional.of(booking));
        when(lineActionTokenService.resolveOwnerId(lineBody)).thenReturn(Optional.of(USER_ID));
        when(shopService.getById(SHOP_ID)).thenReturn(shop());

        Result result = controller.updateParkingPreference("BK-SYNC-PARK", lineBody);

        assertThat(result.getSuccess()).isTrue();
        assertThat(booking.getDrivingToBooking()).isTrue();
        assertThat(booking.getParkingReminderEnabled()).isTrue();
        assertThat(booking.getParkingReminderSentAt()).isNotNull();
        verify(bookingRepo).save(booking);
        verify(bookingLineNotificationService).pushParkingReminder(booking, List.of());
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("bookingCode", "BK-SYNC-PARK")
                .containsEntry("drivingToBooking", true)
                .containsEntry("parkingReminderEnabled", true);
        assertThat(data.get("parkingReminderSentAt")).isNotNull();
    }

    @Test
    void webRescheduleWithSameDepositReservesNewSlotReleasesOldSlotPushesLineAndRefreshesMyBookings() {
        UserHolder.saveUser(webUser());
        BookingJpa booking = paidBooking("BK-SYNC-004");
        booking.setDrivingToBooking(true);
        booking.setParkingReminderEnabled(true);
        booking.setParkingReminderSentAt(LocalDateTime.now().minusHours(1));
        LocalDate oldDate = booking.getBookingDate();
        String oldTime = booking.getBookingTime();
        String oldTableType = booking.getTableType();
        int oldPeople = booking.getPeople();
        LocalDate newDate = oldDate.plusDays(1);
        when(bookingRepo.findByBookingCode("BK-SYNC-004")).thenReturn(Optional.of(booking));
        when(bookingHoldService.expireIfDue(booking)).thenReturn(false);
        when(bookingSlotInventory.reserve(SHOP_ID, newDate, "20:00", "normal", 2)).thenReturn(true);
        when(shopService.getById(SHOP_ID)).thenReturn(shop());
        when(bookingRepo.findByUserIdInOrderByCreatedAtDesc(any(Collection.class))).thenReturn(List.of(booking));
        when(userJpaService.findById(USER_ID)).thenReturn(Optional.empty());
        when(userJpaService.resolveLineIdentity(LINE_USER_ID, null)).thenReturn(linkedLineUser());

        Result result = controller.reschedule("BK-SYNC-004", Map.of(
                "date", newDate.toString(),
                "time", "20:00",
                "people", 2
        ));

        assertThat(result.getSuccess()).isTrue();
        assertThat(booking.getBookingDate()).isEqualTo(newDate);
        assertThat(booking.getBookingTime()).isEqualTo("20:00");
        assertThat(booking.getPeople()).isEqualTo(2);
        assertThat(booking.getDepositTotal()).isEqualTo(600);
        assertThat(booking.getParkingReminderSentAt()).isNull();
        verify(bookingSlotInventory).reserve(SHOP_ID, newDate, "20:00", "normal", 2);
        verify(bookingSlotInventory).release(SHOP_ID, oldDate, oldTime, oldTableType, oldPeople);
        verify(availabilityNotificationService).triggerIfAvailable(SHOP_ID, oldDate, oldTime, oldTableType);
        verify(bookingRepo).saveAndFlush(booking);
        verify(bookingLineNotificationService).pushBookingUpdated(booking, "rescheduled");
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("bookingCode", "BK-SYNC-004")
                .containsEntry("date", newDate.toString())
                .containsEntry("time", "20:00")
                .containsEntry("people", 2)
                .containsEntry("changed", true);
        assertThat(data).containsKey("depositPolicy");

        Result refreshed = controller.myBookings(null, null);
        assertThat(resultList(refreshed).get(0))
                .containsEntry("bookingCode", "BK-SYNC-004")
                .containsEntry("date", newDate.toString())
                .containsEntry("time", "20:00")
                .containsEntry("people", 2)
                .containsEntry("status", "PAID");
    }

    @Test
    void paidRescheduleDefersDepositIncreaseBeforeChangingSlots() {
        UserHolder.saveUser(webUser());
        BookingJpa booking = paidBooking("BK-SYNC-DEPOSIT-INCREASE");
        LocalDate oldDate = booking.getBookingDate();
        String oldTime = booking.getBookingTime();
        int oldPeople = booking.getPeople();
        int oldDepositTotal = booking.getDepositTotal();
        LocalDate newDate = oldDate.plusDays(1);
        when(bookingRepo.findByBookingCode("BK-SYNC-DEPOSIT-INCREASE")).thenReturn(Optional.of(booking));
        when(bookingHoldService.expireIfDue(booking)).thenReturn(false);

        Result result = controller.reschedule("BK-SYNC-DEPOSIT-INCREASE", Map.of(
                "date", newDate.toString(),
                "time", "20:00",
                "people", 4
        ));

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("changed", false)
                .containsEntry("adjustmentRequired", true)
                .containsKey("depositPolicy");
        assertThat(booking.getBookingDate()).isEqualTo(oldDate);
        assertThat(booking.getBookingTime()).isEqualTo(oldTime);
        assertThat(booking.getPeople()).isEqualTo(oldPeople);
        assertThat(booking.getDepositTotal()).isEqualTo(oldDepositTotal);
        verify(bookingSlotInventory, never()).reserve(any(), any(), anyString(), anyString(), anyInt());
        verify(bookingSlotInventory, never()).release(any(), any(), anyString(), anyString(), anyInt());
        verify(bookingRepo, never()).saveAndFlush(booking);
        verify(bookingLineNotificationService, never()).pushBookingUpdated(booking, "rescheduled");
        verify(bookingDepositAdjustmentService).recordRequired(
                eq(booking),
                isNull(),
                eq(newDate),
                eq("20:00"),
                eq("normal"),
                eq(4),
                any(BookingRescheduleService.DepositAdjustment.class),
                eq("CUSTOMER_RESCHEDULE")
        );
    }

    @Test
    void paidRescheduleDefersDepositRefundBeforeChangingCapacity() {
        UserHolder.saveUser(webUser());
        BookingJpa booking = paidBooking("BK-SYNC-DEPOSIT-REFUND");
        booking.setPeople(4);
        booking.setDepositTotal(1200);
        LocalDate oldDate = booking.getBookingDate();
        String oldTime = booking.getBookingTime();
        int oldPeople = booking.getPeople();
        int oldDepositTotal = booking.getDepositTotal();
        when(bookingRepo.findByBookingCode("BK-SYNC-DEPOSIT-REFUND")).thenReturn(Optional.of(booking));
        when(bookingHoldService.expireIfDue(booking)).thenReturn(false);

        Result result = controller.reschedule("BK-SYNC-DEPOSIT-REFUND", Map.of(
                "people", 2
        ));

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("changed", false)
                .containsEntry("adjustmentRequired", true)
                .containsKey("depositPolicy");
        assertThat(booking.getBookingDate()).isEqualTo(oldDate);
        assertThat(booking.getBookingTime()).isEqualTo(oldTime);
        assertThat(booking.getPeople()).isEqualTo(oldPeople);
        assertThat(booking.getDepositTotal()).isEqualTo(oldDepositTotal);
        verify(bookingSlotInventory, never()).reserve(any(), any(), anyString(), anyString(), anyInt());
        verify(bookingSlotInventory, never()).release(any(), any(), anyString(), anyString(), anyInt());
        verify(bookingRepo, never()).saveAndFlush(booking);
        verify(bookingLineNotificationService, never()).pushBookingUpdated(booking, "rescheduled");
    }

    @Test
    void customerAcceptsIncidentProposalByReschedulingThroughBookingService() {
        UserHolder.saveUser(webUser());
        BookingJpa booking = paidBooking("BK-SYNC-PROPOSAL");
        LocalDate bookingDate = booking.getBookingDate();
        String oldTime = booking.getBookingTime();
        int oldPeople = booking.getPeople();
        Map<String, Object> proposal = Map.of(
                "proposalStatus", "PENDING",
                "proposedDate", bookingDate,
                "proposedTime", "19:30",
                "proposedTableType", "normal",
                "proposedPeople", 2,
                "proposalMessage", "店家建議改到 19:30，請確認是否接受。",
                "proposalExpiresAt", futureProposalExpiry()
        );
        when(bookingRepo.findByBookingCode("BK-SYNC-PROPOSAL")).thenReturn(Optional.of(booking));
        when(bookingHoldService.expireIfDue(booking)).thenReturn(false);
        when(jdbcTemplate.queryForList(anyString(), eq(7L), eq("BK-SYNC-PROPOSAL"))).thenReturn(List.of(proposal));
        when(bookingSlotInventory.reserve(SHOP_ID, bookingDate, "19:30", "normal", 2)).thenReturn(true);
        when(shopService.getById(SHOP_ID)).thenReturn(shop());

        Result result = controller.acceptIncidentProposal("BK-SYNC-PROPOSAL", 7L, Map.of());

        assertThat(result.getSuccess()).isTrue();
        assertThat(booking.getBookingTime()).isEqualTo("19:30");
        verify(bookingSlotInventory).reserve(SHOP_ID, bookingDate, "19:30", "normal", 2);
        verify(bookingSlotInventory).release(SHOP_ID, bookingDate, oldTime, "normal", oldPeople);
        verify(availabilityNotificationService).triggerIfAvailable(SHOP_ID, bookingDate, oldTime, "normal");
        verify(bookingLineNotificationService).pushBookingUpdated(booking, "rescheduled");
        verify(jdbcTemplate).update(anyString(), eq(7L), eq("BK-SYNC-PROPOSAL"));
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("bookingCode", "BK-SYNC-PROPOSAL")
                .containsEntry("time", "19:30")
                .containsEntry("changed", true);
        assertThat(data).containsKey("acceptedProposal");
    }

    @Test
    void customerAcceptingIncidentProposalRejectsDepositIncreaseBeforeRescheduling() {
        UserHolder.saveUser(webUser());
        BookingJpa booking = paidBooking("BK-SYNC-PROPOSAL-DEPOSIT");
        LocalDate bookingDate = booking.getBookingDate();
        String oldTime = booking.getBookingTime();
        int oldPeople = booking.getPeople();
        int oldDepositTotal = booking.getDepositTotal();
        Map<String, Object> proposal = Map.of(
                "proposalStatus", "PENDING",
                "proposedDate", bookingDate,
                "proposedTime", "19:30",
                "proposedTableType", "normal",
                "proposedPeople", 4,
                "proposalMessage", "店家建議改到 19:30，請確認是否接受。",
                "proposalExpiresAt", futureProposalExpiry()
        );
        when(bookingRepo.findByBookingCode("BK-SYNC-PROPOSAL-DEPOSIT")).thenReturn(Optional.of(booking));
        when(bookingHoldService.expireIfDue(booking)).thenReturn(false);
        when(jdbcTemplate.queryForList(anyString(), eq(10L), eq("BK-SYNC-PROPOSAL-DEPOSIT"))).thenReturn(List.of(proposal));

        Result result = controller.acceptIncidentProposal("BK-SYNC-PROPOSAL-DEPOSIT", 10L, Map.of());

        assertThat(result.getSuccess()).isFalse();
        assertThat(result.getErrorMsg()).contains("增加訂金");
        assertThat(booking.getBookingTime()).isEqualTo(oldTime);
        assertThat(booking.getPeople()).isEqualTo(oldPeople);
        assertThat(booking.getDepositTotal()).isEqualTo(oldDepositTotal);
        verify(bookingSlotInventory, never()).reserve(any(), any(), anyString(), anyString(), anyInt());
        verify(bookingSlotInventory, never()).release(any(), any(), anyString(), anyString(), anyInt());
        verify(bookingRepo, never()).saveAndFlush(booking);
        verify(bookingLineNotificationService, never()).pushBookingUpdated(booking, "rescheduled");
        verify(bookingDepositAdjustmentService).recordRequired(
                eq(booking),
                eq(10L),
                eq(bookingDate),
                eq("19:30"),
                eq("normal"),
                eq(4),
                any(BookingRescheduleService.DepositAdjustment.class),
                eq("INCIDENT_PROPOSAL")
        );
    }

    @Test
    void customerDeclinesIncidentProposalWithoutRescheduling() {
        UserHolder.saveUser(webUser());
        BookingJpa booking = paidBooking("BK-SYNC-DECLINE");
        String oldTime = booking.getBookingTime();
        Map<String, Object> proposal = Map.of(
                "proposalStatus", "PENDING",
                "proposedDate", booking.getBookingDate(),
                "proposedTime", "19:30",
                "proposedTableType", "normal",
                "proposedPeople", 2,
                "proposalMessage", "店家建議改到 19:30，請確認是否接受。",
                "proposalExpiresAt", futureProposalExpiry()
        );
        when(bookingRepo.findByBookingCode("BK-SYNC-DECLINE")).thenReturn(Optional.of(booking));
        when(bookingHoldService.expireIfDue(booking)).thenReturn(false);
        when(jdbcTemplate.queryForList(anyString(), eq(8L), eq("BK-SYNC-DECLINE"))).thenReturn(List.of(proposal));
        when(jdbcTemplate.update(anyString(), eq(8L), eq("BK-SYNC-DECLINE"))).thenReturn(1);
        when(shopService.getById(SHOP_ID)).thenReturn(shop());

        Result result = controller.declineIncidentProposal("BK-SYNC-DECLINE", 8L, Map.of());

        assertThat(result.getSuccess()).isTrue();
        assertThat(booking.getBookingTime()).isEqualTo(oldTime);
        verify(bookingSlotInventory, never()).reserve(any(), any(), anyString(), anyString(), anyInt());
        verify(bookingSlotInventory, never()).release(any(), any(), anyString(), anyString(), anyInt());
        verify(jdbcTemplate).update(anyString(), eq(8L), eq("BK-SYNC-DECLINE"));
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("bookingCode", "BK-SYNC-DECLINE")
                .containsKey("declinedProposal");
    }

    @Test
    void acceptingExpiredIncidentProposalMarksExpiredWithoutRescheduling() {
        UserHolder.saveUser(webUser());
        BookingJpa booking = paidBooking("BK-SYNC-EXPIRED");
        String oldTime = booking.getBookingTime();
        Map<String, Object> proposal = Map.of(
                "proposalStatus", "PENDING",
                "proposedDate", booking.getBookingDate(),
                "proposedTime", "19:30",
                "proposedTableType", "normal",
                "proposedPeople", 2,
                "proposalMessage", "店家建議改到 19:30，請確認是否接受。",
                "proposalExpiresAt", expiredProposalTime()
        );
        when(bookingRepo.findByBookingCode("BK-SYNC-EXPIRED")).thenReturn(Optional.of(booking));
        when(bookingHoldService.expireIfDue(booking)).thenReturn(false);
        when(jdbcTemplate.queryForList(anyString(), eq(9L), eq("BK-SYNC-EXPIRED"))).thenReturn(List.of(proposal));
        when(jdbcTemplate.update(anyString(), eq(9L), eq("BK-SYNC-EXPIRED"))).thenReturn(1);

        Result result = controller.acceptIncidentProposal("BK-SYNC-EXPIRED", 9L, Map.of());

        assertThat(result.getSuccess()).isFalse();
        assertThat(result.getErrorMsg()).contains("逾期");
        assertThat(booking.getBookingTime()).isEqualTo(oldTime);
        verify(bookingSlotInventory, never()).reserve(any(), any(), anyString(), anyString(), anyInt());
        verify(bookingSlotInventory, never()).release(any(), any(), anyString(), anyString(), anyInt());
        verify(jdbcTemplate).update(anyString(), eq(9L), eq("BK-SYNC-EXPIRED"));
    }

    @Test
    void rescheduleDoesNotReleaseOldSlotWhenNewSlotIsFull() {
        UserHolder.saveUser(webUser());
        BookingJpa booking = paidBooking("BK-SYNC-FULL");
        LocalDate oldDate = booking.getBookingDate();
        String oldTime = booking.getBookingTime();
        String oldTableType = booking.getTableType();
        int oldPeople = booking.getPeople();
        LocalDate newDate = oldDate.plusDays(1);
        when(bookingRepo.findByBookingCode("BK-SYNC-FULL")).thenReturn(Optional.of(booking));
        when(bookingHoldService.expireIfDue(booking)).thenReturn(false);
        when(bookingSlotInventory.reserve(SHOP_ID, newDate, "20:00", "normal", 2)).thenReturn(false);

        Result result = controller.reschedule("BK-SYNC-FULL", Map.of(
                "date", newDate.toString(),
                "time", "20:00",
                "people", 2
        ));

        assertThat(result.getSuccess()).isFalse();
        assertThat(result.getErrorMsg()).contains("原訂位已保留不變");
        assertThat(booking.getBookingDate()).isEqualTo(oldDate);
        assertThat(booking.getBookingTime()).isEqualTo(oldTime);
        assertThat(booking.getTableType()).isEqualTo(oldTableType);
        assertThat(booking.getPeople()).isEqualTo(oldPeople);
        verify(bookingSlotInventory).reserve(SHOP_ID, newDate, "20:00", "normal", 2);
        verify(bookingSlotInventory, never()).release(any(), any(), anyString(), anyString(), anyInt());
        verify(availabilityNotificationService, never()).triggerIfAvailable(any(), any(), anyString(), anyString());
        verify(bookingRepo, never()).saveAndFlush(booking);
        verify(bookingLineNotificationService, never()).pushBookingUpdated(booking, "rescheduled");
    }

    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> resultList(Result result) {
        assertThat(result.getSuccess()).isTrue();
        return (List<Map<String, Object>>) result.getData();
    }

    private LocalDateTime futureProposalExpiry() {
        return LocalDateTime.now(BUSINESS_ZONE).plusMinutes(20);
    }

    private LocalDateTime expiredProposalTime() {
        return LocalDateTime.now(BUSINESS_ZONE).minusMinutes(1);
    }

    private UserDTO webUser() {
        UserDTO user = new UserDTO();
        user.setId(USER_ID);
        user.setLineUserId(LINE_USER_ID);
        user.setNickName("Demo User");
        return user;
    }

    private UserJpa linkedLineUser() {
        UserJpa user = new UserJpa();
        user.setId(USER_ID);
        user.setLineUserId(LINE_USER_ID);
        user.setNickName("Demo User");
        return user;
    }

    private BookingJpa pendingBooking() {
        BookingJpa booking = paidBooking("BK-SYNC-001");
        booking.setStatus(BookingHoldService.STATUS_PENDING_PAYMENT);
        booking.setPaymentTransId(null);
        booking.setHoldExpiresAt(LocalDateTime.now().plusMinutes(8));
        return booking;
    }

    private BookingJpa paidBooking(String bookingCode) {
        BookingJpa booking = new BookingJpa();
        booking.setId(1L);
        booking.setUserId(USER_ID);
        booking.setBookingCode(bookingCode);
        booking.setShopId(SHOP_ID);
        booking.setPeople(2);
        booking.setBookingDate(LocalDate.now(BUSINESS_ZONE).plusDays(3));
        booking.setBookingTime("19:00");
        booking.setTableType("normal");
        booking.setStatus(BookingHoldService.STATUS_PAID);
        booking.setNeedsDeposit(true);
        booking.setDepositPerPerson(300);
        booking.setDepositTotal(600);
        booking.setPaymentTransId("DEMO-EXISTING");
        booking.setCreatedAt(LocalDateTime.now().minusMinutes(5));
        booking.setUpdatedAt(LocalDateTime.now().minusMinutes(4));
        return booking;
    }

    private Shop shop() {
        Shop shop = new Shop();
        shop.setId(SHOP_ID);
        shop.setName("橘色涮涮屋 信義館");
        return shop;
    }

    private static final class NoopTransactionManager extends AbstractPlatformTransactionManager {
        @Override
        protected Object doGetTransaction() {
            return new Object();
        }

        @Override
        protected void doBegin(Object transaction, TransactionDefinition definition) {
        }

        @Override
        protected void doCommit(DefaultTransactionStatus status) {
        }

        @Override
        protected void doRollback(DefaultTransactionStatus status) {
        }
    }
}
