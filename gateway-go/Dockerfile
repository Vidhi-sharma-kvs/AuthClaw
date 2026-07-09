FROM golang:1.23-alpine AS build

WORKDIR /src

COPY go.mod ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /out/authclaw-gateway ./cmd/authclaw-gateway

FROM alpine:3.20

RUN apk update && apk upgrade --no-cache
RUN adduser -D -H -s /sbin/nologin authclaw
COPY --from=build /out/authclaw-gateway /usr/local/bin/authclaw-gateway

USER authclaw
EXPOSE 9000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1:9000/health/ready || exit 1

CMD ["authclaw-gateway"]
