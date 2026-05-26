# ByteBites Grafana Dashboard

## Access

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://localhost:3001 | admin / bytebites |
| Prometheus | http://localhost:9090 | — |
| Prometheus targets | http://localhost:9090/targets | — |

## Dashboard Rows

| Row | Panels | Metrics Source |
|-----|--------|---------------|
| **Java JVM** | Heap Used (MB) · HTTP req/s by URI · P99 latency | `bytebites-java` actuator/prometheus |
| **RabbitMQ** | Queue depth · Published/Delivered msg/s | RabbitMQ prometheus plugin :15692 |
| **Java Business** | Bookings created (stat) · Active connections · Booking+Payment req/s | same Java actuator |
| **Python AI** | AI req/s by endpoint · P50/P99 latency · Starlette req/s · Total AI calls (stat) | FastAPI /metrics |

## Generate Traffic (verify graphs)

```bash
# Hit Java health a bunch
for i in $(seq 50); do curl -s http://localhost:8081/actuator/health > /dev/null; done

# AI agent requests
for i in $(seq 5); do
  curl -s -X POST https://localhost:3000/api/ai/agent \
    -H 'Content-Type: application/json' \
    -d '{"query":"信義區想吃火鍋","session_id":"load-test"}' > /dev/null
done

# Booking reserve
curl -s -X POST http://localhost:8081/api/booking/reserve \
  -H 'Content-Type: application/json' \
  -d '{"shopId":10102,"people":2,"date":"2026-05-28","time":"19:00"}'
```

## Scrape Targets

| Job | Endpoint | Interval |
|-----|----------|----------|
| bytebites-java | host.docker.internal:8081/actuator/prometheus | 10s |
| bytebites-python | host.docker.internal:8000/metrics | 10s |
| rabbitmq | hmdp-rabbitmq:15692/metrics | 10s |
