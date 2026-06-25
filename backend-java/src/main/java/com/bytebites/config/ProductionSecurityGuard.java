package com.bytebites.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

@Component
public class ProductionSecurityGuard implements ApplicationRunner {

    static final String DEFAULT_JWT_SECRET =
            "change-me-in-production-this-is-only-for-dev-environment-must-be-at-least-256-bits";

    private final boolean strictSecurityMode;
    private final boolean demoModeEnabled;
    private final String jwtSecret;

    public ProductionSecurityGuard(
            @Value("${bytebites.security.strict-mode:${SECURITY_STRICT_MODE:false}}") boolean strictSecurityMode,
            @Value("${bytebites.demo-mode.enabled:${DEMO_MODE_ENABLED:true}}") boolean demoModeEnabled,
            @Value("${jwt.secret:" + DEFAULT_JWT_SECRET + "}") String jwtSecret
    ) {
        this.strictSecurityMode = strictSecurityMode;
        this.demoModeEnabled = demoModeEnabled;
        this.jwtSecret = jwtSecret;
    }

    @Override
    public void run(ApplicationArguments args) {
        List<String> failures = validate(strictSecurityMode, demoModeEnabled, jwtSecret);
        if (!failures.isEmpty()) {
            throw new IllegalStateException("Production security guard failed: " + String.join("; ", failures));
        }
    }

    static List<String> validate(boolean strictSecurityMode, boolean demoModeEnabled, String jwtSecret) {
        List<String> failures = new ArrayList<>();
        if (!strictSecurityMode) {
            return failures;
        }

        if (demoModeEnabled) {
            failures.add("DEMO_MODE_ENABLED must be false when SECURITY_STRICT_MODE is true");
        }

        String normalizedSecret = jwtSecret == null ? "" : jwtSecret.trim();
        if (normalizedSecret.isEmpty()) {
            failures.add("JWT_SECRET must be set when SECURITY_STRICT_MODE is true");
        } else {
            if (DEFAULT_JWT_SECRET.equals(normalizedSecret) || normalizedSecret.contains("change-me")) {
                failures.add("JWT_SECRET must not use the development default");
            }
            if (normalizedSecret.getBytes(StandardCharsets.UTF_8).length < 32) {
                failures.add("JWT_SECRET must be at least 32 bytes");
            }
        }

        return failures;
    }
}
