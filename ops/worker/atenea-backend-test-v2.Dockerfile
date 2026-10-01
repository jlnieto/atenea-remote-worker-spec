# Only this reviewed recipe and the hash-locked canonical pom are build inputs.
# Candidate sources execute later, offline, in a fresh rootless container.
FROM maven:3.9.11-eclipse-temurin-21 AS maven
FROM ubuntu:24.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git openssh-client openjdk-21-jdk-headless postgresql-16 python3 \
    && rm -rf /var/lib/apt/lists/* \
    && (getent passwd 1000 >/dev/null \
        || useradd --uid 1000 --no-create-home --home-dir /work/home atenea-test)
COPY --from=maven /usr/share/maven /usr/share/maven
ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
ENV PATH=/usr/share/maven/bin:/usr/lib/postgresql/16/bin:/usr/bin:/bin
COPY pom.xml /opt/atenea-build/pom.xml
RUN printf '%s\n' \
       '<settings xmlns="http://maven.apache.org/SETTINGS/1.2.0"><mirrors><mirror><id>central</id><mirrorOf>*</mirrorOf><url>https://repo.maven.apache.org/maven2</url></mirror></mirrors></settings>' \
       > /opt/atenea-build/settings.xml \
    && cd /opt/atenea-build \
    && mvn -s /opt/atenea-build/settings.xml -B -q -Dmaven.repo.local=/opt/atenea-m2 dependency:go-offline \
    && mvn -s /opt/atenea-build/settings.xml -B -q -Dmaven.repo.local=/opt/atenea-m2 dependency:resolve -DincludeScope=test \
    && mvn -s /opt/atenea-build/settings.xml -B -q -Dmaven.repo.local=/opt/atenea-m2 dependency:get \
       -Dartifact=org.apache.maven.surefire:surefire-junit-platform:3.5.4 \
    && mvn -s /opt/atenea-build/settings.xml -B -q -Dmaven.repo.local=/opt/atenea-m2 dependency:get \
       -Dartifact=org.junit.platform:junit-platform-launcher:1.11.4 \
    && chmod -R a+rX /opt/atenea-m2
COPY atenea-backend-test-v2.py /opt/atenea-backend-test-v2.py
WORKDIR /work
USER 1000:0
CMD ["/bin/sleep", "infinity"]
