package com.bytebites.config;

import com.bytebites.dto.UserDTO;
import com.bytebites.utils.UserHolder;
import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

import java.io.IOException;

@Component
@Order(0)
public class DemoModeFilter implements Filter {

    private static final Long DEMO_USER_ID = 1001L;
    private final boolean enabled;

    public DemoModeFilter(@Value("${bytebites.demo-mode.enabled:${DEMO_MODE_ENABLED:true}}") boolean enabled) {
        this.enabled = enabled;
    }

    @Override
    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain)
            throws IOException, ServletException {
        HttpServletRequest http = (HttpServletRequest) req;
        String demoMode = http.getHeader("X-Demo-Mode");
        boolean shouldUseDemoUser = enabled && "true".equalsIgnoreCase(demoMode);
        if (shouldUseDemoUser) {
            UserDTO demo = new UserDTO();
            demo.setId(DEMO_USER_ID);
            demo.setNickName("DemoUser");
            UserHolder.saveUser(demo);
        }
        try {
            chain.doFilter(req, res);
        } finally {
            if (shouldUseDemoUser) {
                UserHolder.removeUser();
            }
        }
    }
}
