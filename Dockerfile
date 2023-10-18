FROM khipu/openjdk17-alpine:latest
VOLUME /tmp
EXPOSE 8080

COPY /target/LibraryManagementSystem-0.0.1-SNAPSHOT.jar app.jar

ENTRYPOINT ["java","-jar","/app.jar"]



