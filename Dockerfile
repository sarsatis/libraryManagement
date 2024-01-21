FROM khipu/openjdk17-alpine:latest
VOLUME /tmp
EXPOSE 8080

ARG NAME=default
COPY /target/$NAME-0.0.1-SNAPSHOT.jar app.jar

ENTRYPOINT ["java","-jar","/app.jar"]