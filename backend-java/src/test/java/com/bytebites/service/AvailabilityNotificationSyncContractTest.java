package com.bytebites.service;

import com.bytebites.dto.Result;
import com.bytebites.dto.UserDTO;
import com.bytebites.service.jpa.UserJpaService;
import com.bytebites.utils.UserHolder;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
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
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class AvailabilityNotificationSyncContractTest {
    private static final Long USER_ID = 1012L;
    private static final Long SHOP_ID = 10009L;
    private static final Long WATCH_ID = 77L;
    private static final Long NOTIFICATION_ID = 9001L;
    private static final String LINE_USER_ID = "Udemo-sync";
    private static final LocalDate BOOKING_DATE = LocalDate.now().plusDays(3);

    @Mock
    private JdbcTemplate jdbcTemplate;
    @Mock
    private LineNotificationClient lineNotificationClient;
    @Mock
    private UserJpaService userJpaService;
    @Mock
    private LineActionTokenService lineActionTokenService;

    private AvailabilityNotificationService service;

    @BeforeEach
    void setUp() {
        service = new AvailabilityNotificationService(
                jdbcTemplate,
                lineNotificationClient,
                userJpaService,
                lineActionTokenService
        );
    }

    @AfterEach
    void tearDown() {
        UserHolder.removeUser();
    }

    @Test
    void releasedSlotCreatesWebNotificationAndPushesLine() {
        Map<String, Object> watch = Map.of(
                "id", WATCH_ID,
                "user_id", USER_ID,
                "shop_id", SHOP_ID,
                "shop_name", "橘色涮涮屋 信義館",
                "line_user_id", LINE_USER_ID,
                "booking_date", BOOKING_DATE,
                "booking_time", "19:00",
                "table_type", "normal",
                "people", 2
        );
        when(jdbcTemplate.update(contains("INSERT IGNORE INTO tb_booking_slot_inventory"), eq(SHOP_ID), eq(BOOKING_DATE), eq("19:00"), eq("normal")))
                .thenReturn(1);
        when(jdbcTemplate.queryForMap(contains("GREATEST(capacity - booked_count"), eq(SHOP_ID), eq(BOOKING_DATE), eq("19:00"), eq("normal")))
                .thenReturn(Map.of("capacity", 8, "bookedCount", 6, "remaining", 2));
        when(jdbcTemplate.queryForList(contains("FROM tb_availability_watch"), eq(SHOP_ID), eq(BOOKING_DATE), eq("19:00"), eq("normal"), eq(2)))
                .thenReturn(List.of(watch));
        when(jdbcTemplate.update(contains("UPDATE tb_availability_watch"), eq("TRIGGERED"), eq(WATCH_ID))).thenReturn(1);
        when(jdbcTemplate.update(contains("INSERT IGNORE INTO tb_user_notification"), eq(USER_ID), anyString(), anyString(), eq(SHOP_ID), eq(WATCH_ID), eq("UNREAD")))
                .thenReturn(1);
        when(jdbcTemplate.queryForObject(eq("SELECT id FROM tb_user_notification WHERE watch_id = ?"), eq(Long.class), eq(WATCH_ID)))
                .thenReturn(NOTIFICATION_ID);
        when(userJpaService.findLineNotificationUserId(USER_ID)).thenReturn(Optional.of(LINE_USER_ID));

        service.triggerIfAvailable(SHOP_ID, BOOKING_DATE, "19:00", "normal");

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> pushCaptor = ArgumentCaptor.forClass(Map.class);
        verify(lineNotificationClient).pushAvailabilityReleased(pushCaptor.capture(), eq(NOTIFICATION_ID));
        assertThat(pushCaptor.getValue())
                .containsEntry("id", WATCH_ID)
                .containsEntry("shop_id", SHOP_ID)
                .containsEntry("shop_name", "橘色涮涮屋 信義館")
                .containsEntry("line_user_id", LINE_USER_ID);
    }

    @Test
    void webNotificationsExposeReleasedSlotWithLineIdentity() {
        UserHolder.saveUser(webUser());
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("id", NOTIFICATION_ID);
        item.put("type", "AVAILABILITY_RELEASED");
        item.put("title", "橘色涮涮屋 信義館 有空位了");
        item.put("body", BOOKING_DATE + " 19:00 可訂 2 人，請盡快完成訂位。");
        item.put("shopId", SHOP_ID);
        item.put("watchId", WATCH_ID);
        item.put("status", "UNREAD");
        item.put("date", BOOKING_DATE);
        item.put("time", "19:00");
        item.put("tableType", "normal");
        item.put("people", 2);
        item.put("lineUserId", LINE_USER_ID);
        item.put("shopName", "橘色涮涮屋 信義館");
        when(jdbcTemplate.queryForList(contains("FROM tb_user_notification"), eq(USER_ID))).thenReturn(List.of(item));
        when(jdbcTemplate.queryForObject(contains("SELECT COUNT(*)"), eq(Integer.class), eq(USER_ID))).thenReturn(1);

        Result result = service.myNotifications();

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data).containsEntry("unreadCount", 1);
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> items = (List<Map<String, Object>>) data.get("items");
        assertThat(items).hasSize(1);
        assertThat(items.get(0))
                .containsEntry("type", "AVAILABILITY_RELEASED")
                .containsEntry("shopId", SHOP_ID)
                .containsEntry("watchId", WATCH_ID)
                .containsEntry("lineUserId", LINE_USER_ID);
    }

    private UserDTO webUser() {
        UserDTO user = new UserDTO();
        user.setId(USER_ID);
        user.setLineUserId(LINE_USER_ID);
        user.setNickName("Demo User");
        return user;
    }
}
