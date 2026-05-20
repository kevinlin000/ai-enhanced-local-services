package com.hmdp.controller;

import com.hmdp.dto.Result;
import com.hmdp.service.IUserService;
import com.hmdp.service.oauth.LineOAuthService;
import com.hmdp.service.oauth.LineOAuthService.LineProfile;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.io.IOException;
import java.util.UUID;

@RestController
@RequestMapping("/api/auth/line")
@RequiredArgsConstructor
public class AuthController {

    private final LineOAuthService lineOAuthService;
    private final IUserService userService;

    @GetMapping("/login")
    public void startLogin(HttpServletResponse resp) throws IOException {
        String state = UUID.randomUUID().toString();
        // TODO: persist state for CSRF check in v1.1
        String url = lineOAuthService.buildAuthorizeUrl(state);
        resp.sendRedirect(url);
    }

    @GetMapping("/callback")
    public Result callback(@RequestParam String code, @RequestParam(required = false) String state) {
        LineProfile profile = lineOAuthService.exchangeCodeForProfile(code);
        String token = userService.loginWithLine(profile);
        return Result.ok(token);
    }
}
