# Sandbox for generated-app builds. NOT built or run in the Day 2 cloud session (see docs/week-plan.md Known gaps).
FROM eclipse-temurin:17-jdk-jammy

ARG CMDLINE_TOOLS_VERSION=11076708
ARG ANDROID_API=36
ARG BUILD_TOOLS=36.0.0
ARG GRADLE_VERSION=8.13

ENV ANDROID_HOME=/opt/android-sdk \
    ANDROID_SDK_ROOT=/opt/android-sdk \
    GRADLE_USER_HOME=/home/builder/.gradle \
    PATH=/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools:/opt/android-sdk/emulator:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends unzip curl ca-certificates git \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 builder && mkdir -p $ANDROID_HOME /work && chown -R builder /opt/android-sdk /work

USER builder
RUN curl -fsSL -o /tmp/cmdline.zip "https://dl.google.com/android/repository/commandlinetools-linux-${CMDLINE_TOOLS_VERSION}_latest.zip" \
    && mkdir -p $ANDROID_HOME/cmdline-tools && unzip -q /tmp/cmdline.zip -d $ANDROID_HOME/cmdline-tools \
    && mv $ANDROID_HOME/cmdline-tools/cmdline-tools $ANDROID_HOME/cmdline-tools/latest && rm /tmp/cmdline.zip \
    && yes | sdkmanager --licenses >/dev/null \
    && sdkmanager "platform-tools" "platforms;android-${ANDROID_API}" "build-tools;${BUILD_TOOLS}" \
       "emulator" "system-images;android-${ANDROID_API};google_apis;x86_64"

# Warm the Gradle distribution + daemon so first builds are fast. Dependency cache is warmed by
# building sandbox/warmup-project (added with the app templates).
RUN mkdir -p $GRADLE_USER_HOME && printf 'org.gradle.daemon=true\norg.gradle.caching=true\norg.gradle.jvmargs=-Xmx2g\n' > $GRADLE_USER_HOME/gradle.properties \
    && curl -fsSL -o /tmp/gradle.zip "https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip" \
    && unzip -q /tmp/gradle.zip -d /home/builder && rm /tmp/gradle.zip \
    && /home/builder/gradle-${GRADLE_VERSION}/bin/gradle --version >/dev/null

WORKDIR /work
# Network egress should be restricted by the runner to Maven Central and Google Maven.
# No secrets are baked in or passed as build args; signing keys are mounted at run time only for release builds.
CMD ["bash"]
