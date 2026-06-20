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
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class DiningMemoryServiceTest {
    private static final Long USER_ID = 1012L;
    private static final Long SHOP_ID = 10009L;

    @Mock
    private JdbcTemplate jdbcTemplate;
    @Mock
    private BookingJpaRepository bookingRepo;
    @Mock
    private IShopService shopService;

    private DiningMemoryService service;

    @BeforeEach
    void setUp() {
        service = new DiningMemoryService(jdbcTemplate, bookingRepo, shopService);
        UserDTO user = new UserDTO();
        user.setId(USER_ID);
        UserHolder.saveUser(user);
    }

    @AfterEach
    void tearDown() {
        UserHolder.removeUser();
    }

    @Test
    void saveBookingMemoryPersistsPrivateTagsForBookingOwner() {
        BookingJpa booking = booking("BK-MEMORY", USER_ID);
        when(bookingRepo.findByBookingCode("BK-MEMORY")).thenReturn(Optional.of(booking));
        when(shopService.getById(SHOP_ID)).thenReturn(shop());

        Result result = service.saveBookingMemory(
                "BK-MEMORY",
                Map.of(
                        "rating", 3,
                        "tags", List.of("安靜", "服務快"),
                        "note", "下次想坐內側"
                )
        );

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("bookingCode", "BK-MEMORY")
                .containsEntry("shopId", SHOP_ID)
                .containsEntry("shopName", "橘色涮涮屋 信義館")
                .containsEntry("rating", 3)
                .containsEntry("note", "下次想坐內側")
                .containsEntry("doNotRecommend", false);
        @SuppressWarnings("unchecked")
        List<String> tags = (List<String>) data.get("tags");
        assertThat(tags).containsExactly("安靜", "服務快");
        verify(jdbcTemplate).update(
                anyString(),
                eq(USER_ID),
                eq("BK-MEMORY"),
                eq(SHOP_ID),
                eq(3),
                eq("[\"安靜\",\"服務快\"]"),
                eq("下次想坐內側"),
                eq(false)
        );
    }

    @Test
    void saveBookingMemoryRejectsAnotherUsersBooking() {
        when(bookingRepo.findByBookingCode("BK-OTHER")).thenReturn(Optional.of(booking("BK-OTHER", 999L)));

        Result result = service.saveBookingMemory("BK-OTHER", Map.of("rating", 2, "tags", List.of("安靜")));

        assertThat(result.getSuccess()).isFalse();
        assertThat(result.getErrorMsg()).contains("無權");
    }

    @Test
    void myMemoryReturnsTagCountsAndAvoidShopIds() {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("bookingCode", "BK-MEMORY");
        row.put("shopId", SHOP_ID);
        row.put("shopName", "橘色涮涮屋 信義館");
        row.put("rating", 1);
        row.put("tagsJson", "[\"太吵\",\"不再推薦\"]");
        row.put("note", "靠窗位太吵");
        row.put("doNotRecommend", true);
        when(jdbcTemplate.queryForList(anyString(), eq(USER_ID))).thenReturn(List.of(row));

        Result result = service.myMemory();

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        @SuppressWarnings("unchecked")
        Map<String, Integer> tagCounts = (Map<String, Integer>) data.get("tagCounts");
        @SuppressWarnings("unchecked")
        List<Long> avoidShopIds = (List<Long>) data.get("avoidShopIds");
        assertThat(tagCounts).containsEntry("太吵", 1).containsEntry("不再推薦", 1);
        assertThat(avoidShopIds).containsExactly(SHOP_ID);
    }

    private BookingJpa booking(String bookingCode, Long userId) {
        BookingJpa booking = new BookingJpa();
        booking.setUserId(userId);
        booking.setBookingCode(bookingCode);
        booking.setShopId(SHOP_ID);
        booking.setPeople(2);
        booking.setBookingDate(LocalDate.now().plusDays(1));
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
