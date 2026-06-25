package com.bytebites.controller;

import com.bytebites.service.IUserService;
import com.bytebites.service.oauth.LineOAuthService;
import com.bytebites.service.oauth.LineOAuthService.LineProfile;
import jakarta.servlet.http.Cookie;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class AuthControllerTest {

    @Mock
    private LineOAuthService lineOAuthService;
    @Mock
    private IUserService userService;

    @Test
    void callbackSetsHttpOnlyAuthCookieAndKeepsLegacyHashToken() throws Exception {
        AuthController controller = new AuthController(lineOAuthService, userService);
        configure(controller);
        LineProfile profile = new LineProfile();
        profile.setSub("Uline");

        when(lineOAuthService.exchangeCodeForProfile("line-code")).thenReturn(profile);
        when(userService.loginWithLine(profile)).thenReturn("jwt-token-value");

        MockHttpServletRequest request = new MockHttpServletRequest();
        request.setCookies(new Cookie("bb_line_oauth_state", "state-1"));
        MockHttpServletResponse response = new MockHttpServletResponse();

        controller.callback("line-code", null, null, "state-1", request, response);

        List<String> cookies = response.getHeaders("Set-Cookie");
        assertThat(cookies).anySatisfy(cookie -> assertThat(cookie)
                .contains(AuthController.AUTH_COOKIE + "=jwt-token-value")
                .contains("Path=/")
                .contains("HttpOnly")
                .contains("SameSite=Lax")
                .contains("Max-Age=7200")
                .contains("Secure"));
        assertThat(response.getRedirectedUrl()).isEqualTo("https://app.example/auth/callback#token=jwt-token-value");
    }

    private void configure(AuthController controller) {
        ReflectionTestUtils.setField(controller, "frontendUrl", "https://app.example");
        ReflectionTestUtils.setField(controller, "oauthCookiePath", "/api/java/api/auth/line");
        ReflectionTestUtils.setField(controller, "authCookieSecure", true);
        ReflectionTestUtils.setField(controller, "jwtTtlHours", 2L);
    }
}
