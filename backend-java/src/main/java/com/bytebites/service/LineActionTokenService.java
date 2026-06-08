package com.bytebites.service;

import com.bytebites.service.jpa.UserJpaService;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Base64;
import java.util.Map;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class LineActionTokenService {
    private static final String VERSION = "v1";
    private static final String SCOPE = "line_action";

    private final UserJpaService userJpaService;

    @Value("${bytebites.line-action-secret:${LINE_ACTION_SECRET:${LINE_INTERNAL_WEBHOOK_SECRET:dev-line-action-secret}}}")
    private String secret;

    public Optional<Long> resolveOwnerId(Map<String, Object> body) {
        String lineUserId = stringValue(body.get("lineUserId"));
        String token = stringValue(body.get("lineActionToken"));
        String displayName = stringValue(body.get("lineDisplayName"));
        return resolveOwnerId(lineUserId, token, displayName);
    }

    public Optional<Long> resolveOwnerId(String lineUserId, String token, String displayName) {
        String normalizedLineUserId = lineUserId == null ? "" : lineUserId.trim();
        if (normalizedLineUserId.isBlank() || normalizedLineUserId.length() > 128) return Optional.empty();
        if (!verify(token, normalizedLineUserId)) return Optional.empty();
        return Optional.of(userJpaService.resolveLineIdentity(normalizedLineUserId, displayName).getId());
    }

    public boolean verify(String token, String expectedLineUserId) {
        try {
            String normalizedToken = token == null ? "" : token.trim();
            if (normalizedToken.isBlank()) return false;
            String[] parts = normalizedToken.split("\\.");
            if (parts.length != 3 || !VERSION.equals(parts[0])) return false;

            String payloadB64 = parts[1];
            String expectedSig = sign(payloadB64);
            if (!constantTimeEquals(expectedSig, parts[2])) return false;

            String payload = new String(Base64.getUrlDecoder().decode(payloadB64), StandardCharsets.UTF_8);
            String[] fields = payload.split("\\|", -1);
            if (fields.length != 3) return false;
            String lineUserId = fields[0];
            String scope = fields[1];
            long expiresAt = Long.parseLong(fields[2]);
            if (!SCOPE.equals(scope)) return false;
            if (Instant.now().getEpochSecond() > expiresAt) return false;
            return constantTimeEquals(lineUserId, expectedLineUserId == null ? "" : expectedLineUserId.trim());
        } catch (Exception ignored) {
            return false;
        }
    }

    private String sign(String payloadB64) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(secretBytes(), "HmacSHA256"));
        return Base64.getUrlEncoder().withoutPadding()
                .encodeToString(mac.doFinal(payloadB64.getBytes(StandardCharsets.UTF_8)));
    }

    private byte[] secretBytes() {
        String value = secret == null || secret.isBlank() ? "dev-line-action-secret" : secret.trim();
        return value.getBytes(StandardCharsets.UTF_8);
    }

    private boolean constantTimeEquals(String a, String b) {
        return MessageDigestSafe.equals(
                (a == null ? "" : a).getBytes(StandardCharsets.UTF_8),
                (b == null ? "" : b).getBytes(StandardCharsets.UTF_8)
        );
    }

    private String stringValue(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private static final class MessageDigestSafe {
        private static boolean equals(byte[] a, byte[] b) {
            return java.security.MessageDigest.isEqual(a, b);
        }
    }
}
