package com.bytebites.controller;

import com.bytebites.domain.jpa.UserJpa;
import com.bytebites.dto.Result;
import com.bytebites.dto.UserDTO;
import com.bytebites.service.jpa.UserJpaService;
import com.bytebites.utils.UserHolder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/auth")
public class AuthMeController {

    private final UserJpaService userJpaService;

    public AuthMeController(UserJpaService userJpaService) {
        this.userJpaService = userJpaService;
    }

    @GetMapping("/me")
    public Result me() {
        UserDTO current = UserHolder.getUser();
        if (current == null || current.getId() == null) {
            return Result.fail("unauthenticated");
        }

        UserJpa user = userJpaService.findById(current.getId()).orElse(null);
        if (user == null) {
            return Result.fail("user not found");
        }

        String displayName = firstNonBlank(user.getLineDisplayName(), user.getNickName(), "ByteBites User");
        String pictureUrl = firstNonBlank(user.getLinePictureUrl(), user.getIcon(), null);

        return Result.ok(new AuthUserView(
                user.getId(),
                displayName,
                pictureUrl,
                user.getLineUserId() != null
        ));
    }

    private String firstNonBlank(String... values) {
        for (String value : values) {
            if (value != null && !value.isBlank()) {
                return value;
            }
        }
        return null;
    }

    public record AuthUserView(
            Long id,
            String displayName,
            String pictureUrl,
            boolean lineLinked
    ) {
    }
}
