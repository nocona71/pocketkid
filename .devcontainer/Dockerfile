FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

RUN rm -f /etc/apt/sources.list.d/yarn.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        sqlite3 \
        git \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt /tmp/pocketkid/
RUN python -m pip install --no-cache-dir -r /tmp/pocketkid/requirements-dev.txt

RUN mkdir -p \
        /home/vscode/.bash-history \
        /home/vscode/.vscode-server/data/User \
        /home/vscode/.vscode-server/data/agentSessionData \
        /home/vscode/.copilot/chats \
        /home/vscode/.copilot/session-state \
        /home/vscode/.config/gh \
        /home/vscode/.ssh \
    && chown -R vscode:vscode \
        /home/vscode/.bash-history \
        /home/vscode/.vscode-server \
        /home/vscode/.copilot \
        /home/vscode/.config/gh \
        /home/vscode/.ssh \
    && chmod 700 /home/vscode/.ssh

RUN printf '\nshopt -s histappend\nPROMPT_COMMAND="history -a${PROMPT_COMMAND:+; $PROMPT_COMMAND}"\n' \
    >> /home/vscode/.bashrc
