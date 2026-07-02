package com.bytebites.config;

import com.bytebites.utils.UserHolder;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;

class DemoModeFilterTest {

    @AfterEach
    void tearDown() {
        UserHolder.removeUser();
    }

    @Test
    void enabledDemoModeHeaderSetsDemoUserOnlyDuringRequest() throws Exception {
        DemoModeFilter filter = new DemoModeFilter(true);
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.addHeader("X-Demo-Mode", "true");
        AtomicReference<Long> userIdInsideChain = new AtomicReference<>();

        filter.doFilter(request, new MockHttpServletResponse(), (req, res) -> {
            assertThat(UserHolder.getUser()).isNotNull();
            userIdInsideChain.set(UserHolder.getUser().getId());
        });

        assertThat(userIdInsideChain).hasValue(1001L);
        assertThat(UserHolder.getUser()).isNull();
    }

    @Test
    void disabledDemoModeHeaderDoesNotSetDemoUser() throws Exception {
        DemoModeFilter filter = new DemoModeFilter(false);
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.addHeader("X-Demo-Mode", "true");
        AtomicReference<Object> userInsideChain = new AtomicReference<>("unset");

        filter.doFilter(request, new MockHttpServletResponse(), (req, res) ->
                userInsideChain.set(UserHolder.getUser())
        );

        assertThat(userInsideChain).hasValue(null);
        assertThat(UserHolder.getUser()).isNull();
    }
}
