package com.bytebites.service.oauth;

import com.fasterxml.jackson.databind.JsonNode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

@Slf4j
@Service
public class LineOAuthService {

    private final String clientId;
    private final String clientSecret;
    private final String redirectUri;
    private final String authorizeUrl;
    private final String tokenUrl;
    private final String scope;
    private final WebClient webClient;

    public LineOAuthService(
            @Value("${line.oauth.client-id}") String clientId,
            @Value("${line.oauth.client-secret}") String clientSecret,
            @Value("${line.oauth.redirect-uri}") String redirectUri,
            @Value("${line.oauth.authorize-url}") String authorizeUrl,
            @Value("${line.oauth.token-url}") String tokenUrl,
            @Value("${line.oauth.scope}") String scope
    ) {
        this.clientId = clientId;
        this.clientSecret = clientSecret;
        this.redirectUri = redirectUri;
        this.authorizeUrl = authorizeUrl;
        this.tokenUrl = tokenUrl;
        this.scope = scope;
        this.webClient = WebClient.builder().build();
    }

    public String buildAuthorizeUrl(String state) {
        validateConfigured();
        return authorizeUrl
                + "?response_type=code"
                + "&client_id=" + clientId
                + "&redirect_uri=" + URLEncoder.encode(redirectUri, StandardCharsets.UTF_8)
                + "&state=" + state
                + "&scope=" + URLEncoder.encode(scope, StandardCharsets.UTF_8);
    }

    public LineProfile exchangeCodeForProfile(String code) {
        validateConfigured();
        MultiValueMap<String, String> form = new LinkedMultiValueMap<>();
        form.add("grant_type", "authorization_code");
        form.add("code", code);
        form.add("redirect_uri", redirectUri);
        form.add("client_id", clientId);
        form.add("client_secret", clientSecret);

        JsonNode tokenResp = webClient.post()
                .uri(tokenUrl)
                .header("Content-Type", "application/x-www-form-urlencoded")
                .body(BodyInserters.fromFormData(form))
                .retrieve()
                .bodyToMono(JsonNode.class)
                .block();

        if (tokenResp == null || !tokenResp.has("id_token")) {
            throw new IllegalStateException("LINE token endpoint did not return id_token");
        }

        String idToken = tokenResp.get("id_token").asText();
        return parseIdToken(idToken);
    }

    private LineProfile parseIdToken(String idToken) {
        String[] parts = idToken.split("\\.");
        if (parts.length != 3) {
            throw new IllegalStateException("malformed id_token");
        }
        try {
            String payloadJson = new String(
                    java.util.Base64.getUrlDecoder().decode(parts[1]),
                    StandardCharsets.UTF_8
            );
            com.fasterxml.jackson.databind.ObjectMapper m = new com.fasterxml.jackson.databind.ObjectMapper();
            JsonNode p = m.readTree(payloadJson);

            LineProfile profile = new LineProfile();
            profile.setSub(p.path("sub").asText());
            profile.setName(p.path("name").asText(null));
            profile.setPicture(p.path("picture").asText(null));
            profile.setEmail(p.path("email").asText(null));
            return profile;
        } catch (Exception e) {
            throw new IllegalStateException("failed to decode id_token payload", e);
        }
    }

    private void validateConfigured() {
        if (clientId == null || clientId.isBlank() || "placeholder_channel_id".equals(clientId)
                || clientSecret == null || clientSecret.isBlank() || "placeholder_channel_secret".equals(clientSecret)) {
            throw new IllegalStateException("LINE OAuth is not configured. Set LINE_CHANNEL_ID and LINE_CHANNEL_SECRET.");
        }
    }

    @lombok.Data
    public static class LineProfile {
        private String sub;
        private String name;
        private String picture;
        private String email;
    }
}
