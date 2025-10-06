# syntax=docker/dockerfile:1

FROM --platform=$BUILDPLATFORM rust:1.86 as builder

# Install dependencies for cross-compilation
RUN apt-get update && apt-get install -y \
    clang \
    libclang-dev \
    gcc-aarch64-linux-gnu \
    libc6-dev-arm64-cross \
    protobuf-compiler \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for cross-compilation
ARG TARGETPLATFORM
ARG BUILDPLATFORM
ARG TARGETOS
ARG TARGETARCH

# Configure Rust for the target architecture
RUN case ${TARGETARCH} in \
    "amd64") \
        echo "x86_64-unknown-linux-gnu" > /tmp/target.txt && \
        echo "" > /tmp/linker.txt \
        ;; \
    "arm64") \
        echo "aarch64-unknown-linux-gnu" > /tmp/target.txt && \
        echo "CC_aarch64_unknown_linux_gnu=aarch64-linux-gnu-gcc" > /tmp/linker.txt && \
        echo "CXX_aarch64_unknown_linux_gnu=aarch64-linux-gnu-g++" >> /tmp/linker.txt && \
        echo "AR_aarch64_unknown_linux_gnu=aarch64-linux-gnu-ar" >> /tmp/linker.txt && \
        echo "CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_LINKER=aarch64-linux-gnu-gcc" >> /tmp/linker.txt \
        ;; \
    *) \
        echo "Unsupported architecture: ${TARGETARCH}" && exit 1 \
        ;; \
    esac

# Read target and set environment
RUN TARGET=$(cat /tmp/target.txt) && \
    rustup target add $TARGET && \
    rustup target add wasm32-unknown-unknown && \
    rustup component add rust-src && \
    if [ -s /tmp/linker.txt ]; then \
        export $(cat /tmp/linker.txt | xargs); \
    fi

# Create a non-root user for security
RUN useradd -m -u 1000 qxchain

# Set working directory
WORKDIR /build

# Copy workspace configuration first for better caching
COPY Cargo.toml Cargo.lock* ./

# Copy source files
COPY node ./node/
COPY runtime ./runtime/
COPY pallets ./pallets/

# Build the project (without cache to ensure clean build)
RUN TARGET=$(cat /tmp/target.txt) && \
    if [ -s /tmp/linker.txt ]; then \
        export $(cat /tmp/linker.txt | xargs); \
    fi && \
    cargo build --release --target=$TARGET --locked -p qxchain && \
    cp target/$TARGET/release/qxchain /tmp/qxchain && \
    rm -rf target

# Runtime stage - use distroless for security and minimal size
FROM gcr.io/distroless/cc-debian12

# Copy the binary
COPY --from=builder /tmp/qxchain /usr/local/bin/qxchain

# Create non-root user in runtime image
USER 1000:1000

# Expose ports
EXPOSE 9944 30333

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD ["/usr/local/bin/qxchain", "--version"]

# Default command
ENTRYPOINT ["/usr/local/bin/qxchain"]
CMD ["--chain=dev", "--rpc-port=9944", "--port=30333", "--rpc-cors=all", "--rpc-methods=unsafe", "--rpc-external", "--consensus=instant-seal", "--alice", "--dev"]