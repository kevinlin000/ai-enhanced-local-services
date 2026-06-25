package com.bytebites.config;

import org.junit.jupiter.api.Test;
import org.springframework.security.authentication.AnonymousAuthenticationToken;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class SecurityConfigTest {

    @Test
    void localDemoModeAllowsProtectedDemoRoutesWithoutAuthentication() {
        assertThat(SecurityConfig.allowsProtectedDemoRoute(false, null)).isTrue();
    }

    @Test
    void strictModeRejectsMissingAuthentication() {
        assertThat(SecurityConfig.allowsProtectedDemoRoute(true, null)).isFalse();
    }

    @Test
    void strictModeRejectsAnonymousAuthentication() {
        AnonymousAuthenticationToken anonymous = new AnonymousAuthenticationToken(
                "anonymous",
                "anonymousUser",
                List.of(new SimpleGrantedAuthority("ROLE_ANONYMOUS"))
        );

        assertThat(SecurityConfig.allowsProtectedDemoRoute(true, anonymous)).isFalse();
    }

    @Test
    void strictModeAllowsRealAuthentication() {
        UsernamePasswordAuthenticationToken authenticated =
                new UsernamePasswordAuthenticationToken(1001L, null, List.of());

        assertThat(SecurityConfig.allowsProtectedDemoRoute(true, authenticated)).isTrue();
    }
}
