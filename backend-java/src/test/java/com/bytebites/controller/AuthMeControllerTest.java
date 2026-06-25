package com.bytebites.controller;

import com.bytebites.dto.Result;
import com.bytebites.service.jpa.UserJpaService;
import com.bytebites.utils.UserHolder;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletResponse;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

class AuthMeControllerTest {

    @Test
    void meReturnsAnonymousPayloadWithoutAuthentication() {
        UserHolder.removeUser();
        AuthMeController controller = new AuthMeController(mock(UserJpaService.class));

        Result result = controller.me();

        assertThat(result.getSuccess()).isFalse();
        assertThat(result.getErrorMsg()).isEqualTo("unauthenticated");
    }

    @Test
    void logoutClearsHttpOnlyAuthCookie() {
        AuthMeController controller = new AuthMeController(mock(UserJpaService.class));
        MockHttpServletResponse response = new MockHttpServletResponse();

        Result result = controller.logout(response);

        assertThat(result.getSuccess()).isTrue();
        assertThat(response.getHeaders("Set-Cookie")).anySatisfy(cookie -> assertThat(cookie)
                .contains(AuthController.AUTH_COOKIE + "=")
                .contains("Path=/")
                .contains("HttpOnly")
                .contains("SameSite=Lax")
                .contains("Max-Age=0"));
    }
}
