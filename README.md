# ai-enhanced-local-services

## Local Development
Copy `.env.example` to `.env`, fill in local credentials, then export those environment variables before starting backend or running Maven commands. `backend-java/src/main/resources/application.yaml` reads MySQL and Redis settings from env vars with local-safe defaults.
