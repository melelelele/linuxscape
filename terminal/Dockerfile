FROM debian:bookworm-slim

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        cowsay \
        figlet \
        findutils \
        gcc \
        less \
        libc6-dev \
        openssh-server \
        passwd \
        procps \
        psmisc \
        python3 \
        sl \
        util-linux \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd \
        --gid 1000 \
        linuxscape \
    && useradd \
        --uid 1000 \
        --gid 1000 \
        --create-home \
        --home-dir /home/linuxscape \
        --shell /bin/bash \
        linuxscape

COPY queue-worker-mem.c /tmp/queue-worker-mem.c

RUN gcc \
        -O2 \
        -Wall \
        -Wextra \
        -o /usr/local/bin/queue-worker-mem \
        /tmp/queue-worker-mem.c \
    && rm /tmp/queue-worker-mem.c

COPY lab/reset-lab.original.sh \
    /opt/linuxscape/reset-lab.original.sh

COPY reset-lab.sh \
    /usr/local/sbin/reset-lab

COPY entrypoint.sh \
    /usr/local/sbin/linuxscape-entrypoint

COPY linuxscape-shell \
    /usr/local/bin/linuxscape-shell

COPY record-command.py \
    /usr/local/bin/linuxscape-record-command

COPY bashrc \
    /etc/linuxscape/bashrc

COPY sshd_config \
    /etc/ssh/sshd_config

RUN chmod 0755 \
        /opt/linuxscape/reset-lab.original.sh \
        /usr/local/sbin/reset-lab \
        /usr/local/sbin/linuxscape-entrypoint \
        /usr/local/bin/linuxscape-shell \
        /usr/local/bin/linuxscape-record-command \
    && chmod 0644 \
        /etc/linuxscape/bashrc \
        /etc/ssh/sshd_config \
    && mkdir -p \
        /run/sshd \
        /run/linuxscape

EXPOSE 22

ENTRYPOINT ["/usr/local/sbin/linuxscape-entrypoint"]
