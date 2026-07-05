# Build stage
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /app
COPY pom.xml .
# 先抓依賴層，改 code 不會重新下載整個 maven repo
RUN mvn -q dependency:go-offline -B || true
COPY src ./src
RUN mvn -q package -DskipTests -B && cp target/*.jar app.jar

# Runtime stage
FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /app/app.jar app.jar
EXPOSE 8081
# 記憶體上限交由 compose 的 mem_limit 控制；容器內感知 cgroup 上限
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75", "-jar", "app.jar"]
