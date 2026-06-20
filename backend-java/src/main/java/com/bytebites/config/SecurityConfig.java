package com.bytebites.config;

import com.bytebites.security.JwtAuthenticationFilter;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import jakarta.servlet.http.HttpServletResponse;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

@Configuration
@EnableWebSecurity
public class SecurityConfig {

    private final JwtAuthenticationFilter jwtAuthenticationFilter;

    @Value("${bytebites.cors.allowed-origin-patterns:}")
    private String extraAllowedOriginPatterns;

    public SecurityConfig(JwtAuthenticationFilter jwtAuthenticationFilter) {
        this.jwtAuthenticationFilter = jwtAuthenticationFilter;
    }

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
                .csrf(csrf -> csrf.disable())
                .cors(cors -> cors.configurationSource(corsConfigurationSource()))
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .exceptionHandling(ex -> ex.authenticationEntryPoint(
                        (request, response, authException) -> response.sendError(HttpServletResponse.SC_UNAUTHORIZED)
                ))
                        .authorizeHttpRequests(auth -> auth
                        .requestMatchers(
                                "/api/auth/line/**",
                                "/api/demo/**",
                                "/api/category/**",
                                "/api/mrt/**",
                                "/api/merchant/**",
                                "/api/parking/**",
                                "/api/shop/**",
                                "/api/shop/nearby-mrt/**",
                                "/api/shop-type/**",
                                "/api/user/login",
                                "/api/user/code"
                        ).permitAll()
                        .requestMatchers(HttpMethod.GET, "/api/auth/line/**").permitAll()
                        .requestMatchers(HttpMethod.GET, "/shop/**", "/shop-type/**").permitAll()
                        .requestMatchers(HttpMethod.GET, "/api/shop/**", "/api/shop-type/**").permitAll()
                        .requestMatchers("/merchant/**").permitAll()
                        .requestMatchers("/upload/**", "/voucher/**", "/voucher/list/**", "/blog/hot").permitAll()
                        .requestMatchers("/voucher-order/seckill/**", "/api/voucher-order/seckill/**").permitAll()
                        .requestMatchers("/payment/**", "/api/payment/**").permitAll()
                        .requestMatchers("/booking/**", "/api/booking/**").permitAll()
                        .requestMatchers("/availability/**", "/api/availability/**").permitAll()
                        .requestMatchers("/favorites/**", "/api/favorites/**").permitAll()
                        .requestMatchers("/dining-memory/**", "/api/dining-memory/**").permitAll()
                        .requestMatchers("/private-offers/**", "/api/private-offers/**").permitAll()
                        .requestMatchers("/user/login", "/user/code", "/error", "/actuator/**").permitAll()
                        .anyRequest().authenticated()
                )
                .addFilterBefore(jwtAuthenticationFilter, UsernamePasswordAuthenticationFilter.class);
        return http.build();
    }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration cfg = new CorsConfiguration();
        List<String> allowedOrigins = new ArrayList<>(List.of(
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:5173",
                "http://localhost:8080",
                "https://localhost:3000",
                "https://*.ngrok-free.app",
                "https://*.ngrok-free.dev",
                "https://*.ngrok.io"
        ));
        Arrays.stream(extraAllowedOriginPatterns.split(","))
                .map(String::trim)
                .filter(pattern -> !pattern.isEmpty())
                .forEach(allowedOrigins::add);
        cfg.setAllowedOriginPatterns(allowedOrigins);
        cfg.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE", "OPTIONS"));
        cfg.setAllowedHeaders(List.of("*"));
        cfg.setAllowCredentials(true);
        UrlBasedCorsConfigurationSource src = new UrlBasedCorsConfigurationSource();
        src.registerCorsConfiguration("/**", cfg);
        return src;
    }
}
