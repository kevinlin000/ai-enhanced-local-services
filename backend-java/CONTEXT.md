# Backend Java Context

## Scope

`backend-java` owns transactional business behavior for the ByteBites platform.

## Technology

- Spring Boot 3.x
- Java 17+
- Spring Security + JWT
- Spring Data JPA + Hibernate
- MySQL 8
- Redis / Redisson
- RabbitMQ where business messaging is needed

## Domain Terms

- `User`: authenticated platform user
- `Shop`: restaurant/store entity
- `Booking`: restaurant reservation record
- `Deposit`: payment amount required to hold a booking
- `Payment`: demo payment state and transaction identifier
- `AvailabilityWatch`: user request to monitor future availability
- `Parking`: parking-related recommendation or reminder around a booking

## Boundaries

- Java is the source of truth for booking, payment, and persisted user state.
- Java should expose internal APIs for Python when AI needs business data.
- Java should not own RAG, embeddings, or LLM orchestration.
