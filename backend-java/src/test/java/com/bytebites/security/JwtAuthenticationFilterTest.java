package com.bytebites.security;

import com.bytebites.controller.AuthController;
import com.bytebites.utils.UserHolder;
import jakarta.servlet.http.Cookie;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.core.context.SecurityContextHolder;

import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;

class JwtAuthenticationFilterTest {

    private final JwtTokenProvider tokenProvider =
            new JwtTokenProvider("test-secret-with-at-least-32-bytes-2026", 1);
    private final JwtAuthenticationFilter filter = new JwtAuthenticationFilter(tokenProvider);

    @AfterEach
    void tearDown() {
        UserHolder.removeUser();
        SecurityContextHolder.clearContext();
    }

    @Test
    void authenticatesFromHttpOnlyCookieWhenAuthorizationHeaderMissing() throws Exception {
        String token = tokenProvider.issue(1012L, "Ucookie");
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.setCookies(new Cookie(AuthController.AUTH_COOKIE, token));
        AtomicReference<Long> userIdInsideChain = new AtomicReference<>();

        filter.doFilter(request, new MockHttpServletResponse(), (req, res) -> {
            assertThat(SecurityContextHolder.getContext().getAuthentication()).isNotNull();
            assertThat(UserHolder.getUser()).isNotNull();
            userIdInsideChain.set(UserHolder.getUser().getId());
        });

        assertThat(userIdInsideChain).hasValue(1012L);
        assertThat(UserHolder.getUser()).isNull();
        assertThat(SecurityContextHolder.getContext().getAuthentication()).isNull();
    }
}
