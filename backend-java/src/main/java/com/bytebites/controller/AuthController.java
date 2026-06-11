package com.bytebites.controller;

import com.bytebites.dto.Result;
import com.bytebites.service.IUserService;
import com.bytebites.service.oauth.LineOAuthService;
import com.bytebites.service.oauth.LineOAuthService.LineProfile;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.io.IOException;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.UUID;

@RestController
@RequestMapping("/api/auth/line")
@RequiredArgsConstructor
public class AuthController {
    private static final String STATE_COOKIE = "bb_line_oauth_state";

    private final LineOAuthService lineOAuthService;
    private final IUserService userService;

    @Value("${line.oauth.frontend-url}")
    private String frontendUrl;

    @Value("${line.oauth.cookie-path:/api/auth/line}")
    private String oauthCookiePath;

    @GetMapping("/login")
    public void startLogin(HttpServletResponse resp) throws IOException {
        String state = UUID.randomUUID().toString();
        resp.addHeader("Set-Cookie", STATE_COOKIE + "=" + encode(state)
                + "; Path=" + oauthCookiePath + "; HttpOnly; SameSite=Lax; Max-Age=600");
        try {
            String url = lineOAuthService.buildAuthorizeUrl(state);
            resp.sendRedirect(url);
        } catch (IllegalStateException e) {
            redirectToFrontend(resp, null, e.getMessage());
        }
    }

    @GetMapping("/callback")
    public void callback(
        @RequestParam(required = false) String code,
        @RequestParam(required = false) String error,
        @RequestParam(required = false, name = "error_description") String errorDescription,
        @RequestParam(required = false) String state,
        HttpServletRequest req,
        HttpServletResponse resp
    ) throws IOException {
        if (error != null || code == null || code.isBlank()) {
            clearStateCookie(resp);
            redirectToFrontend(resp, null, errorDescription != null ? errorDescription : "LINE login canceled");
            return;
        }
        String expectedState = readCookie(req, STATE_COOKIE);
        clearStateCookie(resp);
        if (state == null || state.isBlank() || expectedState == null || !expectedState.equals(state)) {
            redirectToFrontend(resp, null, "LINE login state expired. Please try again.");
            return;
        }

        try {
            LineProfile profile = lineOAuthService.exchangeCodeForProfile(code);
            String token = userService.loginWithLine(profile);
            redirectToFrontend(resp, token, null);
        } catch (Exception e) {
            redirectToFrontend(resp, null, e.getMessage());
        }
    }

    private void redirectToFrontend(HttpServletResponse resp, String token, String error) throws IOException {
        StringBuilder url = new StringBuilder(frontendUrl).append("/auth/callback");
        if (token != null && !token.isBlank()) {
            url.append("#token=").append(encode(token));
        } else {
            url.append("?error=").append(encode(error != null ? error : "LINE login failed"));
        }
        resp.sendRedirect(url.toString());
    }

    private String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }

    private String readCookie(HttpServletRequest req, String name) {
        Cookie[] cookies = req.getCookies();
        if (cookies == null) return null;
        for (Cookie cookie : cookies) {
            if (name.equals(cookie.getName())) {
                return cookie.getValue();
            }
        }
        return null;
    }

    private void clearStateCookie(HttpServletResponse resp) {
        resp.addHeader("Set-Cookie", STATE_COOKIE + "=; Path=" + oauthCookiePath + "; HttpOnly; SameSite=Lax; Max-Age=0");
    }
}
