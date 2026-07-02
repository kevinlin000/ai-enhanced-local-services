package com.bytebites.config;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class ProductionSecurityGuardTest {

    @Test
    void localDemoModeAllowsDevelopmentDefaults() {
        assertThat(ProductionSecurityGuard.validate(
                false,
                true,
                ProductionSecurityGuard.DEFAULT_JWT_SECRET
        )).isEmpty();
    }

    @Test
    void strictModeRequiresDemoModeDisabled() {
        assertThat(ProductionSecurityGuard.validate(
                true,
                true,
                strongSecret()
        )).containsExactly("DEMO_MODE_ENABLED must be false when SECURITY_STRICT_MODE is true");
    }

    @Test
    void strictModeRejectsDefaultJwtSecret() {
        assertThat(ProductionSecurityGuard.validate(
                true,
                false,
                ProductionSecurityGuard.DEFAULT_JWT_SECRET
        )).containsExactly("JWT_SECRET must not use the development default");
    }

    @Test
    void strictModeRejectsShortJwtSecret() {
        assertThat(ProductionSecurityGuard.validate(
                true,
                false,
                "short-secret"
        )).containsExactly("JWT_SECRET must be at least 32 bytes");
    }

    @Test
    void strictModeAcceptsProductionConfiguration() {
        assertThat(ProductionSecurityGuard.validate(
                true,
                false,
                strongSecret()
        )).isEmpty();
    }

    private static String strongSecret() {
        return "prod-secret-with-at-least-32-bytes-2026";
    }
}
