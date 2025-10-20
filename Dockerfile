# ------------------------------------------------------------------------------
#  QXChain Dockerfile (hardened)
#  – Builds production and local binaries
#  – Final runtime images run as non-root `qxchain` user (UID/GID 10001)
# ------------------------------------------------------------------------------

###############################################################################
# ---------- 1. Common build environment -------------------------------------
###############################################################################
ARG BASE_IMAGE=rust:latest
FROM ${BASE_IMAGE} AS base_builder

# Rust targets and components
RUN rustup update stable && \
  rustup component add rust-src && \
  rustup target add wasm32-unknown-unknown

# Build prerequisites
ENV RUST_BACKTRACE=1
RUN apt-get update && \
  apt-get install -y --no-install-recommends \
  curl build-essential protobuf-compiler clang git pkg-config libssl-dev && \
  rm -rf /var/lib/apt/lists/*

# Copy entire repository once for all build stages (maximises cache hits)
COPY . /build
WORKDIR /build

###############################################################################
# ---------- 2. Production build stage ---------------------------------------
###############################################################################
FROM base_builder AS prod_builder

# Build the production binary (profile defined in Cargo.toml)
RUN cargo build -p qxchain --profile production --locked \
  && test -e /build/target/production/qxchain  # sanity-check

###############################################################################
# ---------- 3. Final production image (hardened) ----------------------------
###############################################################################
FROM ${BASE_IMAGE} AS qxchain-production

# ---- security hardening: create least-privilege user ----
RUN addgroup --system --gid 10001 qxchain && \
  adduser  --system --uid 10001 --gid 10001 --home /home/qxchain --disabled-password qxchain

# Install gosu for privilege dropping
RUN apt-get update && apt-get install -y gosu && \
  rm -rf /var/lib/apt/lists/*

# Writable data directory to be used as --base-path
RUN mkdir -p /data && chown -R qxchain:qxchain /data

# Workdir for the non-root user
WORKDIR /home/qxchain

# Copy chainspecs and binary with correct ownership
COPY --chown=qxchain:qxchain --from=prod_builder /build/*.json ./
COPY --chown=qxchain:qxchain --from=prod_builder /build/chainspecs/*.json ./chainspecs/
COPY --from=prod_builder /build/target/production/qxchain /usr/local/bin/
RUN chown qxchain:qxchain /usr/local/bin/qxchain

# Copy and prepare entrypoint
COPY ./scripts/docker_entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 30333 9933 9944

# Run entrypoint as root to handle permissions, then drop to qxchain user
# in the script
USER root
ENTRYPOINT ["/entrypoint.sh"]
CMD ["--base-path", "/data"]

###############################################################################
# ---------- 4. Local build stage --------------------------------------------
###############################################################################
FROM base_builder AS local_builder

# Build the workspace in release mode
RUN cargo build --workspace --profile release \
  && test -e /build/target/release/qxchain  # sanity-check

###############################################################################
# ---------- 5. Final local image (hardened) ----------------------------------
###############################################################################
FROM ${BASE_IMAGE} AS qxchain-local

# Least-privilege user
RUN addgroup --system --gid 10001 qxchain && \
  adduser  --system --uid 10001 --gid 10001 --home /home/qxchain --disabled-password qxchain

# Install gosu for privilege dropping
RUN apt-get update && apt-get install -y gosu && \
  rm -rf /var/lib/apt/lists/*

RUN mkdir -p /data && chown -R qxchain:qxchain /data
WORKDIR /home/qxchain

# Copy artifacts
COPY --chown=qxchain:qxchain --from=local_builder /build/*.json ./
COPY --chown=qxchain:qxchain --from=local_builder /build/chainspecs/*.json ./chainspecs/
COPY --from=local_builder /build/target/release/qxchain /usr/local/bin/
RUN chown qxchain:qxchain /usr/local/bin/qxchain

# Copy and prepare entrypoint
COPY ./scripts/docker_entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Generate a local chainspec for convenience (run as root before user switch)
RUN qxchain build-spec --disable-default-bootnode --raw --chain localnet > /localnet.json \
  && chown qxchain:qxchain /localnet.json

EXPOSE 30333 9933 9944

# Run entrypoint as root to handle permissions, then drop to qxchain user
# in the script
USER root
ENTRYPOINT ["/entrypoint.sh"]
CMD ["--base-path","/data","--chain","/localnet.json"]
