FROM ubuntu:24.04@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac AS wine-runtime
ENV DEBIAN_FRONTEND=noninteractive
RUN dpkg --add-architecture i386 \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && mkdir -pm755 /etc/apt/keyrings \
    && curl -fsSL https://dl.winehq.org/wine-builds/winehq.key -o /etc/apt/keyrings/winehq-archive.key \
    && curl -fsSL https://dl.winehq.org/wine-builds/ubuntu/dists/noble/winehq-noble.sources -o /etc/apt/sources.list.d/winehq.sources \
    && apt-get update \
    && apt-get install -y --install-recommends winehq-stable \
    && apt-get install -y --no-install-recommends xvfb openbox x11-utils x11-xserver-utils xdotool fonts-liberation procps python3 \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 10001 --shell /bin/bash mt5 \
    && mkdir -p /opt/mt5 \
    && chown mt5:mt5 /opt/mt5
USER mt5
ENV HOME=/home/mt5 WINEPREFIX=/home/mt5/.wine WINEARCH=win64 DISPLAY=:99 WINEDEBUG=-all
WORKDIR /home/mt5

FROM wine-runtime AS installed
COPY --chmod=755 install.sh /opt/mt5/install.sh
COPY factory-common.ini /opt/mt5/factory-common.ini
RUN /opt/mt5/install.sh

FROM installed AS builder
COPY prepare_factory.py /opt/mt5/prepare_factory.py
COPY --chmod=755 factory.sh /opt/mt5/factory.sh
RUN --mount=type=tmpfs,target=/tmp /opt/mt5/factory.sh

FROM builder AS compiled
COPY MarketDataService.mq5 CalendarService.mq5 FileSharingCheck.mq5 /opt/mt5/mql5/
COPY --chmod=755 compile.sh /opt/mt5/compile.sh
# X sockets from a previous build step must not survive into the compiler step.
RUN --mount=type=tmpfs,target=/tmp /opt/mt5/compile.sh

FROM builder AS clean-prefix
RUN find /home/mt5 -type f -iname '*metaeditor*' -delete

# Copy the prepared prefix once; installer/compiler layers never enter the runtime.
FROM wine-runtime AS runtime
ARG BUILD_REVISION=unknown
LABEL org.opencontainers.image.revision=${BUILD_REVISION}
COPY --from=clean-prefix --chown=mt5:mt5 /home/mt5/ /home/mt5/
COPY --from=compiled --chown=mt5:mt5 /opt/mt5/services/ /opt/mt5/services/
COPY --chmod=755 entrypoint.sh /opt/mt5/entrypoint.sh
COPY configure.py /opt/mt5/configure.py
COPY runtime_ui.py /opt/mt5/runtime_ui.py
ENTRYPOINT ["/opt/mt5/entrypoint.sh"]
