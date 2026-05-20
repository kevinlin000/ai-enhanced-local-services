package com.hmdp.security;

import com.hmdp.dto.UserDTO;
import com.hmdp.utils.UserHolder;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.Collections;

@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private final JwtTokenProvider tokenProvider;

    public JwtAuthenticationFilter(JwtTokenProvider tokenProvider) {
        this.tokenProvider = tokenProvider;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        try {
            String token = extract(request);
            if (token != null) {
                Claims claims = tokenProvider.parse(token);
                Long userId = Long.parseLong(claims.getSubject());

                UserDTO userDTO = new UserDTO();
                userDTO.setId(userId);
                UserHolder.saveUser(userDTO);

                UsernamePasswordAuthenticationToken auth =
                        new UsernamePasswordAuthenticationToken(userId, null, Collections.emptyList());
                SecurityContextHolder.getContext().setAuthentication(auth);
            }
            chain.doFilter(request, response);
        } catch (JwtException e) {
            SecurityContextHolder.clearContext();
            chain.doFilter(request, response);
        } finally {
            UserHolder.removeUser();
            SecurityContextHolder.clearContext();
        }
    }

    private String extract(HttpServletRequest req) {
        String h = req.getHeader("Authorization");
        if (h != null && h.startsWith("Bearer ")) {
            return h.substring(7);
        }
        String legacy = req.getHeader("authorization");
        if (legacy != null && !legacy.isBlank() && !legacy.startsWith("Bearer ")) {
            return legacy;
        }
        return null;
    }
}
