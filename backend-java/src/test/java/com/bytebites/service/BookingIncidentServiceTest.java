package com.bytebites.service;

import com.bytebites.dto.Result;
import com.bytebites.dto.UserDTO;
import com.bytebites.entity.Shop;
import com.bytebites.entity.jpa.BookingJpa;
import com.bytebites.repository.BookingJpaRepository;
import com.bytebites.utils.UserHolder;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class BookingIncidentServiceTest {
    private static final Long USER_ID = 1012L;
    private static final Long SHOP_ID = 10009L;

    @Mock
    private JdbcTemplate jdbcTemplate;
    @Mock
    private BookingJpaRepository bookingRepo;
    @Mock
    private IShopService shopService;
    @Mock
    private BookingLineNotificationService bookingLineNotificationService;
    @Mock
    private LineActionTokenService lineActionTokenService;

    private BookingIncidentService service;

    @BeforeEach
    void setUp() {
        service = new BookingIncidentService(
                jdbcTemplate,
                bookingRepo,
                shopService,
                bookingLineNotificationService,
                lineActionTokenService
        );
        UserDTO user = new UserDTO();
        user.setId(USER_ID);
        UserHolder.saveUser(user);
    }

    @AfterEach
    void tearDown() {
        UserHolder.removeUser();
    }

    @Test
    void createRestaurantDelayIncidentPersistsAndPushesLinePayload() {
        BookingJpa booking = booking();
        when(bookingRepo.findByBookingCode("BK-INCIDENT")).thenReturn(Optional.of(booking));
        when(shopService.getById(SHOP_ID)).thenReturn(shop());
        when(jdbcTemplate.queryForList(anyString(), eq("BK-INCIDENT"))).thenReturn(List.of(openIncidentRow()));

        Result result = service.createIncident(
                "BK-INCIDENT",
                Map.of("incidentType", "RESTAURANT_DELAY", "delayMinutes", 15)
        );

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("bookingCode", "BK-INCIDENT")
                .containsEntry("shopName", "橘色涮涮屋 信義館")
                .containsEntry("incidentType", "RESTAURANT_DELAY")
                .containsEntry("status", "OPEN")
                .containsEntry("delayMinutes", 15)
                .containsEntry("originalTime", "19:00")
                .containsEntry("adjustedTime", "19:15");
        verify(jdbcTemplate).update(
                anyString(),
                eq("BK-INCIDENT"),
                eq(USER_ID),
                eq(SHOP_ID),
                eq("RESTAURANT_DELAY"),
                eq(15),
                eq("19:00"),
                eq("19:15"),
                eq("店家回報約延 15 分鐘"),
                anyString(),
                eq("已保留原訂位"),
                eq("AI_RESCUE")
        );
        verify(bookingLineNotificationService).pushBookingIncident(eq(booking), anyMap());
    }

    @Test
    void createIncidentRejectsAnonymousUserWithoutLineToken() {
        UserHolder.removeUser();
        when(bookingRepo.findByBookingCode("BK-INCIDENT")).thenReturn(Optional.of(booking()));
        when(lineActionTokenService.resolveOwnerId(anyMap())).thenReturn(Optional.empty());

        Result result = service.createIncident(
                "BK-INCIDENT",
                Map.of("incidentType", "CUSTOMER_LATE", "delayMinutes", 20)
        );

        assertThat(result.getSuccess()).isFalse();
        assertThat(result.getErrorMsg()).contains("無權");
    }

    @Test
    void latestIncidentReturnsNormalizedPayload() {
        when(jdbcTemplate.queryForList(anyString(), eq("BK-INCIDENT"))).thenReturn(List.of(openIncidentRow()));

        Optional<Map<String, Object>> result = service.latestIncidentForBookingCode("BK-INCIDENT");

        assertThat(result).isPresent();
        assertThat(result.get())
                .containsEntry("id", 7L)
                .containsEntry("bookingCode", "BK-INCIDENT")
                .containsEntry("title", "店家回報約延 15 分鐘")
                .containsEntry("actionLabel", "已保留原訂位");
    }

    private Map<String, Object> openIncidentRow() {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", 7L);
        row.put("bookingCode", "BK-INCIDENT");
        row.put("userId", USER_ID);
        row.put("shopId", SHOP_ID);
        row.put("shopName", "橘色涮涮屋 信義館");
        row.put("incidentType", "RESTAURANT_DELAY");
        row.put("status", "OPEN");
        row.put("delayMinutes", 15);
        row.put("originalTime", "19:00");
        row.put("adjustedTime", "19:15");
        row.put("title", "店家回報約延 15 分鐘");
        row.put("customerMessage", "店家剛回報前面桌用餐延長，預估 19:15 左右可入座。");
        row.put("actionLabel", "已保留原訂位");
        row.put("source", "AI_RESCUE");
        row.put("createdAt", LocalDateTime.of(2026, 6, 18, 18, 50));
        return row;
    }

    private BookingJpa booking() {
        BookingJpa booking = new BookingJpa();
        booking.setId(1L);
        booking.setUserId(USER_ID);
        booking.setBookingCode("BK-INCIDENT");
        booking.setShopId(SHOP_ID);
        booking.setPeople(2);
        booking.setBookingDate(LocalDate.of(2026, 6, 20));
        booking.setBookingTime("19:00");
        booking.setTableType("normal");
        booking.setStatus(BookingHoldService.STATUS_PAID);
        booking.setNeedsDeposit(true);
        booking.setDepositPerPerson(300);
        booking.setDepositTotal(600);
        return booking;
    }

    private Shop shop() {
        Shop shop = new Shop();
        shop.setId(SHOP_ID);
        shop.setName("橘色涮涮屋 信義館");
        return shop;
    }
}
