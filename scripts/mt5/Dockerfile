FROM ubuntu:24.04@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac
ARG BUILD_REVISION=unknown
LABEL org.opencontainers.image.revision=${BUILD_REVISION}
ENV DEBIAN_FRONTEND=noninteractive
RUN dpkg --add-architecture i386 \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && mkdir -pm755 /etc/apt/keyrings \
    && curl -fsSL https://dl.winehq.org/wine-builds/winehq.key -o /etc/apt/keyrings/winehq-archive.key \
    && curl -fsSL https://dl.winehq.org/wine-builds/ubuntu/dists/noble/winehq-noble.sources -o /etc/apt/sources.list.d/winehq.sources \
    && apt-get update \
    && apt-get install -y --install-recommends winehq-stable \
    && apt-get install -y --no-install-recommends xvfb x11vnc novnc websockify openbox x11-utils x11-xserver-utils xdotool fonts-liberation procps \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 10001 --shell /bin/bash mt5 \
    && mkdir -p /opt/mt5
COPY --chmod=755 entrypoint.sh /opt/mt5/entrypoint.sh
COPY MarketDataService.mq5 CalendarService.mq5 /opt/mt5/mql5/
USER mt5
ENV HOME=/home/mt5 WINEPREFIX=/home/mt5/.wine WINEARCH=win64 DISPLAY=:99 WINEDEBUG=-all
WORKDIR /home/mt5
EXPOSE 6080
ENTRYPOINT ["/opt/mt5/entrypoint.sh"]
