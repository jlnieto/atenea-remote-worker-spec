# App's hash-locked SDK/Gradle Dockerfile precedes this reviewed fragment.
# COPY contains only hash-locked configuration, never candidate source/secrets.
RUN apt-get update && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/* \
    && (getent passwd 1000 >/dev/null \
        || useradd --uid 1000 --no-create-home --home-dir /work/home atenea-test) \
    && install -d -o 1000 -g 0 -m 0700 /work
COPY android /source/android
COPY atenea-android-runtime-v2.py /opt/atenea-android-runtime-v2.py
RUN python3 /opt/atenea-android-runtime-v2.py --seed \
    && cd /source/android \
    && GRADLE_USER_HOME=/opt/atenea-build-gradle gradle --no-daemon --console plain \
       -Pkotlin.compiler.execution.strategy=in-process :app:assembleDebug testDebugUnitTest \
    && python3 /opt/atenea-android-runtime-v2.py --seal
USER 1000:0
ENV GRADLE_USER_HOME=/work/gradle-home
ENV ANDROID_USER_HOME=/work/android-home
WORKDIR /work
# Prove a cold, relocated dependency cache with no network or task outputs.
RUN --network=none python3 /opt/atenea-android-runtime-v2.py --prepare \
    && cd /work/repo/android \
    && gradle --offline --no-daemon --console plain \
       -Pkotlin.compiler.execution.strategy=in-process :app:assembleDebug testDebugUnitTest
CMD ["/bin/sleep", "infinity"]
