package com.bytebites.controller;

import com.bytebites.dto.Result;
import com.bytebites.dto.UserDTO;
import com.bytebites.domain.jpa.UserJpa;
import com.bytebites.entity.Shop;
import com.bytebites.entity.jpa.BookingJpa;
import com.bytebites.repository.BookingJpaRepository;
import com.bytebites.service.AvailabilityNotificationService;
import com.bytebites.service.BookingHoldService;
import com.bytebites.service.BookingLineNotificationService;
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
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class BookingSyncContractTest {
    private static final Long USER_ID = 1012L;
    private static final Long SHOP_ID = 10009L;
    private static final String LINE_USER_ID = "Udemo-sync";

    @Mock
    private BookingJpaRepository bookingRepo;
    @Mock
    private IShopService shopService;
    @Mock
    private DepositPolicy depositPolicy;
    @Mock
    private BookingHoldService bookingHoldService;
    @Mock
    private AvailabilityNotificationService availabilityNotificationService;
    @Mock
    private BookingLineNotificationService bookingLineNotificationService;
    @Mock
    private ParkingService parkingService;
    @Mock
    private UserJpaService userJpaService;
    @Mock
    private LineActionTokenService lineActionTokenService;
    @Mock
    private JdbcTemplate jdbcTemplate;

    private BookingController controller;

    @BeforeEach
    void setUp() {
        controller = new BookingController(
                bookingRepo,
                shopService,
                depositPolicy,
                bookingHoldService,
                availabilityNotificationService,
                bookingLineNotificationService,
                parkingService,
                userJpaService,
                lineActionTokenService,
                jdbcTemplate,
                new NoopTransactionManager()
        );
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
        verify(jdbcTemplate).update(
                contains("UPDATE tb_booking_slot_inventory"),
                eq(booking.getPeople()),
                eq(SHOP_ID),
                eq(booking.getBookingDate()),
                eq(booking.getBookingTime()),
                eq(booking.getTableType())
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

    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> resultList(Result result) {
        assertThat(result.getSuccess()).isTrue();
        return (List<Map<String, Object>>) result.getData();
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
        booking.setBookingDate(LocalDate.now().plusDays(3));
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
