package com.bytebites.service;

import com.bytebites.domain.jpa.UserJpa;
import com.bytebites.service.jpa.UserJpaService;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Base64;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class LineActionTokenServiceTest {
    private static final String SECRET = "test-line-action-secret";

    @Test
    void resolveOwnerIdAcceptsValidToken() {
        UserJpaService userJpaService = mock(UserJpaService.class);
        UserJpa user = new UserJpa();
        user.setId(1012L);
        when(userJpaService.resolveLineIdentity("Uabc123", "林庭蔚")).thenReturn(user);
        LineActionTokenService service = service(userJpaService);

        Optional<Long> result = service.resolveOwnerId(
                "Uabc123",
                token("Uabc123", Instant.now().plusSeconds(60).getEpochSecond()),
                "林庭蔚"
        );

        assertThat(result).contains(1012L);
    }

    @Test
    void resolveOwnerIdRejectsMismatchedLineUserId() {
        UserJpaService userJpaService = mock(UserJpaService.class);
        LineActionTokenService service = service(userJpaService);

        Optional<Long> result = service.resolveOwnerId(
                "Uother",
                token("Uabc123", Instant.now().plusSeconds(60).getEpochSecond()),
                "林庭蔚"
        );

        assertThat(result).isEmpty();
        verify(userJpaService, never()).resolveLineIdentity("Uother", "林庭蔚");
    }

    @Test
    void resolveOwnerIdRejectsExpiredToken() {
        UserJpaService userJpaService = mock(UserJpaService.class);
        LineActionTokenService service = service(userJpaService);

        Optional<Long> result = service.resolveOwnerId(
                "Uabc123",
                token("Uabc123", Instant.now().minusSeconds(1).getEpochSecond()),
                "林庭蔚"
        );

        assertThat(result).isEmpty();
        verify(userJpaService, never()).resolveLineIdentity("Uabc123", "林庭蔚");
    }

    private static LineActionTokenService service(UserJpaService userJpaService) {
        LineActionTokenService service = new LineActionTokenService(userJpaService);
        ReflectionTestUtils.setField(service, "secret", SECRET);
        return service;
    }

    private static String token(String lineUserId, long expiresAt) {
        try {
            String payload = lineUserId + "|line_action|" + expiresAt;
            String payloadB64 = Base64.getUrlEncoder().withoutPadding()
                    .encodeToString(payload.getBytes(StandardCharsets.UTF_8));
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(SECRET.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            String sig = Base64.getUrlEncoder().withoutPadding()
                    .encodeToString(mac.doFinal(payloadB64.getBytes(StandardCharsets.UTF_8)));
            return "v1." + payloadB64 + "." + sig;
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }
}
