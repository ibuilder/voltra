# Custom Caddy image with the rate-limit module (not in the stock image).
# Built by docker compose (see the caddy service). Compiles once, then cached.
FROM caddy:2-builder AS builder
RUN xcaddy build --with github.com/mholt/caddy-ratelimit

FROM caddy:2-alpine
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
