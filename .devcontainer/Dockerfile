# It is tested on an M3 Mac but is intended to work for x86 architectures as well.
FROM python:3.12-slim
ARG TARGETPLATFORM

# Set `DEVCONTAINER` environment variable to help with orientation
ENV DEVCONTAINER=true

USER root

# Install basic development tools and iptables/ipset
RUN apt update && apt install -y less \
  git \
  procps \
  sudo \
  zsh \
  man-db \
  unzip \
  gnupg2 \
  gh \
  iptables \
  ipset \
  iproute2 \
  dnsutils \
  aggregate \
  jq \
  curl \
  wget \
  vim \
  libgdal-dev \
  g++ \
  libc6 \
  sqlite3 \
  libsqlite3-dev \
  && rm -rf /var/lib/apt/lists/*

# Install Git LFS
RUN curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.deb.sh | sudo bash && \
  apt-get install -y git-lfs

# Install NodeJS
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
  && apt-get install -y nodejs \
  && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /usr/local/share/npm-global

# Create config directory and set permissions
RUN mkdir -p /root/.claude

# Install global packages
ENV NPM_CONFIG_PREFIX=/usr/local/share/npm-global
ENV PATH=$PATH:/usr/local/share/npm-global/bin

# Set the default shell to zsh rather than sh
ENV SHELL=/bin/zsh

# Default Powerlevel10k theme
RUN sh -c "$(wget -O- https://github.com/deluan/zsh-in-docker/releases/download/v1.2.0/zsh-in-docker.sh)" -- \
  -p git \
  -p colorize \
  -p uv \
  -p https://github.com/zsh-users/zsh-autosuggestions \
  -p https://github.com/zsh-users/zsh-completions \
  -x

# Install Claude
RUN npm install -g @anthropic-ai/claude-code

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
# Add uv to path
ENV PATH="$PATH:/root/.local/bin"

# Copy and set up dev environment script
USER root
COPY setup-dev-environment.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/setup-dev-environment.sh

# Copy CLAUDE.md and settings to Claude config directory
COPY CLAUDE.md /root/.claude/
