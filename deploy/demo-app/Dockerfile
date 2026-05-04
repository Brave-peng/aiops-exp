FROM golang:1.22-alpine AS build

WORKDIR /src
COPY app/go.mod ./
COPY app/main.go ./
RUN CGO_ENABLED=0 GOOS=linux go build -o /out/demo-app .

FROM alpine:3.20

RUN adduser -D -H -u 10001 appuser
USER appuser

COPY --from=build /out/demo-app /demo-app

EXPOSE 8080
ENTRYPOINT ["/demo-app"]

